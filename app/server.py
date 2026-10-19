# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Wen Yi LEONG
"""Local server for JAF Rule Bench: serves the interface and runs the model on request.
Binds to 127.0.0.1 only; nothing leaves the machine."""
from __future__ import annotations
import json, os, sys, threading, time, datetime, traceback, socket, webbrowser, csv, io, copy
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from jaf.params import Params, PARAM_SPEC, VERSION
from jaf import report
from jaf import world_report
from jaf.world import World, illustrative_world, LIABILITY
from jaf.template import write_template, read_template, read_workbook
from jaf.design import Design, ParamSpec
from jaf import estimate as EST
from jaf import recovery as REC
from jaf import prereg as PRE
from jaf.measure import QUANTITIES


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for cand in (os.path.join(base, name), os.path.join(base, "app", name), os.path.join(os.path.dirname(os.path.abspath(__file__)), name)):
        if os.path.exists(cand):
            return cand
    raise FileNotFoundError(name)


def data_dir():
    root = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(root, "JAF Rule Bench"); os.makedirs(d, exist_ok=True)
    return d


def export_dir():
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    base = docs if os.path.isdir(docs) else os.path.expanduser("~")
    d = os.path.join(base, "JAF Rule Bench"); os.makedirs(d, exist_ok=True)
    return d


class Job:
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False; self.progress = 0.0; self.label = ""; self.error = None
        self.started = None; self.cancel_flag = False
        self.result = None
        self._load()

    def _load(self):
        for path in (os.path.join(data_dir(), "last_result.json"), None):
            try:
                if path is None:
                    path = resource("default_result.json")
                with open(path, encoding="utf-8") as fh:
                    self.result = json.load(fh)
                return
            except Exception:
                continue

    def start(self, params: dict, sweep: int):
        with self.lock:
            if self.running:
                return False
            self.running, self.progress, self.label, self.error = True, 0.0, "Starting", None
            self.cancel_flag = False; self.started = time.time()
        threading.Thread(target=self._run, args=(params, sweep), daemon=True).start()
        return True

    def _run(self, params, sweep):
        try:
            P = Params.from_dict({**Params().to_dict(), **params})
            def cb(f, label):
                self.progress, self.label = f, label
            res = report.run(P, sweep_draws=sweep, progress=cb, cancel=lambda: self.cancel_flag)
            res["elapsed_seconds"] = round(time.time() - self.started, 1)
            self.result = res
            with open(os.path.join(data_dir(), "last_result.json"), "w", encoding="utf-8") as fh:
                json.dump(res, fh)
        except KeyboardInterrupt:
            self.error = "Run cancelled. The previous results are still shown."
        except Exception as exc:  # report to the interface
            self.error = f"The run stopped: {exc}"
            traceback.print_exc()
        finally:
            self.running = False

    def state(self):
        return dict(running=self.running, progress=round(self.progress, 4), label=self.label, error=self.error,
                    elapsed=round(time.time() - self.started, 1) if self.started and self.running else None,
                    has_result=self.result is not None)


class WorldJob:
    """Coded-world runs: a loaded world, its last result and the last counterfactual."""
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False; self.progress = 0.0; self.label = ""; self.error = None; self.started = None
        self.cancel_flag = False
        self.world = None; self.issues = []; self.result = None; self.cf = None; self.design = None
        try:
            with open(os.path.join(data_dir(), "world.json"), encoding="utf-8") as fh:
                d = json.load(fh)
            self.world = World.from_dict(d["world"]); self.issues = d.get("issues", [])
            self.design = Design.from_dict(d["design"]) if d.get("design") else None
            with open(os.path.join(data_dir(), "world_result.json"), encoding="utf-8") as fh:
                res = json.load(fh)
            self.result = res if res.get("version") == VERSION else None   # results from an earlier version are re-run (plan s 13.1, issue 8)
        except Exception:
            try:
                with open(resource("default_world_result.json"), encoding="utf-8") as fh:
                    self.result = json.load(fh)
                self.world = World.from_dict(self.result["world"]); self.issues = self.result.get("issues", [])
            except Exception:
                pass

    def set_world(self, world, issues, design=None):
        with self.lock:
            self.world, self.issues, self.result, self.cf, self.design = world, issues, None, None, design
        if EJOB is not None:
            EJOB.reset()
        self.persist()

    def persist(self):
        if self.world is not None:
            with open(os.path.join(data_dir(), "world.json"), "w", encoding="utf-8") as fh:
                json.dump(dict(world=self.world.to_dict(), issues=self.issues,
                               design=self.design.to_dict() if self.design else None), fh, default=str)

    def start(self, kind, params, **kw):
        with self.lock:
            if self.running or self.world is None:
                return False
            self.running, self.progress, self.label, self.error = True, 0.0, "Starting", None
            self.cancel_flag = False; self.started = time.time()
        threading.Thread(target=self._run, args=(kind, params, kw), daemon=True).start()
        return True

    def _run(self, kind, params, kw):
        try:
            P = Params.from_dict({**Params().to_dict(), **params})
            def cb(f, label):
                self.progress, self.label = f, label
            cancel = lambda: self.cancel_flag
            if kind == "run":
                res = world_report.run_world(self.world, P, issues=self.issues, progress=cb, cancel=cancel)
                res["elapsed_seconds"] = round(time.time() - self.started, 1)
                self.result, self.cf = res, None
                with open(os.path.join(data_dir(), "world_result.json"), "w", encoding="utf-8") as fh:
                    json.dump(res, fh)
            else:
                self.cf = world_report.run_counterfactual(self.world, kw["code"], kw["rule"], P, progress=cb, cancel=cancel)
        except KeyboardInterrupt:
            self.error = "Run cancelled."
        except Exception as exc:
            self.error = f"The run stopped: {exc}"
            traceback.print_exc()
        finally:
            self.running = False

    def state(self):
        return dict(running=self.running, progress=round(self.progress, 4), label=self.label, error=self.error,
                    has_world=self.world is not None, has_result=self.result is not None)

    def payload(self):
        return dict(world=self.world.to_dict() if self.world else None, issues=self.issues,
                    result=self.result, cf=self.cf, rule_labels=LIABILITY)


class EstJob:
    """Estimation, identification, recovery and validation on the loaded world and design (build plan s 14)."""
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False; self.progress = 0.0; self.label = ""; self.error = None; self.started = None
        self.cancel_flag = False; self.kind = None
        self.results = {}; self.record = None; self.last_params = None
        try:
            with open(os.path.join(data_dir(), "est_result.json"), encoding="utf-8") as fh:
                d = json.load(fh)
            if d.get("version") == VERSION:
                self.results, self.record = d.get("results", {}), d.get("record")
        except Exception:
            pass

    def reset(self):
        self.results = {}; self._persist()

    def _persist(self):
        try:
            with open(os.path.join(data_dir(), "est_result.json"), "w", encoding="utf-8") as fh:
                json.dump(dict(version=VERSION, results=self.results, record=self.record), fh, default=_jsonable)
        except Exception:
            traceback.print_exc()

    def start(self, kind, params, opts):
        with self.lock:
            if self.running:
                return False, "An estimation task is already running."
            if WJOB.world is None or WJOB.design is None:
                return False, "Load a world with an empirical design first (the Data and Estimation sheets of the template)."
            self.running, self.progress, self.label, self.error, self.kind = True, 0.0, "Starting", None, kind
            self.cancel_flag = False; self.started = time.time(); self.last_params = params
            world = World.from_dict(WJOB.world.to_dict()); design = copy.deepcopy(WJOB.design)   # the job works on its own copies
        threading.Thread(target=self._run, args=(kind, params, opts, world, design), daemon=True).start()
        return True, None

    def _run(self, kind, params, opts, world, design):
        try:
            P = Params.from_dict({**Params().to_dict(), **params})
            d = design
            def cb(f, label):
                self.progress, self.label = f, label
            cancel = lambda: self.cancel_flag
            if kind == "identify":
                m = EST.Model(world, d, P, cancel=cancel)
                cb(0.1, "Computing how each target responds to each parameter")
                res = EST.identification(m)
                self.results["identify"] = dict(res, generated=_now())
            elif kind == "estimate":
                m = EST.Model(world, d, P, cancel=cancel)
                est = EST.estimate(m, override=bool(opts.get("override")), progress=lambda f, l: cb(0.85 * f, l))
                est["generated"] = _now(); est["override"] = bool(opts.get("override"))
                if est["status"] == "ok":
                    cb(0.86, "Validating against holdout observations")
                    est["validation"] = EST.validate(m, est, progress=lambda f, l: cb(0.86 + 0.14 * f, l))
                    if self.record:
                        est["prereg_check"] = PRE.check(self.record, world, d, P)
                    est["synthetic"] = d.synthetic
                self.results["estimate"] = est
                if est.get("identification_start"):
                    self.results["identify"] = dict(est["identification_start"], generated=_now())
            elif kind == "recovery":
                reps = max(0, min(20, int(opts.get("reps", 3))))
                truth = opts.get("truth") or None
                res = REC.recovery(world, d, truth, reps=reps, base=P, progress=cb, cancel=cancel)
                self.results["recovery"] = dict(res, generated=_now())
            if WJOB.design is not None and PRE.fingerprint(WJOB.design.to_dict()) != PRE.fingerprint(d.to_dict()):
                self.results = {}              # the world or design changed while the job ran: discard
                self.error = "The loaded world or design changed while the task ran; its results were discarded."
            self._persist()
        except KeyboardInterrupt:
            self.error = "Cancelled."
        except Exception as exc:
            self.error = f"The task stopped: {exc}"
            traceback.print_exc()
        finally:
            self.running = False

    def state(self):
        return dict(running=self.running, kind=self.kind, progress=round(self.progress, 4), label=self.label, error=self.error,
                    elapsed=round(time.time() - self.started, 1) if self.started and self.running else None)


def _finite(o):
    """Replace non-finite floats with None, recursively (review finding 5)."""
    if isinstance(o, float):
        return o if o == o and o not in (float("inf"), float("-inf")) else None
    if isinstance(o, dict):
        return {k: _finite(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_finite(v) for v in o]
    try:
        import numpy as np
        if isinstance(o, np.ndarray):
            return _finite(o.tolist())
        if isinstance(o, np.generic):
            return _finite(o.item())
    except Exception:
        pass
    return o


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _jsonable(o):
    try:
        import numpy as np
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, np.generic):
            return o.item()
    except Exception:
        pass
    return str(o)


def apply_spec(design: Design, spec: dict):
    """Apply estimation settings edited in the interface to the loaded design. Returns a list of errors
    (nothing is changed if there are any)."""
    if not spec:
        return []
    out = None
    if spec.get("params"):
        out = []
        try:
            for p in spec["params"]:
                num = lambda k: None if p.get(k) in (None, "") else float(p[k])
                out.append(ParamSpec(str(p.get("name")), bool(p.get("free")), num("value"), num("lower"), num("upper"),
                                     num("judgement_low"), num("judgement_high"), str(p.get("notes") or "")))
        except (TypeError, ValueError):
            return ["Every value and bound must be a number."]
        errs = EST.validate_spec(out)
        if errs:
            return errs
    if spec.get("concept") not in (None, "a", "b"):
        return ["The equilibrium concept must be a or b."]
    if spec.get("concept"):
        design.concept = spec["concept"]
    if spec.get("starts"):
        design.starts = max(1, min(20, int(spec["starts"])))
    if out is not None:
        design.params = out
    return []


def est_payload():
    w, d = WJOB.world, WJOB.design
    from jaf.examples import illustrative_design, is_illustrative_world
    if w is not None and d is None and is_illustrative_world(w):
        WJOB.design = d = illustrative_design(w); WJOB.persist()
    base = Params.from_dict({**Params().to_dict(), **(EJOB.last_params or {})})
    check = PRE.check(EJOB.record, w, d, base) if (EJOB.record and w is not None and d is not None) else None
    return dict(has_world=w is not None, design=d.to_dict() if d else None, codes=w.codes if w else [],
                names=[j.name for j in w.jurisdictions] if w else [], illustrative=bool(w and w.settings.illustrative),
                results=EJOB.results, record=EJOB.record, prereg_check=check, quantities=QUANTITIES,
                est_params=EST.EST_PARAMS, world_settings=dict(mobility_custodial=w.settings.mobility_custodial,
                                                               mobility_self_hosted=w.settings.mobility_self_hosted) if w else None)


def save_est_bundle():
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dd = os.path.join(export_dir(), f"estimation_{stamp}"); os.makedirs(dd, exist_ok=True)
    with open(os.path.join(dd, "estimation_results.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(version=VERSION, results=EJOB.results, design=WJOB.design.to_dict() if WJOB.design else None,
                       prereg=EJOB.record), fh, indent=1, default=_jsonable)
    est = EJOB.results.get("estimate")
    if est and est.get("status") == "ok":
        rows = [["parameter", "estimate", "se", "ci_low", "ci_high", "lower_bound", "upper_bound", "at_bound"]]
        rows += [[p["name"], p["estimate"], p["se"], p["ci_low"], p["ci_high"], p["lower"], p["upper"], p["at_bound"]] for p in est["params"]]
        with open(os.path.join(dd, "estimates.csv"), "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows(rows)
        rows = [["id", "quantity", "code", "episode", "compared_with", "observed", "model", "sd", "z"]]
        rows += [[f["id"], f["quantity"], f["code"], f["episode"], f["compared_with"], f["observed"], f["model"], f["sd"], f["z"]] for f in est["fit"]]
        with open(os.path.join(dd, "fit.csv"), "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows(rows)
        v = est.get("validation") or {}
        if v.get("rows"):
            rows = [["id", "quantity", "code", "episode", "compared_with", "prediction", "band_low", "band_high", "observed", "sd", "z", "passed"]]
            rows += [[r["id"], r["quantity"], r["code"], r["episode"], r["compared_with"], r["prediction"], r["lo"], r["hi"], r.get("observed"), r.get("sd"), r.get("z"), r.get("passed")] for r in v["rows"]]
            with open(os.path.join(dd, "validation.csv"), "w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerows(rows)
    if WJOB.world is not None:
        with open(os.path.join(dd, "world_and_design.xlsx"), "wb") as fh:
            fh.write(write_template(WJOB.world, design=WJOB.design))
    return dd


JOB = None
WJOB = None
EJOB = None


def save_bundle(res):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    d = os.path.join(export_dir(), f"run_{stamp}"); os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    rows = [["rule", "concept", "effective_rate", "mean_nominal_rate", "revenue", "gap", "overlap", "unobserved", "exit", "converged"]]
    for r, v in res["rules"].items():
        for c in ("a", "b"):
            x = v[c]
            rows.append([r, c, x["effective"], x["mean_tau"], x["revenue"], x["gap"], x["overlap"], x["unobserved"], x["exit"], x["converged"]])
    with open(os.path.join(d, "rules.csv"), "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    with open(os.path.join(d, "parameters.json"), "w", encoding="utf-8") as fh:
        json.dump(res["params"], fh, indent=1)
    return d


def save_world_bundle(wj):
    res = wj.result
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    d = os.path.join(export_dir(), f"world_{stamp}"); os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "world_results.json"), "w", encoding="utf-8") as fh:
        json.dump(dict(result=res, counterfactual=wj.cf), fh, indent=1)
    with open(os.path.join(d, "coded_world.xlsx"), "wb") as fh:
        fh.write(write_template(wj.world, design=wj.design))
    rows = [["code", "name", "rule", "rate_mode", "concept", "rate", "revenue", "resident_base", "resident_gap", "resident_overlap",
             "claimed_primary", "placed_here", "verified"]]
    for c in ("a", "b"):
        x = res["concepts"].get(c)
        if not x:
            continue
        for i, code in enumerate(res["codes"]):
            rows.append([code, res["names"][i], res["rules"][i], "fixed" if res["fixed"][i] else "competitive", c,
                         x["tau"][i], x["revenue"][i], x["resident_base"][i], x["resident_gap"][i], x["resident_overlap"][i],
                         x["claimed_primary"][i], x["placed_here"][i], code not in res["unverified"]])
    with open(os.path.join(d, "jurisdictions.csv"), "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    return d


class Handler(BaseHTTPRequestHandler):
    server_version = "JAFRuleBench/" + VERSION

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, (bytes, str)):
            body = json.dumps(_finite(body), default=_jsonable, allow_nan=False)   # browsers reject Infinity and NaN
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _raw(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def _xlsx(self, name, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers(); self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(resource("ui.html"), "rb") as fh:
                return self._send(200, fh.read(), "text/html; charset=utf-8")
        if self.path == "/api/state":
            return self._send(200, JOB.state())
        if self.path == "/api/result":
            return self._send(200, JOB.result or {})
        if self.path == "/api/template/illustrative":
            return self._xlsx("JAF_template_illustrative.xlsx", write_template(kind="illustrative"))
        if self.path == "/api/template/blank":
            return self._xlsx("JAF_template_real_sample.xlsx", write_template(kind="blank"))
        if self.path == "/api/template/current":
            if WJOB.world is None:
                return self._send(404, {"error": "No world is loaded."})
            return self._xlsx("JAF_template_current.xlsx", write_template(WJOB.world, design=WJOB.design))
        if self.path == "/api/world/state":
            return self._send(200, WJOB.state())
        if self.path == "/api/world/data":
            return self._send(200, WJOB.payload())
        if self.path == "/api/est/state":
            return self._send(200, EJOB.state())
        if self.path == "/api/est/data":
            return self._send(200, json.loads(json.dumps(est_payload(), default=_jsonable)))
        if self.path in ("/api/est/prereg.md", "/api/est/prereg.json"):
            if not EJOB.record:
                return self._send(404, {"error": "Nothing has been frozen yet."})
            fp = EJOB.record["fingerprint"][:12]
            if self.path.endswith(".md"):
                data = PRE.to_markdown(EJOB.record).encode("utf-8"); ctype = "text/markdown; charset=utf-8"; name = f"JAF_preregistration_{fp}.md"
            else:
                data = json.dumps(EJOB.record, indent=1, ensure_ascii=False, default=_jsonable).encode("utf-8"); ctype = "application/json"; name = f"JAF_preregistration_{fp}.json"
            self.send_response(200); self.send_header("Content-Type", ctype)
            self.send_header("Content-Disposition", f'attachment; filename="{name}"'); self.send_header("Content-Length", str(len(data)))
            self.end_headers(); self.wfile.write(data); return
        if self.path == "/api/defaults":
            return self._send(200, dict(params=Params().to_dict(), spec=PARAM_SPEC, version=VERSION))
        return self._send(404, {"error": "Not found"})

    def do_POST(self):
        if self.path == "/api/run":
            b = self._body()
            sweep = max(0, min(200, int(b.get("sweep", 12))))
            ok = JOB.start(b.get("params", {}), sweep)
            return self._send(200 if ok else 409, {"started": ok, "message": None if ok else "A run is already in progress."})
        if self.path in ("/api/world/load", "/api/world/illustrative") and (EJOB.running or WJOB.running):
            self._raw()
            return self._send(409, {"error": "A task is running. Wait for it to finish, or cancel it, before loading another world."})
        if self.path == "/api/world/load":
            world, design, issues = read_workbook(self._raw())
            if world is not None:
                WJOB.set_world(world, issues, design)
            return self._send(200, {"ok": world is not None, "issues": issues, "design": design is not None})
        if self.path == "/api/world/illustrative":
            from jaf.examples import illustrative_design
            w = illustrative_world()
            WJOB.set_world(w, [], illustrative_design(w))
            return self._send(200, {"ok": True, "issues": []})
        if self.path == "/api/est/run":
            b = self._body()
            kind = b.get("kind")
            if kind not in ("identify", "estimate", "recovery"):
                return self._send(400, {"error": "Unknown task."})
            if EJOB.running:
                return self._send(409, {"started": False, "message": "An estimation task is already running."})
            if WJOB.design is not None:
                errs = apply_spec(WJOB.design, b.get("spec") or {})
                if errs:
                    return self._send(400, {"started": False, "message": "Estimation settings: " + " ".join(errs[:6])})
                WJOB.persist()
            ok, msg = EJOB.start(kind, b.get("params", {}), b)
            return self._send(200 if ok else 409, {"started": ok, "message": msg})
        if self.path == "/api/est/cancel":
            EJOB.cancel_flag = True
            return self._send(200, {"cancelling": True})
        if self.path == "/api/est/freeze":
            if WJOB.design is None or WJOB.world is None:
                return self._send(400, {"error": "Load a world with an empirical design first."})
            b = self._body()
            if EJOB.running:
                return self._send(409, {"error": "Wait for the running task to finish before freezing."})
            errs = apply_spec(WJOB.design, b.get("spec") or {})
            if errs:
                return self._send(400, {"error": "Estimation settings: " + " ".join(errs[:6])})
            WJOB.persist()
            EJOB.last_params = b.get("params") or EJOB.last_params
            base = Params.from_dict({**Params().to_dict(), **(EJOB.last_params or {})})
            EJOB.record = PRE.freeze(WJOB.world, WJOB.design, author=str(b.get("author") or ""), title=str(b.get("title") or ""), base=base)
            EJOB._persist()
            return self._send(200, {"fingerprint": EJOB.record["fingerprint"]})
        if self.path == "/api/est/prereg/load":
            try:
                raw = self._raw().decode("utf-8")
                if raw.lstrip().startswith("#"):          # markdown: take the record's JSON block
                    return self._send(400, {"error": "Load the .json file saved with the pre-registration, not the .md document."})
                rec = json.loads(raw)
                if rec.get("kind") != "JAF Rule Bench pre-registration" or "content" not in rec:
                    raise ValueError
            except Exception:
                return self._send(400, {"error": "This is not a JAF Rule Bench pre-registration file (.json)."})
            EJOB.record = rec; EJOB._persist()
            return self._send(200, {"fingerprint": rec.get("fingerprint")})
        if self.path == "/api/est/save":
            if not EJOB.results:
                return self._send(400, {"error": "There are no estimation results to save yet."})
            return self._send(200, {"folder": save_est_bundle()})
        if self.path == "/api/world/run":
            b = self._body()
            ok = WJOB.start("run", b.get("params", {}))
            return self._send(200 if ok else 409, {"started": ok, "message": None if ok else "A run is in progress, or no world is loaded."})
        if self.path == "/api/world/counterfactual":
            b = self._body()
            rule_ok = b.get("rule") in LIABILITY or b.get("rule") in ("intermediary:seat", "intermediary:base")
            if WJOB.world is None or b.get("code") not in WJOB.world.codes or not rule_ok:
                return self._send(400, {"error": "Choose a jurisdiction and a rule."})
            ok = WJOB.start("cf", b.get("params", {}), code=b["code"], rule=b["rule"])
            return self._send(200 if ok else 409, {"started": ok, "message": None if ok else "A run is in progress."})
        if self.path == "/api/world/cancel":
            WJOB.cancel_flag = True
            return self._send(200, {"cancelling": True})
        if self.path == "/api/world/save":
            if not WJOB.result:
                return self._send(400, {"error": "There are no coded-world results to save yet."})
            return self._send(200, {"folder": save_world_bundle(WJOB)})
        if self.path == "/api/cancel":
            JOB.cancel_flag = True
            return self._send(200, {"cancelling": True})
        if self.path == "/api/save":
            if not JOB.result:
                return self._send(400, {"error": "There are no results to save yet. Run the model first."})
            return self._send(200, {"folder": save_bundle(JOB.result)})
        if self.path == "/api/quit":
            self._send(200, {"bye": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        return self._send(404, {"error": "Not found"})


def free_port(start=8765):
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port)); return port
            except OSError:
                continue
    raise RuntimeError("No free local port found between 8765 and 8814.")


def main(open_browser=True):
    global JOB, WJOB, EJOB
    JOB = Job(); WJOB = WorldJob(); EJOB = EstJob()
    port = free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None
    print(f"JAF Rule Bench {VERSION}")
    print(f"Interface: {url}")
    print("Runs locally; nothing is sent over the internet.")
    print("Free for noncommercial use (PolyForm Noncommercial 1.0.0; documents CC BY-NC 4.0).")
    print("Bundled components keep their own licences: see THIRD_PARTY_NOTICES.txt.")
    print("Close this window, or press Ctrl+C, to quit.\n")
    if open_browser and not os.environ.get("JAF_NO_BROWSER"):
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
