"""Local server for JAF Rule Bench: serves the interface and runs the model on request.
Binds to 127.0.0.1 only; nothing leaves the machine."""
from __future__ import annotations
import json, os, sys, threading, time, datetime, traceback, socket, webbrowser, csv, io
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from jaf.params import Params, PARAM_SPEC, VERSION
from jaf import report
from jaf import world_report
from jaf.world import World, illustrative_world, LIABILITY
from jaf.template import write_template, read_template


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
        self.world = None; self.issues = []; self.result = None; self.cf = None
        try:
            with open(os.path.join(data_dir(), "world.json"), encoding="utf-8") as fh:
                d = json.load(fh)
            self.world = World.from_dict(d["world"]); self.issues = d.get("issues", [])
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

    def set_world(self, world, issues):
        with self.lock:
            self.world, self.issues, self.result, self.cf = world, issues, None, None
        if world is not None:
            with open(os.path.join(data_dir(), "world.json"), "w", encoding="utf-8") as fh:
                json.dump(dict(world=world.to_dict(), issues=issues), fh)

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


JOB = None
WJOB = None


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
        fh.write(write_template(wj.world))
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
        data = body if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body)).encode("utf-8")
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
            return self._xlsx("JAF_template_current.xlsx", write_template(WJOB.world))
        if self.path == "/api/world/state":
            return self._send(200, WJOB.state())
        if self.path == "/api/world/data":
            return self._send(200, WJOB.payload())
        if self.path == "/api/defaults":
            return self._send(200, dict(params=Params().to_dict(), spec=PARAM_SPEC, version=VERSION))
        return self._send(404, {"error": "Not found"})

    def do_POST(self):
        if self.path == "/api/run":
            b = self._body()
            sweep = max(0, min(200, int(b.get("sweep", 12))))
            ok = JOB.start(b.get("params", {}), sweep)
            return self._send(200 if ok else 409, {"started": ok, "message": None if ok else "A run is already in progress."})
        if self.path == "/api/world/load":
            world, issues = read_template(self._raw())
            if world is not None:
                WJOB.set_world(world, issues)
            return self._send(200, {"ok": world is not None, "issues": issues})
        if self.path == "/api/world/illustrative":
            WJOB.set_world(illustrative_world(), [])
            return self._send(200, {"ok": True, "issues": []})
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
    global JOB, WJOB
    JOB = Job(); WJOB = WorldJob()
    port = free_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, "reconfigure") else None
    print(f"JAF Rule Bench {VERSION}")
    print(f"Interface: {url}")
    print("Runs locally; nothing is sent over the internet.")
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
