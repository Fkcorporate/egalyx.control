# Egalyx Control — image pour une installation chez un client (on-premise).
# Construite par docker-compose.yml ; voir deploiement/on-premise/GUIDE_INSTALLATION.md
FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# pg_dump (sauvegardes de nuit), Pango (rapport PDF « élégant » avec WeasyPrint), polices, curl (contrôle de santé)
RUN apt-get update && apt-get install -y --no-install-recommends \
        postgresql-client libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
        fonts-dejavu-core fonts-liberation curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt && pip install "weasyprint>=62"

COPY . .

# l'application ne tourne pas en administrateur du conteneur
RUN useradd --uid 1000 --create-home egalyx \
    && mkdir -p /donnees /sauvegardes /app/instance /app/logs /app/uploads \
    && chown -R egalyx:egalyx /app /donnees /sauvegardes
USER egalyx

ENV EGALYX_PRODUCTION=1 \
    EGALYX_LICENCE_REQUISE=1 \
    EGALYX_DONNEES=/donnees \
    EGALYX_DOSSIER_SAUVEGARDES=/sauvegardes

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

# un seul processus (plusieurs fils) : les tâches planifiées (alertes, résumés, sauvegarde de nuit) ne tournent qu'une fois
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000", "--workers=1", "--threads=8", "--worker-class=gthread", "--timeout=120", "--access-logfile", "-"]
