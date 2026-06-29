"""
updater.py — Auto-update ProjectMind.

Vérifie périodiquement si une mise à jour est disponible sur GitHub,
notifie le dashboard via bannière, et peut appliquer la mise à jour + redémarrer.

Modes :
  "notify" : affiche une bannière dans l interface (défaut)
  "auto"   : applique automatiquement et redémarre
"""
import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "updater_state.json"


class ProjectMindUpdater:
    """
    Watcher de mise à jour pour ProjectMind.
    Tourne en thread daemon, non bloquant.
    """

    DEFAULT_CHECK_INTERVAL = 3600  # 1 heure

    def __init__(self, mode: str = "notify", check_interval: int = None) -> None:
        self.mode           = mode
        self.check_interval = check_interval or self.DEFAULT_CHECK_INTERVAL
        self.repo_path      = Path(__file__).resolve().parent.parent
        self._thread        = None
        self._stop_event    = threading.Event()
        self._state         = self._load_state()

    # ── API publique ───────────────────────────────────────────────────────────

    def start(self) -> None:
        """Lance le watcher en thread daemon."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._watch_loop, daemon=True, name="pm-updater"
        )
        self._thread.start()
        logger.info("ProjectMindUpdater démarré (mode=%s, interval=%ds)", self.mode, self.check_interval)

    def stop(self) -> None:
        self._stop_event.set()

    def check_now(self) -> dict:
        """Vérifie immédiatement si une mise à jour est disponible via git fetch."""
        try:
            # 1. git fetch silencieux
            fetch = subprocess.run(
                ["git", "fetch", "origin", "main", "--quiet"],
                cwd=str(self.repo_path), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=30
            )
            if fetch.returncode != 0:
                raise RuntimeError(f"git fetch failed: {fetch.stderr.strip()[:200]}")

            # 2. SHA local
            local = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.repo_path), capture_output=True, text=True,
                encoding="utf-8", errors="replace"
            )
            current_sha = local.stdout.strip()[:12]

            # 3. SHA distant
            remote = subprocess.run(
                ["git", "rev-parse", "origin/main"],
                cwd=str(self.repo_path), capture_output=True, text=True,
                encoding="utf-8", errors="replace"
            )
            remote_sha = remote.stdout.strip()[:12]

            update_available = current_sha != remote_sha

            # 4. Commits en retard
            commits_behind = 0
            if update_available:
                behind = subprocess.run(
                    ["git", "rev-list", "--count", "HEAD..origin/main"],
                    cwd=str(self.repo_path), capture_output=True, text=True,
                    encoding="utf-8", errors="replace"
                )
                try:
                    commits_behind = int(behind.stdout.strip())
                except ValueError:
                    commits_behind = 1

            # 5. Dernier message commit distant
            last_msg = subprocess.run(
                ["git", "log", "origin/main", "-1", "--pretty=%s"],
                cwd=str(self.repo_path), capture_output=True, text=True,
                encoding="utf-8", errors="replace"
            )
            latest_message = last_msg.stdout.strip()

            # 6. Date relative
            last_date = subprocess.run(
                ["git", "log", "origin/main", "-1", "--pretty=%cr"],
                cwd=str(self.repo_path), capture_output=True, text=True,
                encoding="utf-8", errors="replace"
            )
            latest_date = last_date.stdout.strip()

            state = {
                "update_available": update_available,
                "current_commit":   current_sha,
                "remote_commit":    remote_sha,
                "commits_behind":   commits_behind,
                "latest_message":   latest_message,
                "latest_date":      latest_date,
                "checked_at":       datetime.now().isoformat(),
                "applied_at":       self._state.get("applied_at", ""),
                "error":            "",
            }
            self._state = state
            self._save_state()
            logger.info("Update check: %s (behind=%d) %s",
                        "DISPO" if update_available else "A JOUR",
                        commits_behind, latest_message[:60])

            if update_available and self.mode == "auto":
                return self.apply_update()

            return state

        except Exception as e:
            state = {
                "update_available": False,
                "current_commit": "unknown", "remote_commit": "unknown",
                "commits_behind": 0, "latest_message": "", "latest_date": "",
                "checked_at": datetime.now().isoformat(),
                "applied_at": self._state.get("applied_at", ""),
                "error": str(e),
            }
            self._state = state
            self._save_state()
            logger.warning("Update check error: %s", e)
            return state

    def apply_update(self) -> dict:
        """git pull + pip install + redémarrage."""
        steps = []
        logger.info("=== Application mise à jour ProjectMind ===")

        # Étape 1 : git pull
        try:
            pull = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=str(self.repo_path), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=120
            )
            ok = pull.returncode == 0
            steps.append({"name": "git pull", "success": ok,
                           "output": (pull.stdout if ok else pull.stderr).strip()[:200]})
            if not ok:
                return {"success": False, "steps": steps,
                        "message": f"git pull échoué : {pull.stderr.strip()[:200]}"}
            logger.info("git pull OK")
        except Exception as e:
            steps.append({"name": "git pull", "success": False, "output": str(e)})
            return {"success": False, "steps": steps, "message": str(e)}

        # Étape 2 : pip install
        venv_pip = self.repo_path / ".venv" / "Scripts" / "pip.exe"
        pip_cmd  = [str(venv_pip)] if venv_pip.exists() else [sys.executable, "-m", "pip"]
        req_file = self.repo_path / "requirements.txt"
        if req_file.exists():
            try:
                pip = subprocess.run(
                    pip_cmd + ["install", "-r", "requirements.txt", "--quiet"],
                    cwd=str(self.repo_path), capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=300
                )
                steps.append({"name": "pip install", "success": pip.returncode == 0,
                               "output": (pip.stdout + pip.stderr).strip()[:200]})
            except Exception as e:
                steps.append({"name": "pip install", "success": False, "output": str(e)})
                logger.warning("pip install error (non bloquant): %s", e)
        else:
            steps.append({"name": "pip install", "success": True, "output": "Pas de requirements.txt"})

        # Mettre à jour le state
        self._state["applied_at"]       = datetime.now().isoformat()
        self._state["update_available"] = False
        self._save_state()

        steps.append({"name": "restart", "success": True, "output": "Redémarrage dans 3s..."})
        logger.info("Mise à jour appliquée. Redémarrage dans 3s...")

        def _do_restart():
            time.sleep(3)
            self._restart()

        threading.Thread(target=_do_restart, daemon=True, name="pm-restart").start()

        return {
            "success": True, "steps": steps,
            "message": "Mise à jour appliquée ! ProjectMind redémarre dans 3 secondes.",
            "restart_in": 3,
        }

    def get_state(self) -> dict:
        return self._state

    # ── Thread watcher ─────────────────────────────────────────────────────────

    def _watch_loop(self) -> None:
        self._stop_event.wait(30)  # Attendre 30s après démarrage
        while not self._stop_event.is_set():
            self.check_now()
            self._stop_event.wait(self.check_interval)

    # ── Redémarrage ────────────────────────────────────────────────────────────

    def _restart(self) -> None:
        """Redémarre ProjectMind dans la même console via uvicorn."""
        os.system("cls" if sys.platform == "win32" else "clear")
        print("\n" + "=" * 50)
        print("  🔄 ProjectMind — Redémarrage après mise à jour")
        print("=" * 50 + "\n")

        venv_uvicorn = self.repo_path / ".venv" / "Scripts" / "uvicorn.exe"
        if venv_uvicorn.exists():
            exe = str(venv_uvicorn)
        else:
            exe = "uvicorn"

        try:
            os.execvp(exe, [exe, "main:app", "--reload", "--port", "8766"])
        except Exception as e:
            logger.error("os.execvp échoué (%s) — fallback subprocess", e)
            try:
                subprocess.call([exe, "main:app", "--reload", "--port", "8766"],
                                cwd=str(self.repo_path))
            except Exception as e2:
                logger.error("Fallback aussi échoué: %s", e2)
            finally:
                os._exit(0)

    # ── State persistant ───────────────────────────────────────────────────────

    def _load_state(self) -> dict:
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "update_available": False, "current_commit": "",
            "remote_commit": "", "commits_behind": 0,
            "latest_message": "", "latest_date": "",
            "checked_at": "", "applied_at": "", "error": "",
        }

    def _save_state(self) -> None:
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("Impossible de sauvegarder updater state: %s", e)
