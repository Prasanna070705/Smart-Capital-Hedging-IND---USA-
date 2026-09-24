# Dockerfile: the hedging advisor as one container.
# Build:  docker build -t fx-hedging:1.1 .
# Run:    docker run --rm -p 8501:8501 --env-file .env fx-hedging:1.1     (chat on, if .env has CHAT_API_KEY)
#         docker run --rm -p 8501:8501 fx-hedging:1.1                     (offline mode: no chat)
FROM python:3.14-slim

# No .pyc files, unbuffered logs, and Streamlit settings for running inside a container
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# Dependencies first, so this slow layer is reused when only the code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The app: code, committed data snapshot, trained models and outputs (see .dockerignore for what's left out)
COPY . .

# Fail the build if any test fails (the app tests run headless; the chatbot is tested offline)
RUN python -m unittest discover tests

# Run as a normal user, not root
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=4)"

CMD ["streamlit", "run", "app.py"]
