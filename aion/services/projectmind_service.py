"""Service projectmind_status - récupère le statut de ProjectMind pour AION."""
import os
from typing import Any
import requests as req

from aion.services.base_service import BaseService

PROJECTMIND_URL = os.getenv("PROJECTMIND_URL", "http://localhost:8766")


class ProjectmindStatusService(BaseService):
    """Récupère le statut des projets ProjectMind."""

    name        = "projectmind_status"
    description = "Affiche le statut des projets ProjectMind"
    permissions = ["network"]
    domain      = "svc"

    def execute(self, payload: dict[str, Any]) -> str:
        try:
            r = req.get(f"{PROJECTMIND_URL}/api/projects", timeout=3)
            r.raise_for_status()
            projects = r.json()
            if not projects:
                return "ProjectMind : aucun projet."
            lines = [f"ProjectMind : {len(projects)} projet(s) :"]
            for p in projects:
                lines.append(
                    f"  - {p['name']} [{p.get('language','fr').upper()}]"
                    + (f" | Go-Live: {p['go_live_date']}" if p.get("go_live_date") else "")
                )
            lines.append(f"  Dashboard : {PROJECTMIND_URL}")
            return "\n".join(lines)
        except req.exceptions.ConnectionError:
            return f"ProjectMind non disponible ({PROJECTMIND_URL})"
        except Exception as exc:
            return f"ProjectMind erreur : {exc}"
