class ProjectMindAgent:
    def __init__(self, groq_api_key: str):
        self.groq_api_key = groq_api_key

    def run(self, project_context: dict, user_text: str, image_data: str = "", image_mime: str = "") -> dict:
        """
        Retourne toujours :
        {
            "actions": [...],
            "message": "...",
            "raw": "..."
        }
        """