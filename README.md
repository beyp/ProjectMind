# ProjectMind

**AI-Powered Project Management**

ProjectMind est un gestionnaire de projets intelligent qui combine :
- 📊 **Vue Weekly Status** — tableau de suivi par catégories et livrables
- 📅 **Vue Gantt** — chronologie avec Fiscal Year (début 1er mars)
- 🤖 **IA Groq** — structuration automatique des tâches par chat
- 🔵 **Sync Azure DevOps** — liaison par ID item + project + area path
- 📄 **Export PowerPoint** — one-pager weekly status automatique
- 🌐 **Multi-projets** — gestion de plusieurs projets simultanément
- 🇫🇷🇬🇧 **Multi-langues** — FR/EN par projet

## Stack technique
- **Backend** : FastAPI + SQLite
- **Frontend** : htmx + Jinja2
- **IA** : Groq llama-3.3-70b-versatile
- **Gantt** : dhtmlxGantt
- **Export** : python-pptx
- **Docker** : port 8766

## Démarrage rapide

```bash
# Copier et configurer l'environnement
cp .env.example .env
# Editer .env avec vos clés

# Docker
docker-compose up -d

# Ou local
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8766 --reload
```

## Accès
- Dashboard : http://localhost:8766
- API Docs  : http://localhost:8766/docs

## Fiscal Year
- Début : 1er mars  
- Fin : 28/29 février
- Exemple : FY27-Q1 = 1 mars 2026 → 31 mai 2026

## Statuts disponibles
| FR | EN |
|---|---|
| En cours | In Progress |
| Réalisé | Completed |
| A planifier | To Plan |
| Bloqué | Blocked |
| Annulé | Cancelled |
| En retard | Delayed |
| En revue | In Review |
