"""Parse du texte brut en taches structurees via Groq."""
import json
import logging
import os

import requests

logger   = logging.getLogger(__name__)
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL    = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = """Tu es un assistant de gestion de projet pour Premier Tech.
Tu analyses du texte brut (notes, emails, messages) et le structures en taches.
Reponds UNIQUEMENT avec un JSON valide, sans texte avant ou apres.

Format exact :
{
  "categories": [
    {
      "name": "Nom de la categorie",
      "deliverables": [
        {
          "title": "Titre du livrable",
          "status": "in_progress|done|to_plan|blocked|late|cancelled",
          "due_date": "YYYY-MM-DD ou null",
          "tasks": [
            {
              "title": "Titre de la tache",
              "status": "to_plan",
              "start_date": null,
              "end_date": null,
              "assignee": null,
              "completion_pct": 0
            }
          ]
        }
      ]
    }
  ],
  "summary": "Resume executif 2-3 phrases",
  "watch_items": ["item1"],
  "risks": ["risque1"]
}

Regles :
- Regroupe par categorie logique (OCM, TI, Cegedim, Dayforce WFM, etc.)
- Infere le statut depuis le contexte
- Reponds dans la langue du texte fourni
- Utilise les categories existantes si mentionnees
"""


def parse_text_to_tasks(
    text:                str,
    existing_categories: list[str] | None = None,
    language:            str = "fr",
    project_name:        str = "",
) -> dict:
    """Parse du texte brut en structure de taches via Groq."""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return {"error": "GROQ_API_KEY non configuree"}

    context  = f"Projet : {project_name}\n" if project_name else ""
    context += f"Categories existantes : {', '.join(existing_categories)}\n" if existing_categories else ""
    context += "Reponds en francais.\n" if language == "fr" else "Respond in English.\n"

    try:
        r = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model":    MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": f"{context}\nTexte :\n{text}"},
                ],
                "temperature": 0.3,
                "max_tokens":  2048,
            },
            timeout=30,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        return json.loads(content)

    except json.JSONDecodeError as e:
        return {"error": f"Reponse IA invalide : {e}"}
    except Exception as e:
        logger.error("task_parser error: %s", e)
        return {"error": str(e)}
