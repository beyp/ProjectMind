## ProjectMindAgent

Main project copilot.

Responsibilities:
- Understand project context
- Return structured actions only
- Use ProjectActionExecutor for database changes
- Never access SQLite directly
- Never create tasks when the user asks to update/delete risks, milestones, categories, resources, or capacity