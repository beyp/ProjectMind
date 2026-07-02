from services.project_context import ProjectContext
from services.prompt_builder import PromptBuilder

class ProjectMindAgent:
    def __init__(self, groq_api_key: str):
        self.groq_api_key = groq_api_key
        self.prompt_builder = PromptBuilder()

    def run(
        self,
        project: ProjectContext,
        user_text: str,
        image_data: str = "",
        image_mime: str = "",
    ) -> dict:
        prompt = self.prompt_builder.build(project, user_text)

        response = self._call_llm(prompt)

        actions = self._parse_response(response)

        # TODO: brancher Groq texte/vision ici
        return {
            "actions": actions,
            "message": "",
            "raw": prompt,
        }