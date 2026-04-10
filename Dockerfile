FROM python:3.13-slim

WORKDIR /app

# Copie uniquement les fichiers nécessaires à l'installation des dépendances
COPY pyproject.toml .

# Installation des dépendances sans créer de venv (on est déjà dans le container)
RUN pip install --no-cache-dir -e .

# Copie du code source
COPY src/ src/

EXPOSE 8000

CMD ["uvicorn", "sharetrip.main:app", "--host", "0.0.0.0", "--port", "8000"]
