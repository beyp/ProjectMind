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


# ── Modèle vision Groq ────────────────────────────────────────────────────────
GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

VISION_SYSTEM_PROMPT_FR = """Tu es un assistant de gestion de projets expert.
Tu analyses des images (screenshots, photos, tableaux, notes) et tu en extrais
une liste structurée de tâches pour un tableau de suivi de projet.

Pour chaque tâche identifiée dans l image, fournis un JSON avec :
- "category" : catégorie/livrable (ex: OCM, TI, Data Collect)
- "title" : titre court de la tâche
- "status" : parmi [En cours, Réalisé, A planifier, Bloqué, En retard, En revue]
- "date_label" : date ou période si visible (ex: "17/06", "Juin", "TBD")
- "description" : détail optionnel extrait de l image
- "ado_item_id" : ID Azure DevOps si visible (nombre uniquement, null sinon)

Analyse TOUT le contenu visible : texte, tableaux, listes, annotations.
Réponds UNIQUEMENT avec un tableau JSON valide, sans texte avant ou après."""

VISION_SYSTEM_PROMPT_EN = """You are an expert project management assistant.
You analyze images (screenshots, photos, tables, notes) and extract
a structured list of tasks for a project tracking table.

For each task identified in the image, provide a JSON with:
- "category" : category/deliverable (ex: OCM, IT, Data Collect)
- "title" : short task title
- "status" : from [In Progress, Completed, To Plan, Blocked, Delayed, In Review]
- "date_label" : date or period if visible (ex: "Jun 17", "June", "TBD")
- "description" : optional detail extracted from image
- "ado_item_id" : Azure DevOps ID if visible (number only, null otherwise)

Analyze ALL visible content: text, tables, lists, annotations.
Reply ONLY with a valid JSON array, no text before or after."""


class VisionTaskParser:
    """
    Parse des images via Groq llama-4-scout (vision).
    Bascule automatiquement sur le modèle vision quand une image est fournie.
    """

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")

    def parse_image(
        self,
        image_data: str,
        image_mime: str = "image/jpeg",
        text_context: str = "",
        language: str = "fr",
    ) -> list[dict]:
        """
        Analyse une image (base64) et extrait les tâches.

        Args:
            image_data : image encodée en base64
            image_mime : type MIME (image/jpeg, image/png, image/webp)
            text_context : texte additionnel optionnel (contexte)
            language   : "fr" ou "en"

        Returns:
            Liste de tâches structurées
        """
        if not self.api_key:
            return [{"error": "GROQ_API_KEY non configurée"}]

        system = VISION_SYSTEM_PROMPT_FR if language == "fr" else VISION_SYSTEM_PROMPT_EN

        # Construire le message multimodal
        user_content = []

        # Ajouter le contexte texte si fourni
        if text_context.strip():
            user_content.append({
                "type": "text",
                "text": (
                    f"Contexte additionnel : {text_context}\n\n"
                    "Analyse cette image et extrais les taches :"
                )
            })
        else:
            user_content.append({
                "type": "text",
                "text": "Analyse cette image et extrais toutes les tâches, actions et livrables visibles :"
            })

        # Ajouter l image en base64
        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{image_mime};base64,{image_data}"
            }
        })

        try:
            r = requests.post(
                GROQ_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":    GROQ_VISION_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user_content},
                    ],
                    "temperature": 0.3,
                    "max_tokens":  2048,
                },
                timeout=60,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()

            # Extraire le JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            tasks = json.loads(content)
            return tasks if isinstance(tasks, list) else [tasks]

        except json.JSONDecodeError as e:
            logger.error("VisionTaskParser: JSON invalide: %s", e)
            return [{"error": f"Réponse non parseable: {e}"}]
        except requests.exceptions.HTTPError as exc:
            try:
                err_detail = r.json().get("error", {}).get("message", str(exc))
            except Exception:
                err_detail = str(exc)
            logger.error("VisionTaskParser: HTTP %s: %s", r.status_code, err_detail)
            return [{"error": f"Erreur Groq vision: {err_detail}"}]
        except Exception as e:
            logger.error("VisionTaskParser: erreur: %s", e)
            return [{"error": str(e)}]
