FROM python:3.12-slim

WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code source
COPY . .

# Créer les dossiers nécessaires
RUN mkdir -p data logs templates/static

EXPOSE 8766

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8766"]
