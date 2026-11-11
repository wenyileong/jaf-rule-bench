# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Wen Yi LEONG
"""The file library: every export and import in one folder, shown, checked and moved safely.

Modelled on the A-share Company Intelligence data folder (its ``files`` and ``datafolder`` modules), with the same
principles:

* **preview first** - every operation that changes files has a dry run that changes nothing;
* **nothing is lost** - deleting moves to the library's Trash, which only an explicit "empty" clears; moving the
  library copies and verifies before switching, and leaves the old folder untouched;
* **checked** - each saved bundle carries a manifest with the SHA-256 of every file, so changes, damage and
  incomplete copies are detected; packages for another device carry the same and are verified on import;
* **recorded** - every operation is logged in the library (``.jaf/log.jsonl``), and the last one can be undone.

Layout of the library (default: Documents/JAF Rule Bench)::

    Exports/     results, coded-world and estimation bundles saved by the program
    Imports/     a copy of every workbook or record loaded, and every package imported
    Packages/    packages made for another device (.jafpack)
    <any folders the user creates>
    .jaf/        the log, the Trash and the undo records (not shown as an ordinary folder)

Nothing here sends anything over the network.
"""
from __future__ import annotations

import datetime
import hashlib
import io
import json
import os
import re
import shutil
import zipfile
from pathlib import Path, PurePosixPath

from .params import VERSION

MANIFEST = "manifest.json"
PACKAGE_INDEX = "package.json"
PACKAGE_EXT = ".jafpack"
INTERNAL = ".jaf"
STANDARD = ("Exports", "Imports", "Packages")
MAX_PACKAGE_BYTES = 2 * 1024 ** 3          # uncompressed size accepted from a package
MAX_PACKAGE_FILES = 20000
_BAD = re.compile(r'[\\/:*?"<>|\r\n\t\x00]+')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
SYNCED = ("onedrive", "dropbox", "google drive", "googledrive", "icloud", "box sync")


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
    if not t or t.split(".")[0].upper() in _RESERVED:
        t = "untitled" if not t else "_" + t
    return t


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
        for p in folder.rglob("*"):
            if p.is_file() and INTERNAL not in p.relative_to(folder).parts:
                n += 1
                total += _size(p)
    return n, total


def unique_path(p: Path) -> Path:
    """p, or 'name (2).ext', 'name (3).ext' ... if p exists."""
    if not p.exists():
        return p
    stem, suf = (p.stem, p.suffix) if p.is_file() or p.suffix else (p.name, "")
    i = 2
    while True:
        q = p.with_name(f"{stem} ({i}){suf}")
        if not q.exists():
            return q
        i += 1


def same_device(a: Path, b: Path) -> bool:
    try:
        tb = b if b.exists() else b.parent
        while not tb.exists() and tb != tb.parent:
            tb = tb.parent
        return os.stat(a).st_dev == os.stat(tb).st_dev
    except OSError:
        return False


# ---- the library -----------------------------------------------------------------------------------------
class Library:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for s in STANDARD:
            (self.root / s).mkdir(exist_ok=True)
        (self.root / INTERNAL / "trash").mkdir(parents=True, exist_ok=True)

    # paths -------------------------------------------------------------------------------------------
    def resolve(self, rel: str | None, allow_internal=False) -> Path:
        """The absolute path of a library-relative path, refusing anything outside the library."""
        rel = (rel or "").replace("\\", "/")
        if rel.startswith("/") or re.match(r"^[A-Za-z]:", rel) or rel.startswith("~"):
            raise LibraryError("Paths must be inside the library.")
        rel = rel.strip("/")
        parts = [x for x in rel.split("/") if x not in ("", ".")]
        if any(x == ".." for x in parts):
            raise LibraryError("Paths must be inside the library.")
        if parts and parts[0] == INTERNAL and not allow_internal:
            raise LibraryError("That folder belongs to the program.")
        p = (self.root.joinpath(*parts)).resolve()
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
        rec = dict(id=f"{now_stamp()}-{os.urandom(3).hex()}", time=now_iso(), op=op, version=VERSION, **detail)
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
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        undone = {r.get("undoes") for r in rows if r.get("op") == "undo"}
        for r in rows:
            r["undone"] = r["id"] in undone
        return rows[-limit:][::-1]

    def last_undoable(self):
        for r in self.history(1000):
            if r["op"] in ("move", "copy", "rename", "trash", "make_folder") and not r["undone"]:
                return r
            if r["op"] in ("empty_trash", "move_library", "adopt_library"):
                return None                      # not undoable, and older operations may no longer be valid
        return None

    # manifests ---------------------------------------------------------------------------------------
    def write_manifest(self, folder: Path, kind: str, title: str = "", **meta):
        files = []
        for p in sorted(folder.rglob("*")):
            if p.is_file() and p.name != MANIFEST:
                files.append(dict(path=p.relative_to(folder).as_posix(), bytes=_size(p), sha256=sha256_file(p)))
        man = dict(format="JAF Rule Bench bundle 1", kind=kind, title=title or folder.name, created=now_iso(),
                   tool_version=VERSION, files=files, **meta)
        (folder / MANIFEST).write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
        return man

    @staticmethod
    def read_manifest(folder: Path):
        try:
            m = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
            return m if isinstance(m, dict) and isinstance(m.get("files"), list) else None
        except (OSError, json.JSONDecodeError):
            return None

    def check_item(self, folder: Path, full=False):
        """Integrity of a bundle against its manifest: ok, changed, missing files, extra files."""
        man = self.read_manifest(folder)
        if man is None:
            return None
        changed, missing = [], []
        listed = set()
        for f in man["files"]:
            p = folder / f["path"]
            listed.add(f["path"])
            if not p.is_file():
                missing.append(f["path"])
            elif _size(p) != f.get("bytes") or (full and sha256_file(p) != f.get("sha256")):
                changed.append(f["path"])
        extra = [p.relative_to(folder).as_posix() for p in folder.rglob("*")
                 if p.is_file() and p.name != MANIFEST and p.relative_to(folder).as_posix() not in listed]
        status = "ok" if not (changed or missing) else ("missing" if missing else "changed")
        return dict(status=status, checked="full" if full else "sizes", changed=changed, missing=missing, extra=extra)

    # listing and preview -----------------------------------------------------------------------------------
    def entry(self, p: Path, check=True):
        is_dir = p.is_dir()
        st = p.stat()
        e = dict(name=p.name, rel=self.rel(p), type="folder" if is_dir else "file", modified=datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"))
        if is_dir:
            n, total = folder_stats(p)
            e.update(files=n, bytes=total)
            man = self.read_manifest(p)
            if man:
                e.update(kind=man.get("kind"), title=man.get("title"), created=man.get("created"), tool_version=man.get("tool_version"),
                         source=man.get("source"))
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
        entries = []
        for p in sorted(folder.iterdir(), key=lambda q: (not q.is_dir(), q.name.lower())):
            if p.name == INTERNAL or p.name == MANIFEST and self.read_manifest(folder):
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
        """All folders (for 'Move to'), excluding bundle contents and the program's own folder."""
        out = [""]
        def walk(p: Path, depth):
            if depth > max_depth:
                return
            for q in sorted((x for x in p.iterdir() if x.is_dir() and x.name != INTERNAL), key=lambda x: x.name.lower()):
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
                with open(p, encoding="utf-8-sig", newline="") as fh:
                    rows = [r for _, r in zip(range(max_rows + 1), csv.reader(fh))]
                out.update(kind="table", rows=rows, truncated=len(rows) > max_rows)
            elif ext in (".json", ".md", ".txt", ".cff", ".log", ".jsonl"):
                with open(p, encoding="utf-8", errors="replace") as fh:
                    text = fh.read(60000)
                if ext == ".json":
                    try:
                        obj = json.loads(text) if _size(p) <= 60000 else None
                        if isinstance(obj, dict):
                            out["keys"] = list(obj)[:40]
                            for k in ("version", "tool_version", "kind", "generated", "created", "fingerprint"):
                                if k in obj and not isinstance(obj[k], (dict, list)):
                                    out.setdefault("facts", {})[k] = obj[k]
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
                    sheets.append(dict(name=ws.title, rows=rows))
                wb.close()
                out.update(kind="workbook", sheets=sheets)
            elif ext in (".png", ".svg", ".jpg", ".jpeg", ".gif"):
                out.update(kind="image")
            elif ext == PACKAGE_EXT:
                out.update(kind="package", package=self.inspect_package(p.read_bytes()))
            else:
                out.update(kind="none")
        except Exception as exc:                       # a damaged file must not break the file manager
            out.update(kind="error", message=f"This file could not be read: {exc}")
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
        q = p.with_name(new)
        if q.exists():
            raise LibraryError(f"'{new}' already exists here.")
        p.rename(q)
        rec = self.log("rename", moves=[[self.rel(q), rel]], **{"from": rel, "to": self.rel(q)})
        return dict(path=self.rel(q), log=rec["id"])

    def plan_transfer(self, rels, dest, copy=False):
        """Dry run of moving (or copying) items into a folder: where each would go, and any problems."""
        target = self.resolve(dest)
        problems, steps = [], []
        if not target.is_dir():
            problems.append("The destination is not a folder.")
        elif self.read_manifest(target):
            problems.append("The destination is a saved bundle; choose an ordinary folder.")
        planned = set()
        for r in rels:
            try:
                src = self.resolve(r)
            except LibraryError as exc:
                problems.append(f"{r}: {exc}"); continue
            if not src.exists():
                problems.append(f"{r}: not found."); continue
            if src == self.root or (src.parent == self.root and src.name in STANDARD and not copy):
                problems.append(f"{r}: the standard folders stay where they are."); continue
            if target.is_dir() and (target == src or src in target.parents):
                problems.append(f"{r}: a folder cannot be moved into itself."); continue
            if not copy and target.is_dir() and src.parent == target:
                problems.append(f"{r}: already in that folder."); continue
            dst = target / src.name
            while dst.exists() or str(dst) in planned:
                dst = unique_path(dst) if not str(unique_path(dst)) in planned else dst.with_name(dst.name + " (copy)")
            planned.add(str(dst))
            steps.append(dict(source=self.rel(src), target=self.rel(dst) if target.is_dir() else str(dst),
                              renamed=dst.name != src.name, bytes=folder_stats(src)[1] if src.is_dir() else _size(src)))
        return dict(op="copy" if copy else "move", destination=dest, steps=steps, problems=problems,
                    can_apply=bool(steps) and not problems)

    def transfer(self, rels, dest, copy=False, apply=False):
        plan = self.plan_transfer(rels, dest, copy)
        if not apply or not plan["can_apply"]:
            return dict(plan, applied=False)
        done, verify = [], []
        for s in plan["steps"]:
            src, dst = self.resolve(s["source"]), self.resolve(s["target"])
            if copy:
                shutil.copytree(src, dst) if src.is_dir() else shutil.copy2(src, dst)
                chk = self.check_item(dst, full=True) if dst.is_dir() else None
                if chk and chk["status"] != "ok":
                    verify.append(s["target"])
            else:
                shutil.move(str(src), str(dst))
            done.append([s["target"], s["source"]])
        rec = self.log("copy" if copy else "move", moves=done, destination=dest)
        return dict(plan, applied=True, log=rec["id"], verification_failed=verify)

    def trash(self, rels, apply=False):
        items, problems = [], []
        for r in rels:
            try:
                p = self.resolve(r)
            except LibraryError as exc:
                problems.append(f"{r}: {exc}"); continue
            if not p.exists():
                problems.append(f"{r}: not found."); continue
            if p == self.root or (p.parent == self.root and p.name in STANDARD):
                problems.append(f"{r}: the standard folders cannot be deleted."); continue
            items.append(p)
        plan = dict(op="trash", steps=[dict(source=self.rel(p)) for p in items], problems=problems, can_apply=bool(items) and not problems)
        if not apply or not plan["can_apply"]:
            return dict(plan, applied=False)
        bin_ = self.root / INTERNAL / "trash" / now_stamp()
        bin_.mkdir(parents=True, exist_ok=True)
        moves = []
        for p in items:
            dst = unique_path(bin_ / p.name)
            origin = self.rel(p)
            shutil.move(str(p), str(dst))
            (dst.parent / (dst.name + ".origin.json")).write_text(json.dumps(dict(origin=origin, trashed=now_iso())), encoding="utf-8")
            moves.append([self.rel(dst), origin])
        rec = self.log("trash", moves=moves)
        return dict(plan, applied=True, log=rec["id"])

    def trash_list(self):
        base = self.root / INTERNAL / "trash"
        out = []
        if not base.exists():
            return out
        for batch in sorted(base.iterdir(), reverse=True):
            if not batch.is_dir():
                continue
            for p in sorted(batch.iterdir()):
                if p.name.endswith(".origin.json"):
                    continue
                try:
                    meta = json.loads((batch / (p.name + ".origin.json")).read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    meta = {}
                n, total = folder_stats(p) if p.is_dir() else (1, _size(p))
                out.append(dict(rel=self.rel(p), name=p.name, origin=meta.get("origin"), trashed=meta.get("trashed"), files=n, bytes=total))
        return out

    def restore(self, trash_rels):
        moves, problems = [], []
        for r in trash_rels:
            p = self.resolve(r, allow_internal=True)
            if INTERNAL not in Path(self.rel(p)).parts or not p.exists():
                problems.append(f"{r}: not in the Trash."); continue
            try:
                meta = json.loads((p.parent / (p.name + ".origin.json")).read_text(encoding="utf-8"))
                origin = self.resolve(meta["origin"])
            except Exception:                            # noqa: BLE001
                origin = self.root / "Imports" / p.name
            origin.parent.mkdir(parents=True, exist_ok=True)
            dst = unique_path(origin)
            shutil.move(str(p), str(dst))
            try:
                (p.parent / (p.name + ".origin.json")).unlink()
            except OSError:
                pass
            moves.append([self.rel(dst), r])
        rec = self.log("restore", moves=moves) if moves else None
        return dict(restored=[m[0] for m in moves], problems=problems, log=rec["id"] if rec else None)

    def empty_trash(self, apply=False):
        items = self.trash_list()
        n = sum(i["files"] for i in items); size = sum(i["bytes"] for i in items)
        if not apply:
            return dict(applied=False, items=len(items), files=n, bytes=size,
                        note="Emptying the Trash deletes these permanently. This cannot be undone.")
        shutil.rmtree(self.root / INTERNAL / "trash", ignore_errors=True)
        (self.root / INTERNAL / "trash").mkdir(parents=True, exist_ok=True)
        self.log("empty_trash", items=len(items), files=n, bytes=size)
        return dict(applied=True, items=len(items), files=n, bytes=size)

    def undo(self):
        r = self.last_undoable()
        if r is None:
            return dict(undone=False, note="There is nothing to undo.")
        problems = []
        if r["op"] == "make_folder":
            p = self.resolve(r["path"])
            if p.exists() and not any(p.iterdir()):
                p.rmdir()
            else:
                problems.append("The folder is no longer empty, so it was left in place.")
        elif r["op"] == "copy":                           # the copies go to the Trash
            res = self.trash([m[0] for m in r["moves"] if self.resolve(m[0]).exists()], apply=True)
            problems += res["problems"]
        else:                                             # move, rename, trash: move each back
            for now_, before in r["moves"]:
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
                meta = a.parent / (a.name + ".origin.json")
                if meta.exists():
                    meta.unlink()
        self.log("undo", undoes=r["id"], undone_op=r["op"], problems=problems)
        return dict(undone=True, op=r["op"], problems=problems)

    def verify(self, rel=""):
        """Full SHA-256 check of every bundle under a folder (or of one bundle)."""
        start = self.resolve(rel)
        out = []
        cands = [start] if self.read_manifest(start) else [p for p in start.rglob(MANIFEST) if INTERNAL not in p.relative_to(self.root).parts]
        for c in cands:
            folder = c if c.is_dir() else c.parent
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
        """A single .jafpack file holding the chosen items, with the SHA-256 of every file, saved in Packages/."""
        items = []
        for r in rels:
            p = self.resolve(r)
            if not p.exists():
                raise LibraryError(f"{r}: not found.")
            if p == self.root:
                raise LibraryError("Choose items or folders, not the whole library (use 'Move the library' for that).")
            items.append(p)
        if not items:
            raise LibraryError("Choose at least one item to package.")
        title = safe_name(name or (items[0].name if len(items) == 1 else f"JAF package {now_stamp()}"))
        out = unique_path(self.root / "Packages" / f"{title}{PACKAGE_EXT}")
        files = []
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for p in items:
                srcs = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file())
                for f in srcs:
                    arc = (PurePosixPath(p.name) / f.relative_to(p).as_posix()).as_posix() if p.is_dir() else p.name
                    z.write(f, "items/" + arc)
                    files.append(dict(path=arc, bytes=_size(f), sha256=sha256_file(f)))
            index = dict(format="JAF Rule Bench package 1", title=title, created=now_iso(), tool_version=VERSION,
                         items=[p.name for p in items], files=files)
            z.writestr(PACKAGE_INDEX, json.dumps(index, indent=1, ensure_ascii=False))
        digest = sha256_file(out)
        self.log("package", path=self.rel(out), items=[self.rel(p) for p in items], files=len(files), sha256=digest)
        return dict(path=self.rel(out), files=len(files), bytes=_size(out), sha256=digest)

    @staticmethod
    def inspect_package(data: bytes):
        """Read and check a package without extracting it. Raises LibraryError if it is unsafe or not a package."""
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            raise LibraryError("This is not a JAF Rule Bench package (.jafpack).")
        with z:
            names = z.namelist()
            if PACKAGE_INDEX not in names:
                raise LibraryError("This is not a JAF Rule Bench package (it has no package.json).")
            infos = z.infolist()
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
            except Exception:                              # noqa: BLE001
                raise LibraryError("The package's index could not be read.")
            problems = []
            listed = {f["path"]: f for f in index.get("files", [])}
            present = {n[len("items/"):] for n in names if n.startswith("items/") and not n.endswith("/")}
            for path, f in listed.items():
                if path not in present:
                    problems.append(f"missing: {path}"); continue
                if hashlib.sha256(z.read("items/" + path)).hexdigest() != f.get("sha256"):
                    problems.append(f"changed or damaged: {path}")
            for path in sorted(present - set(listed)):
                problems.append(f"not listed in the index: {path}")
        return dict(title=index.get("title"), created=index.get("created"), tool_version=index.get("tool_version"),
                    items=index.get("items", []), files=len(listed), bytes=sum(f.get("bytes", 0) for f in listed.values()),
                    problems=problems, intact=not problems)

    def import_package(self, data: bytes, name="package.jafpack", apply=False):
        info = self.inspect_package(data)
        if not apply or not info["intact"]:
            return dict(info, applied=False,
                        note=("Checked only: nothing imported." if info["intact"] else
                              "The package failed its checks, so nothing was imported: " + "; ".join(info["problems"][:6])))
        dest = unique_path(self.root / "Imports" / safe_name(f"{now_stamp()}_{info['title'] or Path(name).stem}", 90))
        dest.mkdir(parents=True)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for n in z.namelist():
                if not n.startswith("items/") or n.endswith("/"):
                    continue
                parts = [safe_name(x) for x in PurePosixPath(n[len("items/"):]).parts]
                out = dest.joinpath(*parts)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(z.read(n))
        bad = []
        for m in dest.rglob(MANIFEST):                     # bundles inside keep their own manifests: check them
            r = self.check_item(m.parent, full=True)
            if r and r["status"] != "ok":
                bad.append(self.rel(m.parent))
        self.log("import_package", path=self.rel(dest), title=info["title"], files=info["files"],
                 sha256=hashlib.sha256(data).hexdigest(), created=info["created"], from_version=info["tool_version"])
        return dict(info, applied=True, path=self.rel(dest), bundle_problems=bad)


# ---- moving or adopting the whole library -------------------------------------------------------------------------
def plan_move_library(root: Path, target: str):
    root = Path(root).resolve()
    dst = Path(target).expanduser()
    problems, warnings = [], []
    if not dst.is_absolute():
        problems.append("Give the full path of the new location (for example D:\\Research\\JAF Rule Bench).")
        dst = dst.resolve()
    else:
        dst = dst.resolve()
    if dst == root:
        problems.append("That is the current library.")
    if root in dst.parents:
        problems.append("The new location is inside the current library.")
    if dst in root.parents:
        problems.append("The current library is inside the new location.")
    if dst.exists() and (not dst.is_dir() or any(dst.iterdir())):
        problems.append("The new location must be an empty folder, or a folder that does not exist yet.")
    n, size = folder_stats(root)
    internal = folder_stats(root / INTERNAL)
    probe = dst
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        free = shutil.disk_usage(probe).free
    except OSError:
        free = None
    same = same_device(root, probe)
    total = size + internal[1]
    if free is not None and not same and free < total * 1.05:
        problems.append(f"Not enough free space: {total / 1e6:,.1f} MB needed, {free / 1e6:,.1f} MB free.")
    low = str(dst).lower()
    if any(s in low for s in SYNCED):
        warnings.append("The new location is in a synced folder (such as OneDrive or Dropbox). That works for exports, "
                        "but files may be held as online-only placeholders; keep them available offline.")
    return dict(source=str(root), target=str(dst), files=n, bytes=total, free_bytes=free,
                method="rename (same drive)" if same else "copy, then verify", problems=problems, warnings=warnings,
                can_apply=not problems)


def move_library(root: Path, target: str, apply=False):
    """Without apply, the dry run. With it: rename on the same drive, or copy every file and verify each by
    SHA-256; the caller then switches the setting. After a copy the old folder is left untouched."""
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
        dst.mkdir(parents=True, exist_ok=True)
        bad = []
        for p in src.rglob("*"):
            q = dst / p.relative_to(src)
            if p.is_dir():
                q.mkdir(parents=True, exist_ok=True)
            elif p.is_file():
                q.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, q)
                if sha256_file(p) != sha256_file(q):
                    bad.append(p.relative_to(src).as_posix())
        if bad:
            return dict(plan, applied=False, method=method, copy_problems=bad,
                        note="Some copies differ from their originals; the library was not switched. The old folder is unchanged.")
    lib = Library(dst)
    lib.log("move_library", **{"from": str(src), "to": str(dst), "method": method})
    note = ("Moved by renaming." if method == "rename" else
            "Copied and verified. The old folder is untouched: delete it yourself once you have checked the new one.")
    return dict(plan, applied=True, method=method, note=note)


def adopt_library(folder: str):
    """Use an existing library folder (for example one copied from another device): check it, then switch."""
    p = Path(folder).expanduser()
    if not p.is_absolute() or not p.is_dir():
        raise LibraryError("Give the full path of an existing folder.")
    lib = Library(p)
    res = lib.verify("")
    lib.log("adopt_library", folder=str(lib.root), bundles=len(res["items"]), problems=res["problems"])
    return dict(folder=str(lib.root), bundles=len(res["items"]), problems=res["problems"],
                damaged=[r["item"] for r in res["items"] if r["status"] != "ok"])
