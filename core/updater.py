"""
updater.py - Auto-update ProjectMind via git pull + redémarrage.
"""
import json, logging, os, subprocess, sys, threading, time
from datetime import datetime
from pathlib import Path

logger     = logging.getLogger(__name__)
STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "updater_state.json"

class ProjectMindUpdater:
    DEFAULT_CHECK_INTERVAL = 3600

    def __init__(self, mode="notify", check_interval=None):
        self.mode           = mode
        self.check_interval = check_interval or self.DEFAULT_CHECK_INTERVAL
        self.repo_path      = Path(__file__).resolve().parent.parent
        self._thread        = None
        self._stop_event    = threading.Event()
        self._state         = self._load_state()

    def start(self):
        if self._thread and self._thread.is_alive(): return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True, name="pm-updater")
        self._thread.start()
        logger.info("ProjectMindUpdater démarré (mode=%s, interval=%ds)", self.mode, self.check_interval)

    def stop(self):
        self._stop_event.set()

    def check_now(self):
        try:
            fetch = subprocess.run(["git","fetch","origin","main","--quiet"],
                cwd=str(self.repo_path), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            if fetch.returncode != 0:
                raise RuntimeError(f"git fetch: {fetch.stderr.strip()[:100]}")
            local  = subprocess.run(["git","rev-parse","HEAD"],            cwd=str(self.repo_path), capture_output=True, text=True, encoding="utf-8", errors="replace")
            remote = subprocess.run(["git","rev-parse","origin/main"],     cwd=str(self.repo_path), capture_output=True, text=True, encoding="utf-8", errors="replace")
            cur_sha = local.stdout.strip()[:12]; rem_sha = remote.stdout.strip()[:12]
            update  = cur_sha != rem_sha
            behind  = 0
            if update:
                b = subprocess.run(["git","rev-list","--count","HEAD..origin/main"], cwd=str(self.repo_path), capture_output=True, text=True, encoding="utf-8", errors="replace")
                try: behind = int(b.stdout.strip())
                except: behind = 1
            msg  = subprocess.run(["git","log","origin/main","-1","--pretty=%s"],  cwd=str(self.repo_path), capture_output=True, text=True, encoding="utf-8", errors="replace")
            date = subprocess.run(["git","log","origin/main","-1","--pretty=%cr"], cwd=str(self.repo_path), capture_output=True, text=True, encoding="utf-8", errors="replace")
            state = {"update_available":update,"current_commit":cur_sha,"remote_commit":rem_sha,
                     "commits_behind":behind,"latest_message":msg.stdout.strip(),
                     "latest_date":date.stdout.strip(),"checked_at":datetime.now().isoformat(),
                     "applied_at":self._state.get("applied_at",""),"error":""}
            self._state = state; self._save_state()
            logger.info("Update check: %s (behind=%d)", "DISPO" if update else "À JOUR", behind)
            if update and self.mode == "auto": return self.apply_update()
            return state
        except Exception as e:
            state = {"update_available":False,"current_commit":"unknown","remote_commit":"unknown",
                     "commits_behind":0,"latest_message":"","latest_date":"",
                     "checked_at":datetime.now().isoformat(),"applied_at":self._state.get("applied_at",""),"error":str(e)}
            self._state = state; self._save_state()
            logger.warning("Update check error: %s", e); return state

    def apply_update(self):
        steps = []
        pull = subprocess.run(["git","pull","origin","main"], cwd=str(self.repo_path),
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        ok = pull.returncode == 0
        steps.append({"name":"git pull","success":ok,"output":(pull.stdout if ok else pull.stderr).strip()[:200]})
        if not ok: return {"success":False,"steps":steps,"message":f"git pull échoué: {pull.stderr.strip()[:100]}"}

        venv_pip = self.repo_path / ".venv" / "Scripts" / "pip.exe"
        pip_cmd  = [str(venv_pip)] if venv_pip.exists() else [sys.executable, "-m", "pip"]
        req      = self.repo_path / "requirements.txt"
        if req.exists():
            pip = subprocess.run(pip_cmd + ["install","-r","requirements.txt","--quiet"],
                cwd=str(self.repo_path), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
            steps.append({"name":"pip install","success":pip.returncode==0,"output":(pip.stdout+pip.stderr).strip()[:200]})
        else:
            steps.append({"name":"pip install","success":True,"output":"Pas de requirements.txt"})

        self._state["applied_at"] = datetime.now().isoformat()
        self._state["update_available"] = False; self._save_state()
        steps.append({"name":"restart","success":True,"output":"Redémarrage dans 3s..."})
        threading.Thread(target=self._delayed_restart, daemon=True).start()
        return {"success":True,"steps":steps,"message":"Mise à jour appliquée ! Redémarrage dans 3 secondes.","restart_in":3}

    def get_state(self): return self._state

    def _watch_loop(self):
        self._stop_event.wait(30)
        while not self._stop_event.is_set():
            self.check_now(); self._stop_event.wait(self.check_interval)

    def _delayed_restart(self):
        time.sleep(3); self._restart()

    def _restart(self):
        os.system("cls" if sys.platform=="win32" else "clear")
        print("\n" + "="*52 + "\n  ProjectMind — Redémarrage après mise à jour\n" + "="*52)
        venv_uv = self.repo_path / ".venv" / "Scripts" / "uvicorn.exe"
        if venv_uv.exists():
            exe = str(venv_uv); args = [exe, "main:app", "--reload", "--port", "8766"]
        else:
            venv_py = self.repo_path / ".venv" / "Scripts" / "python.exe"
            exe     = str(venv_py) if venv_py.exists() else sys.executable
            args    = [exe, "-m", "uvicorn", "main:app", "--reload", "--port", "8766"]
        try:
            os.chdir(str(self.repo_path)); os.execv(exe, args)
        except Exception as e:
            logger.error("os.execv: %s", e)
            try: subprocess.call(args, cwd=str(self.repo_path))
            except: pass
            finally: os._exit(0)

    def _load_state(self):
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, encoding="utf-8") as f: return json.load(f)
            except: pass
        return {"update_available":False,"current_commit":"","remote_commit":"","commits_behind":0,
                "latest_message":"","latest_date":"","checked_at":"","applied_at":"","error":""}

    def _save_state(self):
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE,"w",encoding="utf-8") as f: json.dump(self._state,f,indent=2,ensure_ascii=False)
        except Exception as e: logger.warning("Save state: %s", e)
