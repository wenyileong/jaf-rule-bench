# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Wen Yi LEONG
"""The file library: every export and import in one folder, shown, checked and moved safely.

Modelled on the A-share Company Intelligence data folder (its ``files`` and ``datafolder`` modules), with the same
principles:

* **preview first** - every operation that changes files has a dry run that changes nothing;
* **nothing is lost** - deleting moves to the library's Trash, which only an explicit "empty" clears; moving the
  library copies into a temporary folder, verifies, then switches, and leaves the old folder untouched;
* **checked** - each saved bundle carries a manifest with the SHA-256 of every file, so changes, damage and
  incomplete copies are detected; packages for another device carry the same and are verified on import;
* **recorded** - every operation is logged in the library (``.jaf/log.jsonl``), including operations that stopped
  partway, and the most recent change can be undone (one level).

Links (symbolic links, Windows junctions) are never followed: a path through a link is refused, and links inside
folders are skipped when copying, packaging, hashing or moving.

Layout of the library (default: Documents/JAF Rule Bench)::

    Exports/     results, coded-world and estimation bundles saved by the program
    Imports/     a copy of every workbook or record loaded, and every package imported
    Packages/    packages made for another device (.jafpack)
    <any folders the user creates>
    .jaf/        the log, the Trash and temporary files (not shown as an ordinary folder)

Nothing here sends anything over the network. Build plan, section 15 (and 15.7 for the review fixes).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from .params import VERSION

MANIFEST = "manifest.json"
PACKAGE_INDEX = "package.json"
PACKAGE_EXT = ".jafpack"
INTERNAL = ".jaf"
TRASH_INDEX = "trash-index.json"
STANDARD = ("Exports", "Imports", "Packages")
MAX_PACKAGE_BYTES = 2 * 1024 ** 3          # uncompressed size accepted from a package
MAX_PACKAGE_FILES = 20000
_BAD = re.compile(r'[\\/:*?"<>|\r\n\t\x00-\x1f]+')
_RESERVED = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
             *(f"COM{i}" for i in "123456789¹²³"), *(f"LPT{i}" for i in "123456789¹²³")}
SYNCED = ("onedrive", "dropbox", "google drive", "googledrive", "icloud", "box sync")
UNDO_SKIPS = ("verify", "save", "import", "package", "import_package")   # record-only: do not end the undo chain
UNDOABLE = ("move", "copy", "rename", "trash", "make_folder")


class LibraryError(ValueError):
    pass


# ---- basics --------------------------------------------------------------------------------------------
def now_stamp():
    return datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def safe_name(text: str, limit: int = 100) -> str:
    """A file or folder name valid on Windows, macOS and Linux."""
    t = _BAD.sub(" ", str(text or "")).strip(" .")
    t = re.sub(r"\s+", " ", t)[:limit].rstrip(" .")
    if not t:
        return "untitled"
    if t.split(".")[0].strip().upper() in _RESERVED:
        t = "_" + t
    return t


def is_link(p: Path) -> bool:
    try:
        if p.is_symlink():
            return True
        j = getattr(p, "is_junction", None)            # Windows junctions (Python 3.12+)
        return bool(j and j())
    except OSError:
        return False


def walk_files(folder: Path):
    """Every regular file under folder, without following or including links."""
    for dirpath, dirnames, filenames in os.walk(folder, followlinks=False):
        d = Path(dirpath)
        dirnames[:] = [n for n in dirnames if not is_link(d / n)]
        for n in filenames:
            p = d / n
            if not is_link(p) and p.is_file():
                yield p


def sha256_file(p: Path, chunk=1 << 20) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def _size(p: Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return 0


def folder_stats(folder: Path):
    n = total = 0
    if folder.exists():
        for p in walk_files(folder):
            if INTERNAL not in p.relative_to(folder).parts:
                n += 1
                total += _size(p)
    return n, total


def _taken(folder: Path, name: str, also=()) -> bool:
    """Is a name taken in a folder, compared without regard to case (as Windows and macOS do)?"""
    key = name.casefold()
    if any(x.casefold() == key for x in also):
        return True
    try:
        return any(q.name.casefold() == key for q in folder.iterdir())
    except OSError:
        return False


def unique_path(p: Path, also=()) -> Path:
    """p, or 'name (2).ext', 'name (3).ext' ... if the name is taken (case-insensitively)."""
    if not _taken(p.parent, p.name, also):
        return p
    stem, suf = (p.stem, p.suffix) if p.suffix and not p.is_dir() else (p.name, "")
    i = 2
    while True:
        q = p.with_name(f"{stem} ({i}){suf}")
        if not _taken(p.parent, q.name, also):
            return q
        i += 1


def same_device(a: Path, b: Path) -> bool:
    try:
        tb = b
        while not tb.exists() and tb != tb.parent:
            tb = tb.parent
        return os.stat(a).st_dev == os.stat(tb).st_dev
    except OSError:
        return False


def _copy_tree(src: Path, dst: Path):
    """Copy a folder or file without following links (links are skipped)."""
    if src.is_file():
        shutil.copy2(src, dst)
        return
    dst.mkdir(parents=True, exist_ok=False)
    for f in walk_files(src):
        q = dst / f.relative_to(src)
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, q)


# ---- the library -----------------------------------------------------------------------------------------
class Library:
    def __init__(self, root, create=True):
        root = Path(root).expanduser()
        if not root.exists():
            if not create:
                raise LibraryError("The library folder does not exist.")
            if not root.parent.exists():                # e.g. a removable drive that is not connected
                raise LibraryError(f"The folder that should contain the library ({root.parent}) is not available.")
            root.mkdir()
        self.root = root.resolve()
        for s in STANDARD:
            (self.root / s).mkdir(exist_ok=True)
        (self.root / INTERNAL / "trash").mkdir(parents=True, exist_ok=True)
        (self.root / INTERNAL / "tmp").mkdir(parents=True, exist_ok=True)

    # paths -------------------------------------------------------------------------------------------
    def resolve(self, rel: str | None, allow_internal=False) -> Path:
        """The absolute path of a library-relative path, refusing anything outside the library or through a link."""
        rel = (rel or "").replace("\\", "/")
        if rel.startswith("/") or re.match(r"^[A-Za-z]:", rel) or rel.startswith("~"):
            raise LibraryError("Paths must be inside the library.")
        parts = [x for x in rel.strip("/").split("/") if x not in ("", ".")]
        if any(x == ".." for x in parts):
            raise LibraryError("Paths must be inside the library.")
        if parts and parts[0] == INTERNAL and not allow_internal:
            raise LibraryError("That folder belongs to the program.")
        cur = self.root
        for x in parts:                                   # no segment may be a link (review finding 6)
            cur = cur / x
            if is_link(cur):
                raise LibraryError("Links (shortcuts to other places) are not followed by the library.")
        p = cur.resolve()
        if p != self.root and self.root not in p.parents:
            raise LibraryError("Paths must be inside the library.")
        return p

    def rel(self, p: Path) -> str:
        return p.resolve().relative_to(self.root).as_posix()

    # log and undo ------------------------------------------------------------------------------------
    @property
    def log_path(self) -> Path:
        return self.root / INTERNAL / "log.jsonl"

    def log(self, op: str, **detail):
        rec = dict(id=f"{now_stamp()}-{uuid.uuid4().hex[:6]}", time=now_iso(), op=op, version=VERSION, **detail)
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def history(self, limit=100):
        if not self.log_path.exists():
            return []
        rows = []
        with open(self.log_path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                    if isinstance(r, dict):
                        rows.append(r)
                except json.JSONDecodeError:
                    continue
        undone = {r.get("undoes") for r in rows if r.get("op") == "undo"}
        for r in rows:
            r["undone"] = r.get("id") in undone
        return rows[-limit:][::-1]

    def last_undoable(self):
        """The most recent change, if it can be undone. One level only: an undo, or any operation that is not
        undoable, ends the chain (review finding 4)."""
        for r in self.history(1000):
            if r.get("op") in UNDO_SKIPS:
                continue
            op = r.get("op")
            if op in UNDOABLE and not r.get("undone") and (op == "make_folder" or r.get("moves")):
                return r
            return None
        return None

    # manifests ---------------------------------------------------------------------------------------
    def write_manifest(self, folder: Path, kind: str, title: str = "", **meta):
        files = []
        for p in sorted(walk_files(folder)):
            if p.name != MANIFEST or p.parent != folder:
                files.append(dict(path=p.relative_to(folder).as_posix(), bytes=_size(p), sha256=sha256_file(p)))
        man = dict(format="JAF Rule Bench bundle 1", kind=kind, title=title or folder.name, created=now_iso(),
                   tool_version=VERSION, files=files, **meta)
        (folder / MANIFEST).write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
        return man

    @staticmethod
    def read_manifest(folder: Path):
        try:
            m = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(m, dict) or not isinstance(m.get("files"), list):
            return None
        # keep only well-formed entries; everything shown is treated as untrusted text by the interface
        m["files"] = [f for f in m["files"] if isinstance(f, dict) and isinstance(f.get("path"), str)]
        return m

    def check_item(self, folder: Path, full=False):
        """Integrity of a bundle against its manifest: ok, changed, missing files, extra files."""
        man = self.read_manifest(folder)
        if man is None:
            return None
        changed, missing, listed = [], [], set()
        for f in man["files"]:
            listed.add(f["path"])
            parts = PurePosixPath(f["path"]).parts
            if ".." in parts or PurePosixPath(f["path"]).is_absolute():
                changed.append(f["path"]); continue
            p = folder.joinpath(*parts)
            if is_link(p) or not p.is_file():
                missing.append(f["path"])
            elif _size(p) != f.get("bytes") or (full and sha256_file(p) != f.get("sha256")):
                changed.append(f["path"])
        extra = [p.relative_to(folder).as_posix() for p in walk_files(folder)
                 if not (p.name == MANIFEST and p.parent == folder) and p.relative_to(folder).as_posix() not in listed]
        status = "ok" if not (changed or missing) else ("missing" if missing else "changed")
        return dict(status=status, checked="full" if full else "sizes", changed=changed, missing=missing, extra=extra)

    # listing and preview -----------------------------------------------------------------------------------
    def entry(self, p: Path, check=True):
        if is_link(p):
            return dict(name=p.name, rel=self.rel(p.parent) + "/" + p.name if p.parent != self.root else p.name,
                        type="link", note="a link to another place; not followed")
        st = p.stat()
        e = dict(name=p.name, rel=self.rel(p), type="folder" if p.is_dir() else "file",
                 modified=datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"))
        if p.is_dir():
            n, total = folder_stats(p)
            e.update(files=n, bytes=total)
            man = self.read_manifest(p)
            if man:
                e.update({k: str(man.get(k))[:200] for k in ("kind", "title", "created", "tool_version", "source") if man.get(k) is not None})
                if check:
                    e["integrity"] = self.check_item(p)["status"]
        else:
            e.update(bytes=st.st_size, ext=p.suffix.lower())
            if p.suffix.lower() == PACKAGE_EXT:
                e["kind"] = "package"
        return e

    def listing(self, rel=""):
        folder = self.resolve(rel)
        if not folder.is_dir():
            raise LibraryError("Not a folder.")
        has_man = self.read_manifest(folder) is not None
        entries = []
        for p in sorted(folder.iterdir(), key=lambda q: (not q.is_dir(), q.name.lower())):
            if (p.name == INTERNAL and folder == self.root) or (p.name == MANIFEST and has_man):
                continue
            try:
                entries.append(self.entry(p))
            except OSError:
                continue
        crumbs, acc = [dict(name="Library", rel="")], []
        for part in (Path(self.rel(folder)).parts if folder != self.root else ()):
            acc.append(part); crumbs.append(dict(name=part, rel="/".join(acc)))
        man = self.read_manifest(folder) if folder != self.root else None
        return dict(rel=self.rel(folder) if folder != self.root else "", crumbs=crumbs, entries=entries,
                    item=dict(manifest=man, integrity=self.check_item(folder)) if man else None,
                    folders=self.folder_tree(), trash=len(self.trash_list()))

    def folder_tree(self, max_depth=4):
        """All folders (for 'Move to'), excluding bundle contents, links and the program's own folder."""
        out = [""]
        def walk(p: Path, depth):
            if depth > max_depth:
                return
            for q in sorted((x for x in p.iterdir() if x.is_dir() and not is_link(x) and not (p == self.root and x.name == INTERNAL)),
                            key=lambda x: x.name.lower()):
                out.append(self.rel(q))
                if not self.read_manifest(q):
                    walk(q, depth + 1)
        walk(self.root, 1)
        return out

    def preview(self, rel, max_rows=60):
        p = self.resolve(rel)
        if p.is_dir():
            man = self.read_manifest(p)
            return dict(type="folder", entry=self.entry(p), manifest=man, integrity=self.check_item(p) if man else None)
        ext = p.suffix.lower()
        out = dict(type="file", entry=self.entry(p, check=False), ext=ext)
        try:
            if ext == ".csv":
                import csv
                with open(p, encoding="utf-8-sig", newline="", errors="replace") as fh:
                    rows = [r for _, r in zip(range(max_rows + 1), csv.reader(fh))]
                out.update(kind="table", rows=rows, truncated=len(rows) > max_rows)
            elif ext in (".json", ".md", ".txt", ".cff", ".log", ".jsonl"):
                with open(p, encoding="utf-8", errors="replace") as fh:
                    text = fh.read(60000)
                if ext == ".json" and _size(p) <= 60000:
                    try:
                        obj = json.loads(text)
                        if isinstance(obj, dict):
                            out["keys"] = [str(k)[:80] for k in list(obj)[:40]]
                            for k in ("version", "tool_version", "kind", "generated", "created", "fingerprint"):
                                if k in obj and not isinstance(obj[k], (dict, list)):
                                    out.setdefault("facts", {})[k] = str(obj[k])[:200]
                    except json.JSONDecodeError:
                        pass
                out.update(kind="text", text=text, truncated=_size(p) > 60000)
            elif ext == ".xlsx":
                from openpyxl import load_workbook
                wb = load_workbook(p, read_only=True, data_only=True)
                sheets = []
                for ws in wb.worksheets[:12]:
                    rows = []
                    for r in ws.iter_rows(max_row=12, values_only=True):
                        rows.append(["" if v is None else str(v)[:60] for v in r[:12]])
                    sheets.append(dict(name=str(ws.title), rows=rows))
                wb.close()
                out.update(kind="workbook", sheets=sheets)
            elif ext in (".png", ".jpg", ".jpeg", ".gif"):
                out.update(kind="image")
            elif ext == PACKAGE_EXT:
                out.update(kind="package", package=self.inspect_package(p, hash_files=False))
            else:
                out.update(kind="none")
        except Exception as exc:                       # a damaged file must not break the file manager
            out.update(kind="error", message=f"This file could not be read ({type(exc).__name__}).")
        return out

    # operations ----------------------------------------------------------------------------------------------
    def make_folder(self, parent, name):
        folder = self.resolve(parent)
        if not folder.is_dir():
            raise LibraryError("Choose a folder to create the new folder in.")
        if self.read_manifest(folder):
            raise LibraryError("A saved bundle cannot contain other folders; choose an ordinary folder.")
        p = unique_path(folder / safe_name(name))
        p.mkdir()
        rec = self.log("make_folder", path=self.rel(p))
        return dict(path=self.rel(p), log=rec["id"])

    def rename(self, rel, new_name):
        p = self.resolve(rel)
        if p == self.root:
            raise LibraryError("The library itself cannot be renamed here; use 'Move the library'.")
        if p.parent == self.root and p.name in STANDARD:
            raise LibraryError(f"'{p.name}' is a standard folder of the library and keeps its name.")
        new = safe_name(new_name)
        if new == p.name:
            return dict(path=self.rel(p), unchanged=True)
        if new.casefold() != p.name.casefold() and _taken(p.parent, new):
            raise LibraryError(f"'{new}' already exists here.")
        q = p.with_name(new)
        p.rename(q)
        rec = self.log("rename", moves=[[self.rel(q), rel]], **{"from": rel, "to": self.rel(q)})
        return dict(path=self.rel(q), log=rec["id"])

    def plan_transfer(self, rels, dest, copy=False):
        """Dry run of moving (or copying) items into a folder: where each would go, and any problems."""
        target = self.resolve(dest)
        problems, steps, planned = [], [], []
        if not target.is_dir():
            problems.append("The destination is not a folder.")
        elif self.read_manifest(target):
            problems.append("The destination is a saved bundle; choose an ordinary folder.")
        for r in dict.fromkeys(rels):
            try:
                src = self.resolve(r)
            except LibraryError as exc:
                problems.append(f"{r}: {exc}"); continue
            if not src.exists():
                problems.append(f"{r}: not found."); continue
            if src == self.root or (src.parent == self.root and src.name in STANDARD and not copy):
                problems.append(f"{r}: the standard folders stay where they are."); continue
            if target.is_dir() and (target == src or src in target.parents):
                problems.append(f"{r}: a folder cannot be moved or copied into itself."); continue
            if not copy and target.is_dir() and src.parent == target:
                problems.append(f"{r}: already in that folder."); continue
            dst = unique_path(target / src.name, also=planned) if target.is_dir() else target / src.name
            planned.append(dst.name)
            steps.append(dict(source=self.rel(src), target=(self.rel(target) + "/" if target != self.root else "") + dst.name,
                              renamed=dst.name != src.name, bytes=folder_stats(src)[1] if src.is_dir() else _size(src)))
        return dict(op="copy" if copy else "move", destination=dest, steps=steps, problems=problems,
                    can_apply=bool(steps) and not problems)

    def _run_steps(self, op, steps, do, **detail):
        """Apply steps one by one; log what was done even if a step fails (review finding 5)."""
        done = []
        try:
            for s in steps:
                do(s)
                done.append([s["target"], s["source"]])
        except Exception as exc:                          # noqa: BLE001
            if done:
                self.log(op, moves=done, partial=True, error=str(exc)[:300], **detail)
            raise LibraryError(f"Stopped after {len(done)} of {len(steps)} item(s): {exc}. "
                               + ("What was done can be undone." if done else "Nothing was changed."))
        return self.log(op, moves=done, **detail)

    def transfer(self, rels, dest, copy=False, apply=False):
        plan = self.plan_transfer(rels, dest, copy)
        if not apply or not plan["can_apply"]:
            return dict(plan, applied=False)
        verify = []
        def do(s):
            src = self.resolve(s["source"])
            dst = self.root / s["target"]
            if _taken(dst.parent, dst.name):              # appeared since the plan
                raise OSError(f"'{s['target']}' now exists")
            if copy:
                _copy_tree(src, dst)
                chk = self.check_item(dst, full=True) if dst.is_dir() else None
                if chk and chk["status"] != "ok":
                    verify.append(s["target"])
            else:
                shutil.move(str(src), str(dst))
        rec = self._run_steps("copy" if copy else "move", plan["steps"], do, destination=dest)
        return dict(plan, applied=True, log=rec["id"], verification_failed=verify)

    # Trash: each item goes in its own folder inside a batch, with a batch index (review finding 2)
    def _trash_batch(self):
        b = self.root / INTERNAL / "trash" / f"{now_stamp()}-{uuid.uuid4().hex[:6]}"
        b.mkdir(parents=True)
        return b

    def _read_index(self, batch: Path):
        try:
            d = json.loads((batch / TRASH_INDEX).read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_index(self, batch: Path, idx):
        (batch / TRASH_INDEX).write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")

    def _to_trash(self, p: Path, batch: Path):
        slot = batch / uuid.uuid4().hex[:10]
        slot.mkdir()
        origin = self.rel(p)
        shutil.move(str(p), str(slot / p.name))
        idx = self._read_index(batch)
        idx[slot.name] = dict(name=p.name, origin=origin, trashed=now_iso())
        self._write_index(batch, idx)
        return self.rel(slot / p.name), origin

    def trash(self, rels, apply=False):
        items, problems = [], []
        for r in dict.fromkeys(rels):
            try:
                p = self.resolve(r)
            except LibraryError as exc:
                problems.append(f"{r}: {exc}"); continue
            if not p.exists():
                problems.append(f"{r}: not found."); continue
            if p == self.root or (p.parent == self.root and p.name in STANDARD):
                problems.append(f"{r}: the standard folders cannot be deleted."); continue
            items.append(p)
        items = [p for p in items if not any(q in p.parents for q in items)]      # a folder and something inside it
        plan = dict(op="trash", steps=[dict(source=self.rel(p)) for p in items], problems=problems, can_apply=bool(items) and not problems)
        if not apply or not plan["can_apply"]:
            return dict(plan, applied=False)
        batch = self._trash_batch()
        steps = [dict(source=self.rel(p)) for p in items]
        def do(s):
            now_, _ = self._to_trash(self.resolve(s["source"]), batch)
            s["target"] = now_
        rec = self._run_steps("trash", steps, do)
        return dict(plan, applied=True, log=rec["id"])

    def trash_list(self):
        base = self.root / INTERNAL / "trash"
        out = []
        if not base.exists():
            return out
        for batch in sorted((b for b in base.iterdir() if b.is_dir()), reverse=True):
            idx = self._read_index(batch)
            for slot in sorted(x for x in batch.iterdir() if x.is_dir()):
                meta = idx.get(slot.name, {})
                for p in slot.iterdir():
                    n, total = folder_stats(p) if p.is_dir() else (1, _size(p))
                    out.append(dict(rel=self.rel(p), name=p.name, origin=meta.get("origin"), trashed=meta.get("trashed"), files=n, bytes=total))
        return out

    def _trash_item(self, rel):
        """A path that is exactly an item in the Trash: .jaf/trash/<batch>/<slot>/<name> (review finding 7)."""
        p = self.resolve(rel, allow_internal=True)
        parts = Path(self.rel(p)).parts
        if len(parts) != 5 or parts[0] != INTERNAL or parts[1] != "trash" or not p.exists():
            raise LibraryError(f"{rel}: not an item in the Trash.")
        return p

    def restore(self, trash_rels):
        steps, problems = [], []
        for r in dict.fromkeys(trash_rels):
            try:
                p = self._trash_item(r)
            except LibraryError as exc:
                problems.append(str(exc)); continue
            meta = self._read_index(p.parent.parent).get(p.parent.name, {})
            try:
                origin = self.resolve(meta["origin"])
            except Exception:                            # noqa: BLE001
                origin = self.root / "Imports" / p.name
            steps.append(dict(source=r, origin=origin))
        def do(s):
            origin = s["origin"]
            origin.parent.mkdir(parents=True, exist_ok=True)
            dst = unique_path(origin)
            src = self.resolve(s["source"], allow_internal=True)
            shutil.move(str(src), str(dst))
            slot = src.parent
            if slot.exists() and not any(slot.iterdir()):
                slot.rmdir()
            s["target"] = self.rel(dst)
        rec = self._run_steps("restore", steps, do) if steps else None
        return dict(restored=[s["target"] for s in steps if "target" in s], problems=problems, log=rec["id"] if rec else None)

    def empty_trash(self, apply=False):
        items = self.trash_list()
        n = sum(i["files"] for i in items); size = sum(i["bytes"] for i in items)
        if not apply:
            return dict(applied=False, items=len(items), files=n, bytes=size,
                        note="Emptying the Trash deletes these permanently. This cannot be undone.")
        base = self.root / INTERNAL / "trash"
        failed = []
        for b in list(base.iterdir()):
            try:
                shutil.rmtree(b) if b.is_dir() else b.unlink()
            except OSError:
                failed.append(b.name)
        left = self.trash_list()
        deleted = len(items) - len(left)
        self.log("empty_trash", items=deleted, files=n - sum(i["files"] for i in left), left=len(left))
        return dict(applied=True, items=deleted, files=n - sum(i["files"] for i in left), bytes=size - sum(i["bytes"] for i in left),
                    left=len(left), note=("Some items could not be deleted (perhaps open in another program) and remain in the Trash."
                                          if left else ""))

    def undo(self):
        r = self.last_undoable()
        if r is None:
            return dict(undone=False, note="There is nothing to undo.")
        problems = []
        if r["op"] == "make_folder":
            p = self.root / r["path"]
            if p.exists() and not any(p.iterdir()):
                p.rmdir()
            else:
                problems.append("The folder is no longer empty, so it was left in place.")
        elif r["op"] == "copy":                           # the copies go to the Trash (not itself undoable)
            batch = self._trash_batch()
            for now_, _ in r["moves"]:
                try:
                    p = self.resolve(now_)
                    if p.exists():
                        self._to_trash(p, batch)
                except (LibraryError, OSError) as exc:
                    problems.append(str(exc))
        else:                                             # move, rename, trash: move each back
            for now_, before in reversed(r["moves"]):
                try:
                    a = self.resolve(now_, allow_internal=True)
                    b = self.resolve(before)
                except LibraryError as exc:
                    problems.append(str(exc)); continue
                if not a.exists():
                    problems.append(f"{now_} is no longer there."); continue
                if b.exists():
                    problems.append(f"{before} is occupied; {now_} was left where it is."); continue
                b.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(a), str(b))
                slot = a.parent
                if r["op"] == "trash" and slot.exists() and not any(slot.iterdir()):
                    slot.rmdir()
        self.log("undo", undoes=r["id"], undone_op=r["op"], problems=problems)
        return dict(undone=True, op=r["op"], problems=problems)

    def verify(self, rel=""):
        """Full SHA-256 check of every bundle under a folder (or of one bundle)."""
        start = self.resolve(rel)
        out = []
        if self.read_manifest(start):
            cands = [start]
        else:
            cands = sorted({p.parent for p in walk_files(start) if p.name == MANIFEST
                            and INTERNAL not in p.relative_to(self.root).parts})
        for folder in cands:
            res = self.check_item(folder, full=True)
            if res:
                out.append(dict(item=self.rel(folder), **res))
        self.log("verify", scope=rel or "(library)", checked=len(out), problems=sum(r["status"] != "ok" for r in out))
        return dict(items=out, ok=sum(r["status"] == "ok" for r in out), problems=sum(r["status"] != "ok" for r in out))

    # saving and importing ------------------------------------------------------------------------------------------
    def new_export(self, kind: str) -> Path:
        d = unique_path(self.root / "Exports" / f"{kind}_{now_stamp()}")
        d.mkdir(parents=True)
        return d

    def finish_export(self, folder: Path, kind: str, title: str, **meta):
        man = self.write_manifest(folder, kind, title, source="saved by the program", **meta)
        self.log("save", path=self.rel(folder), kind=kind, files=len(man["files"]))
        return man

    def record_import(self, name: str, data: bytes, kind: str = "file", note: str = ""):
        """Keep a copy of a file that was loaded or imported, with its hash, in Imports/."""
        d = unique_path(self.root / "Imports" / f"{now_stamp()}_{safe_name(Path(name).stem, 60)}")
        d.mkdir(parents=True)
        f = d / safe_name(name)
        f.write_bytes(data)
        man = self.write_manifest(d, kind, title=name, source="imported", original_name=name, note=note)
        self.log("import", path=self.rel(d), kind=kind, original_name=name, sha256=man["files"][0]["sha256"])
        return dict(path=self.rel(d), file=self.rel(f), sha256=man["files"][0]["sha256"])

    # packages for another device ------------------------------------------------------------------------------------
    def make_package(self, rels, name=""):
        """A single .jafpack file holding the chosen items, with the SHA-256 of every file, saved in Packages/.
        Each item has its own numbered place in the archive, so items with the same name stay apart (review
        finding 3); the package is written outside the library first, so it never contains itself (finding 8)."""
        items = []
        for r in dict.fromkeys(rels):
            p = self.resolve(r)
            if not p.exists():
                raise LibraryError(f"{r}: not found.")
            if p == self.root:
                raise LibraryError("Choose items or folders, not the whole library (use 'Move the library' for that).")
            items.append(p)
        if not items:
            raise LibraryError("Choose at least one item to package.")
        items = [p for p in items if not any(q in p.parents for q in items)]
        title = safe_name(name or (items[0].name if len(items) == 1 else f"JAF package {now_stamp()}"))
        tmp = self.root / INTERNAL / "tmp" / f"{uuid.uuid4().hex}{PACKAGE_EXT}"
        files, index_items = [], []
        try:
            with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as z:
                for i, p in enumerate(items, 1):
                    prefix = f"items/{i:03d}"
                    index_items.append(dict(n=i, name=p.name, type="folder" if p.is_dir() else "file"))
                    srcs = [p] if p.is_file() else sorted(walk_files(p))
                    for f in srcs:
                        sub = p.name if p.is_file() else f"{p.name}/{f.relative_to(p).as_posix()}"
                        z.write(f, f"{prefix}/{sub}")
                        files.append(dict(path=f"{i:03d}/{sub}", bytes=_size(f), sha256=sha256_file(f)))
                index = dict(format="JAF Rule Bench package 2", title=title, created=now_iso(), tool_version=VERSION,
                             items=index_items, files=files)
                z.writestr(PACKAGE_INDEX, json.dumps(index, indent=1, ensure_ascii=False))
            out = unique_path(self.root / "Packages" / f"{title}{PACKAGE_EXT}")
            shutil.move(str(tmp), str(out))
        finally:
            if tmp.exists():
                tmp.unlink()
        digest = sha256_file(out)
        self.log("package", path=self.rel(out), items=[self.rel(p) for p in items], files=len(files), sha256=digest)
        return dict(path=self.rel(out), files=len(files), bytes=_size(out), sha256=digest)

    @staticmethod
    def _zip_hash(z, name, chunk=1 << 20):
        h = hashlib.sha256()
        with z.open(name) as fh:
            for b in iter(lambda: fh.read(chunk), b""):
                h.update(b)
        return h.hexdigest()

    @staticmethod
    def _target_parts(path: str):
        """Where a package entry would land, after names are made safe."""
        return [safe_name(x) for x in PurePosixPath(path).parts]

    def inspect_package(self, src, hash_files=True):
        """Read and check a package without extracting it. src: bytes, a path, or a file object.
        Raises LibraryError if it is unsafe or not a package."""
        import io as _io
        fobj = _io.BytesIO(src) if isinstance(src, (bytes, bytearray)) else src
        try:
            z = zipfile.ZipFile(fobj)
        except (zipfile.BadZipFile, OSError):
            raise LibraryError("This is not a JAF Rule Bench package (.jafpack).")
        with z:
            infos = z.infolist()
            names = [i.filename for i in infos]
            if PACKAGE_INDEX not in names:
                raise LibraryError("This is not a JAF Rule Bench package (it has no package.json).")
            if len(infos) > MAX_PACKAGE_FILES or sum(i.file_size for i in infos) > MAX_PACKAGE_BYTES:
                raise LibraryError("The package is too large to import safely.")
            for i in infos:
                n = i.filename
                if n.startswith("/") or "\\" in n or re.match(r"^[A-Za-z]:", n) or ".." in PurePosixPath(n).parts:
                    raise LibraryError("The package contains an unsafe path and was not opened.")
                if (i.external_attr >> 16) & 0o170000 == 0o120000:
                    raise LibraryError("The package contains a link and was not opened.")
            try:
                index = json.loads(z.read(PACKAGE_INDEX).decode("utf-8"))
                assert isinstance(index, dict) and isinstance(index.get("files", []), list)
            except Exception:                              # noqa: BLE001
                raise LibraryError("The package's index could not be read.")
            problems = []
            listed = {}
            for f in index.get("files", []):
                if isinstance(f, dict) and isinstance(f.get("path"), str):
                    if f["path"] in listed:
                        problems.append(f"listed twice: {f['path']}")
                    listed[f["path"]] = f
            members = [n for n in names if n.startswith("items/") and not n.endswith("/")]
            if len(members) != len(set(members)):
                problems.append("the package holds two entries with the same name")
            present = {n[len("items/"):] for n in members}
            seen = {}
            for path in present:                            # names that would clash once made safe (finding 3)
                key = "/".join(self._target_parts(path)).casefold()
                if key in seen:
                    problems.append(f"names clash when unpacked: {seen[key]} and {path}")
                seen[key] = path
            for path, f in listed.items():
                if path not in present:
                    problems.append(f"missing: {path}")
                elif hash_files and self._zip_hash(z, "items/" + path) != f.get("sha256"):
                    problems.append(f"changed or damaged: {path}")
            for path in sorted(present - set(listed)):
                problems.append(f"not listed in the index: {path}")
        title = str(index.get("title") or "")[:120]
        items = [str(x.get("name") if isinstance(x, dict) else x)[:120] for x in index.get("items", [])][:200]
        return dict(title=title, created=str(index.get("created") or "")[:40], tool_version=str(index.get("tool_version") or "")[:20],
                    items=items, files=len(listed), bytes=sum(int(f.get("bytes") or 0) for f in listed.values()),
                    problems=problems, intact=not problems, hashes_checked=hash_files)

    def import_package(self, src, name="package.jafpack", apply=False):
        info = self.inspect_package(src)
        if not apply or not info["intact"]:
            return dict(info, applied=False,
                        note=("Checked only: nothing imported." if info["intact"] else
                              "The package failed its checks, so nothing was imported: " + "; ".join(info["problems"][:6])))
        import io as _io
        fobj = _io.BytesIO(src) if isinstance(src, (bytes, bytearray)) else src
        stage = self.root / INTERNAL / "tmp" / f"import-{uuid.uuid4().hex}"
        stage.mkdir(parents=True)
        try:
            with zipfile.ZipFile(fobj) as z:
                index = json.loads(z.read(PACKAGE_INDEX).decode("utf-8"))
                listed = {f["path"]: f for f in index.get("files", [])}
                members = sorted(n for n in z.namelist() if n.startswith("items/") and not n.endswith("/"))
                tops, taken = {}, []                         # item number -> name it is unpacked under
                for n in members:
                    parts = self._target_parts(n[len("items/"):])
                    if len(parts) > 1 and re.fullmatch(r"\d{3}", parts[0]) and parts[0] not in tops:
                        tops[parts[0]] = unique_path(stage / parts[1], also=taken).name
                        taken.append(tops[parts[0]])
                for n in members:
                    parts = self._target_parts(n[len("items/"):])
                    if len(parts) > 1 and re.fullmatch(r"\d{3}", parts[0]):
                        parts = [tops[parts[0]]] + parts[2:]  # items with the same name are kept apart: 'x', 'x (2)'
                    out = stage.joinpath(*parts)
                    if out.exists():
                        raise LibraryError(f"Two entries would be unpacked to the same place ({'/'.join(parts)}).")
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(n) as fi, open(out, "wb") as fo:
                        shutil.copyfileobj(fi, fo, 1 << 20)
                    want = listed.get(n[len("items/"):], {}).get("sha256")
                    if want and sha256_file(out) != want:   # check after unpacking too
                        raise LibraryError(f"{'/'.join(parts)} differs from the package's record after unpacking.")
            dest = unique_path(self.root / "Imports" / safe_name(f"{now_stamp()}_{info['title'] or Path(name).stem}", 90))
            shutil.move(str(stage), str(dest))
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        bad = [self.rel(m.parent) for m in walk_files(dest) if m.name == MANIFEST
               and (lambda r: r and r["status"] != "ok")(self.check_item(m.parent, full=True))]
        h = hashlib.sha256(src).hexdigest() if isinstance(src, (bytes, bytearray)) else None
        self.log("import_package", path=self.rel(dest), title=info["title"], files=info["files"], sha256=h,
                 created=info["created"], from_version=info["tool_version"])
        return dict(info, applied=True, path=self.rel(dest), bundle_problems=bad)


# ---- moving or adopting the whole library -------------------------------------------------------------------------
def plan_move_library(root: Path, target: str):
    root = Path(root).resolve()
    dst = Path(target).expanduser()
    problems, warnings = [], []
    if not str(target).strip() or not dst.is_absolute():
        problems.append("Give the full path of the new location (for example D:\\Research\\JAF Rule Bench).")
    dst = dst.resolve() if dst.is_absolute() else dst
    if dst == root:
        problems.append("That is the current library.")
    if root in dst.parents:
        problems.append("The new location is inside the current library.")
    if dst in root.parents:
        problems.append("The current library is inside the new location.")
    if dst.exists() and (not dst.is_dir() or any(dst.iterdir())):
        problems.append("The new location must be an empty folder, or a folder that does not exist yet.")
    partial = dst.with_name(dst.name + ".partial") if dst.name else None
    if partial is not None and partial.exists():
        warnings.append(f"An unfinished copy from an earlier attempt is at {partial}; it will be replaced.")
    probe = dst
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    if not probe.exists():
        problems.append("The drive for the new location is not available.")
    n, size = folder_stats(root)
    total = size + folder_stats(root / INTERNAL)[1]
    try:
        free = shutil.disk_usage(probe).free
    except OSError:
        free = None
    same = same_device(root, probe)
    if free is not None and not same and free < total * 1.05:
        problems.append(f"Not enough free space: {total / 1e6:,.1f} MB needed, {free / 1e6:,.1f} MB free.")
    if any(s in str(dst).lower() for s in SYNCED):
        warnings.append("The new location is in a synced folder (such as OneDrive or Dropbox). That works, "
                        "but files may be held as online-only placeholders; keep them available offline.")
    return dict(source=str(root), target=str(dst), files=n, bytes=total, free_bytes=free,
                method="rename (same drive)" if same else "copy, then verify", problems=problems, warnings=warnings,
                can_apply=not problems)


def move_library(root: Path, target: str, apply=False):
    """Without apply, the dry run. With it: rename on the same drive, or copy every file into '<target>.partial',
    verify each by SHA-256, and only then rename it to the target (review finding 9). The caller switches the
    setting. After a copy the old folder is left untouched."""
    plan = plan_move_library(root, target)
    if not apply or not plan["can_apply"]:
        return dict(plan, applied=False)
    src, dst = Path(plan["source"]), Path(plan["target"])
    method = "rename"
    try:
        if not plan["method"].startswith("rename"):
            raise OSError("different drive")
        if dst.exists():
            dst.rmdir()
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src, dst)
    except OSError:
        method = "copy"
        partial = dst.with_name(dst.name + ".partial")
        if partial.exists():
            shutil.rmtree(partial)
        bad, skipped = [], []
        try:
            partial.mkdir(parents=True)
            for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
                d = Path(dirpath)
                for n in list(dirnames):
                    if is_link(d / n):
                        skipped.append((d / n).relative_to(src).as_posix()); dirnames.remove(n)
                for n in filenames:
                    p = d / n
                    if is_link(p):
                        skipped.append(p.relative_to(src).as_posix()); continue
                    q = partial / p.relative_to(src)
                    q.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, q)
                    if sha256_file(p) != sha256_file(q):
                        bad.append(p.relative_to(src).as_posix())
            if bad:
                raise OSError(f"{len(bad)} copied file(s) differ from their originals")
            if dst.exists():
                dst.rmdir()
            os.replace(partial, dst)
        except OSError as exc:
            shutil.rmtree(partial, ignore_errors=True)
            return dict(plan, applied=False, method=method, copy_problems=bad,
                        note=f"The copy failed ({exc}); the library was not switched, the unfinished copy was removed, "
                             "and the old folder is unchanged.")
    lib = Library(dst)
    lib.log("move_library", **{"from": str(src), "to": str(dst), "method": method})
    note = ("Moved by renaming." if method == "rename" else
            "Copied and verified. The old folder is untouched: delete it yourself once you have checked the new one.")
    return dict(plan, applied=True, method=method, note=note)


def plan_adopt(folder: str):
    """Check a folder before using it as the library: it must already be a library (it has the program's
    '.jaf' folder) and every saved result in it is checked. Nothing is switched or created (review finding 1)."""
    p = Path(folder).expanduser()
    if not str(folder).strip() or not p.is_absolute() or not p.is_dir():
        raise LibraryError("Give the full path of an existing folder.")
    if not (p / INTERNAL).is_dir() or is_link(p / INTERNAL):
        raise LibraryError("That folder is not a JAF Rule Bench library (it has no '.jaf' folder). "
                           "To start a new library there, use 'Move the library' instead.")
    lib = Library(p, create=False)
    res = lib.verify("")
    n, size = folder_stats(lib.root)
    return dict(folder=str(lib.root), files=n, bytes=size, bundles=len(res["items"]), problems=res["problems"],
                damaged=[r["item"] for r in res["items"] if r["status"] != "ok"])


def adopt_library(folder: str):
    res = plan_adopt(folder)
    Library(res["folder"], create=False).log("adopt_library", folder=res["folder"], bundles=res["bundles"], problems=res["problems"])
    return res
