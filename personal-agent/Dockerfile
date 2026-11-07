# Jarvis — image du serveur (Python + polices Unicode pour les PDF + git pour le Cerveau et l'auto-évolution)
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core git curl \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*'
WORKDIR /repo/personal-agent
COPY requirements.txt requirements-dev.txt ./
# pytest est nécessaire : Jarvis teste chaque évolution de son propre code avant de l'appliquer.
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY agent ./agent
COPY tests ./tests
ENV AGENT_DATA_DIR=/data AGENT_ATELIER=/atelier JARVIS_SOURCE=/repo/personal-agent PYTHONUNBUFFERED=1
EXPOSE 8787
CMD ["uvicorn", "agent.server:app", "--host", "0.0.0.0", "--port", "8787"]
