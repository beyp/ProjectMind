"""
TaskParser - Analyse du texte libre et des images via Groq.
"""
import json
import logging
import os
import base64 as _b64
import requests

logger = logging.getLogger(__name__)

GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

GROQ_VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "llama-4-scout",
    "llama-3.2-90b-vision-preview",
    "llama-3.2-11b-vision-preview",
]
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", GROQ_VISION_MODELS[0])

SYSTEM_PROMPT_FR = """Tu es un assistant de gestion de projets expert.
Analyse du texte brut et extrais une liste structuree de taches.

Pour chaque tache, fournis un JSON avec :
- "category" : categorie/livrable (ex: OCM, TI, Discovery, Kick-off)
- "title" : titre court de la tache (max 80 caracteres)
- "status" : parmi [En cours, Realise, A planifier, Bloque, En retard, En revue]
- "date_label" : date ou periode si mentionnee (ex: "17/06", "Juin", "S21", "TBD")
- "description" : detail optionnel
- "ado_item_id" : ID Azure DevOps si mentionne (nombre uniquement, null sinon)

Reponds UNIQUEMENT avec un tableau JSON valide, sans texte avant ou apres."""

SYSTEM_PROMPT_EN = """You are an expert project management assistant.
Analyze raw text and extract a structured list of tasks.

For each task, provide a JSON with:
- "category" : category/deliverable (ex: OCM, IT, Discovery, Kick-off)
- "title" : short task title (max 80 chars)
- "status" : from [In Progress, Completed, To Plan, Blocked, Delayed, In Review]
- "date_label" : date or period if mentioned (ex: "Jun 17", "June", "W21", "TBD")
- "description" : optional detail
- "ado_item_id" : Azure DevOps ID if mentioned (number only, null otherwise)

Reply ONLY with a valid JSON array, no text before or after."""

RESTRUCTURE_PROMPT_FR = """Tu es un assistant de gestion de projets.
Restructure la liste de taches en regroupant par categories logiques.
Retourne UNIQUEMENT le JSON restructure, meme format qu en entree."""

VISION_SYSTEM_PROMPT_FR = """Tu es un expert en gestion de projets qui analyse des images de plannings.

INSTRUCTIONS CRITIQUES :
1. Extrais CHAQUE tache, activite ou livrable visible dans l image
2. Pour un Gantt/Excel : chaque barre coloree = une tache distincte
3. Pour un slide de phases : chaque bullet point = une tache distincte
4. Pour une timeline : chaque bloc colore = une tache distincte
5. Liste toutes les taches individuellement - ne regroupe pas
6. Utilise le texte exact visible comme titre

Pour chaque element, cree un objet JSON avec :
- "category" : la categorie/phase/stream visible (ex: Discovery, Kick-off, Milestones, Functional, Technical, Change)
- "title" : le texte exact visible dans la barre ou le bloc
- "status" : "Realise" si dans le passe, "En cours" si actif, "A planifier" si futur
- "date_label" : periode visible (ex: "S21", "Juin", "FY-Q2", "TBD")
- "description" : tout detail supplementaire visible
- "ado_item_id" : null

REPONDS UNIQUEMENT AVEC UN TABLEAU JSON VALIDE. Minimum 5 elements pour un planning."""

VISION_SYSTEM_PROMPT_EN = """You are a project management expert who analyzes planning images.

CRITICAL INSTRUCTIONS:
1. Extract EVERY task, activity or deliverable visible in the image
2. For Gantt/Excel: each colored bar = one distinct task
3. For phase slides: each bullet point = one distinct task
4. For timelines: each colored block = one distinct task
5. List all tasks individually - do not group them
6. Use the exact visible text as the title

For each element, create a JSON object with:
- "category" : the visible category/phase/stream
- "title" : the exact text visible in the bar or block
- "status" : "Completed" if past, "In Progress" if active, "To Plan" if future
- "date_label" : visible period (ex: "W21", "June", "FY-Q2", "TBD")
- "description" : any additional visible detail
- "ado_item_id" : null

REPLY ONLY WITH A VALID JSON ARRAY. Minimum 5 elements for a planning."""


class TaskParser:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")

    def parse_text(self, text: str, language: str = "fr") -> list:
        if not self.api_key:
            return [{"error": "GROQ_API_KEY non configuree"}]
        system = SYSTEM_PROMPT_FR if language == "fr" else SYSTEM_PROMPT_EN
        try:
            r = requests.post(GROQ_URL,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": GROQ_MODEL, "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": f"Analyse ce texte :\n\n{text}"}],
                    "temperature": 0.2, "max_tokens": 4096},
                timeout=30)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            tasks = json.loads(content)
            return tasks if isinstance(tasks, list) else [tasks]
        except json.JSONDecodeError as e:
            logger.error("TaskParser JSON: %s", e)
            return [{"error": f"Reponse non parseable: {e}"}]
        except Exception as e:
            logger.error("TaskParser: %s", e)
            return [{"error": str(e)}]

    def restructure_tasks(self, tasks: list, language: str = "fr") -> list:
        if not self.api_key or not tasks:
            return tasks
        try:
            r = requests.post(GROQ_URL,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": GROQ_MODEL, "messages": [
                    {"role": "system", "content": RESTRUCTURE_PROMPT_FR},
                    {"role": "user",   "content": json.dumps(tasks, ensure_ascii=False)}],
                    "temperature": 0.4, "max_tokens": 4096},
                timeout=30)
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


class VisionTaskParser:
    """Parse des images via Groq vision avec fallback automatique sur plusieurs modeles."""

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")

    def _try_model(self, model: str, messages: list) -> tuple:
        """Essaie un modele. Retourne (succes:bool, contenu:str)."""
        try:
            r = requests.post(GROQ_URL,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "temperature": 0.1, "max_tokens": 4096},
                timeout=60)
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"]["content"].strip()
                logger.info("VisionTaskParser: modele %s OK", model)
                return True, content
            err = r.json().get("error", {}).get("message", f"HTTP {r.status_code}")
            logger.warning("VisionTaskParser: modele %s -> %s", model, err)
            return False, err
        except Exception as e:
            logger.warning("VisionTaskParser: modele %s exception: %s", model, e)
            return False, str(e)

    def _compress_image(self, image_data: str, image_mime: str) -> tuple:
        """Compresse l image si > 3MB. Retourne (image_data, image_mime)."""
        try:
            decoded = _b64.b64decode(image_data)
            size_mb = len(decoded) / (1024 * 1024)
            if size_mb <= 3.0:
                return image_data, image_mime
            logger.info("VisionTaskParser: image %.1fMB, compression...", size_mb)
            from io import BytesIO
            from PIL import Image as PILImage
            img = PILImage.open(BytesIO(decoded))
            max_size = 1600
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                img = img.resize((int(img.size[0]*ratio), int(img.size[1]*ratio)), PILImage.LANCZOS)
            buf = BytesIO()
            img = img.convert("RGB")
            img.save(buf, format="JPEG", quality=85)
            compressed = _b64.b64encode(buf.getvalue()).decode()
            logger.info("VisionTaskParser: %.1fMB -> %.1fMB", size_mb, len(buf.getvalue())/(1024*1024))
            return compressed, "image/jpeg"
        except ImportError:
            logger.warning("VisionTaskParser: PIL non disponible")
            return image_data, image_mime
        except Exception as e:
            logger.warning("VisionTaskParser: compression: %s", e)
            return image_data, image_mime

    def _extract_json(self, content: str) -> list:
        """Extrait et parse le JSON de la reponse."""
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            parts = content.split("```")
            if len(parts) >= 2:
                content = parts[1].strip()
                if content.startswith("json"):
                    content = content[4:].strip()
        # Extraire le tableau JSON si du texte precede/suit
        start = content.find("[")
        end   = content.rfind("]")
        if start >= 0 and end > start:
            content = content[start:end+1]
        parsed = json.loads(content)
        return parsed if isinstance(parsed, list) else [parsed]

    def parse_image(self, image_data: str, image_mime: str = "image/jpeg",
                    text_context: str = "", language: str = "fr") -> list:
        if not self.api_key:
            return [{"error": "GROQ_API_KEY non configuree"}]

        system = VISION_SYSTEM_PROMPT_FR if language == "fr" else VISION_SYSTEM_PROMPT_EN

        # Compression si image trop grande
        image_data, image_mime = self._compress_image(image_data, image_mime)

        user_text = (
            f"Contexte : {text_context}\n\n" if text_context.strip() else ""
        ) + "Analyse cette image de planning et extrais TOUTES les taches en JSON :"

        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": [
                {"type": "text",      "text": user_text},
                {"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{image_data}"}},
            ]},
        ]

        # Essayer les modeles dans l ordre avec fallback
        models = [GROQ_VISION_MODEL] + [m for m in GROQ_VISION_MODELS if m != GROQ_VISION_MODEL]
        last_error = "Aucun modele disponible"

        for model in models:
            ok, content = self._try_model(model, messages)
            if not ok:
                last_error = content
                continue
            try:
                tasks = self._extract_json(content)
                logger.info("VisionTaskParser: %d taches extraites avec %s", len(tasks), model)
                return tasks
            except json.JSONDecodeError as e:
                logger.warning("VisionTaskParser JSON %s: %s | %.200s", model, e, content)
                last_error = f"JSON invalide: {e}"

        logger.error("VisionTaskParser: echec total. Dernier: %s", last_error)
        return [{"error": f"Echec vision: {last_error}"}]
