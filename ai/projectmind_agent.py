import json
import requests

from ai.task_parser import GROQ_URL, GROQ_VISION_MODEL
from services.project_context import ProjectContext
from services.prompt_builder import PromptBuilder


class ProjectMindAgent:
    def __init__(self, groq_api_key: str):
        self.groq_api_key = groq_api_key
        self.prompt_builder = PromptBuilder()

    def run(
        self,
        context,
        user_text: str,
        image_data: str = "",
        image_mime: str = "",
    ) -> dict:
        prompt = self.prompt_builder.build(context, user_text)
        try:
            raw = self._call_llm(prompt, image_data, image_mime)
            actions = self._parse_actions(raw)
        except Exception as exc:
            return {
                "actions": [
                    {
                        "type": "message",
                        "text": f"Erreur IA : {exc}",
                        "executed": False,
                    }
                ],
                "message": f"Erreur IA : {exc}",
                "raw": "",
            }

        return {
            "actions": actions,
            "message": self._extract_message(actions),
            "raw": raw,
        }

    def _call_llm(self, prompt: str, image_data: str = "", image_mime: str = "") -> str:
        if not self.groq_api_key:
            raise ValueError("GROQ_API_KEY non configurée")

        if image_data:
            model = GROQ_VISION_MODEL
            user_content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{image_data}"}},
            ]
        else:
            model = "llama-3.3-70b-versatile"
            user_content = prompt

        response = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.2,
                "max_tokens": 2048,
            },
            timeout=30,
        )
        if response.status_code == 429:
            raise RuntimeError("Limite Groq atteinte. Réessaie dans quelques secondes.")

        response.raise_for_status()

        return response.json()["choices"][0]["message"]["content"].strip()

    def _parse_actions(self, raw: str) -> list[dict]:
        cleaned = raw.strip()

        if "```json" in cleaned:
            cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()

        data = json.loads(cleaned)

        if isinstance(data, dict):
            return data.get("actions", [data])

        if isinstance(data, list):
            return data

        return [{"type": "message", "text": "Réponse IA non exploitable."}]

    def _extract_message(self, actions: list[dict]) -> str:
        for action in actions:
            if action.get("type") == "message":
                return action.get("text", "")
        return ""