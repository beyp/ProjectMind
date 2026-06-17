"""
TaskParser - Analyse du texte libre via Groq pour structurer les tâches.
"""
import json
import logging
import os
import requests

logger = logging.getLogger(__name__)

GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT_FR = """Tu es un assistant de gestion de projets expert.
Ton rôle est d analyser du texte brut (notes, emails, compte-rendus) et d en extraire
une liste structurée de tâches pour un tableau de suivi de projet.

Pour chaque tâche identifiée, fournis un JSON avec :
- "category" : catégorie/livrable (ex: OCM, TI, Data Collect)
- "title" : titre court de la tâche
- "status" : statut parmi [En cours, Réalisé, A planifier, Bloqué, En retard, En revue]
- "date_label" : date ou période si mentionnée (ex: "17/06", "Juin", "TBD")
- "description" : détail optionnel
- "ado_item_id" : ID Azure DevOps si mentionné (nombre uniquement, null sinon)

Réponds UNIQUEMENT avec un tableau JSON valide, sans texte avant ou après.
Exemple :
[
  {"category": "OCM", "title": "Formation équipes DO/PAIE", "status": "En cours", "date_label": "Juin", "description": "", "ado_item_id": null},
  {"category": "TI", "title": "Activation comptes MANUF", "status": "En cours", "date_label": "TBD", "description": "Lié au planning formation", "ado_item_id": 12345}
]"""

SYSTEM_PROMPT_EN = """You are an expert project management assistant.
Your role is to analyze raw text (notes, emails, meeting minutes) and extract
a structured list of tasks for a project tracking table.

For each identified task, provide a JSON with:
- "category" : category/deliverable (ex: OCM, IT, Data Collect)
- "title" : short task title
- "status" : status from [In Progress, Completed, To Plan, Blocked, Delayed, In Review]
- "date_label" : date or period if mentioned (ex: "Jun 17", "June", "TBD")
- "description" : optional detail
- "ado_item_id" : Azure DevOps ID if mentioned (number only, null otherwise)

Reply ONLY with a valid JSON array, no text before or after."""

RESTRUCTURE_PROMPT_FR = """Tu es un assistant de gestion de projets.
Voici la liste actuelle des tâches d un projet (JSON).
Restructure-les en regroupant par catégories logiques, en suggérant des catégories
manquantes ou en renommant celles qui seraient plus claires.
Retourne UNIQUEMENT le JSON restructuré, même format qu en entrée."""


class TaskParser:
    """Parse du texte libre en tâches structurées via Groq."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")

    def parse_text(self, text: str, language: str = "fr") -> list[dict]:
        """
        Analyse du texte libre et retourne une liste de tâches structurées.

        Args:
            text: Texte brut à analyser
            language: "fr" ou "en"

        Returns:
            Liste de dicts avec keys: category, title, status, date_label,
                                      description, ado_item_id
        """
        if not self.api_key:
            return [{"error": "GROQ_API_KEY non configurée"}]

        system = SYSTEM_PROMPT_FR if language == "fr" else SYSTEM_PROMPT_EN

        try:
            r = requests.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":    GROQ_MODEL,
                    "messages": [
                        {"role": "system",  "content": system},
                        {"role": "user",    "content": f"Analyse ce texte :\n\n{text}"},
                    ],
                    "temperature": 0.3,
                    "max_tokens":  2048,
                },
                timeout=30,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()

            # Extraire le JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            tasks = json.loads(content)
            if isinstance(tasks, list):
                return tasks
            return [tasks] if isinstance(tasks, dict) else []

        except json.JSONDecodeError as e:
            logger.error("TaskParser: JSON invalide: %s", e)
            return [{"error": f"Réponse Groq non parseable: {e}"}]
        except Exception as e:
            logger.error("TaskParser: erreur: %s", e)
            return [{"error": str(e)}]

    def restructure_tasks(self, tasks: list[dict], language: str = "fr") -> list[dict]:
        """
        Demande à Groq de restructurer/regrouper les tâches existantes.
        """
        if not self.api_key or not tasks:
            return tasks

        prompt_base = RESTRUCTURE_PROMPT_FR if language == "fr" else RESTRUCTURE_PROMPT_FR

        try:
            r = requests.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":    GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": prompt_base},
                        {"role": "user",   "content": json.dumps(tasks, ensure_ascii=False)},
                    ],
                    "temperature": 0.4,
                    "max_tokens":  3000,
                },
                timeout=30,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()
            if "```" in content:
                content = content.split("```")[1].strip()
                if content.startswith("json"):
                    content = content[4:].strip()
            return json.loads(content)
        except Exception as e:
            logger.error("TaskParser restructure: %s", e)
            return tasks

    def suggest_categories(self, tasks: list[dict], language: str = "fr") -> list[str]:
        """Suggère des catégories basées sur les tâches existantes."""
        cats = list({t.get("category", "") for t in tasks if t.get("category")})
        return sorted(cats)
