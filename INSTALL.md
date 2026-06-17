# ProjectMind — Guide d installation

## Prérequis
- Python 3.12+
- Docker Desktop (pour le mode conteneur)
- Clé API Groq : https://console.groq.com

## Installation locale (sans Docker)

```bash
git clone https://github.com/beyp/ProjectMind
cd ProjectMind

# Environnement virtuel
python -m venv .venv
.venv\\Scripts\\activate   # Windows
# source .venv/bin/activate  # Linux/Mac

# Dépendances
pip install -r requirements.txt

# Configuration
cp .env.example .env
# Editer .env : GROQ_API_KEY, ADO_PAT

# Lancer
uvicorn main:app --host 0.0.0.0 --port 8766 --reload
```

Accès : http://localhost:8766

## Installation Docker

```bash
# Configurer
cp .env.example .env
# Editer .env

# Construire et lancer
docker-compose up -d

# Voir les logs
docker-compose logs -f projectmind
```

## Intégration AION

1. Copier `aion/services/projectmind_service.py` dans ton repo AION
2. Ajouter dans `.env` AION :
   ```
   PROJECTMIND_URL=http://localhost:8766
   ```
3. Dans AION :
   ```
   AION> run projectmind_status
   AION> domain add svc "Services applicatifs"
   ```

## Variables d environnement

| Variable | Description | Défaut |
|---|---|---|
| GROQ_API_KEY | Clé API Groq (gratuit) | — |
| GROQ_MODEL | Modèle Groq | llama-3.3-70b-versatile |
| ADO_PAT | Token Azure DevOps | — |
| ADO_ORG | Organisation ADO | Premiertech |
| SECRET_KEY | Clé secrète app | change_me |

## Structure des données

```
data/
  projectmind.db    ← SQLite (projets, tâches, KPIs...)
templates/
  weekly_template.pptx  ← Template PowerPoint
logs/
  *.log
```

## Fiscal Year
- Début : 1er mars
- Fin : 28/29 février  
- FY27-Q1 : 1 mars 2026 → 31 mai 2026
- FY27-Q2 : 1 juin 2026 → 31 août 2026
- FY27-Q3 : 1 sept 2026 → 30 nov 2026
- FY27-Q4 : 1 déc 2026 → 28 fév 2027
