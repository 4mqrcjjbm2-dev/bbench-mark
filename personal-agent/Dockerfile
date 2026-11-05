# Jarvis — image du serveur (Python + polices Unicode pour les PDF + git pour le Cerveau)
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core git curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent ./agent
ENV AGENT_DATA_DIR=/data AGENT_ATELIER=/atelier PYTHONUNBUFFERED=1
EXPOSE 8787
CMD ["uvicorn", "agent.server:app", "--host", "0.0.0.0", "--port", "8787"]
