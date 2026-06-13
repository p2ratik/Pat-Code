FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
COPY Pat-Code/requirements.txt ./Pat-Code/requirements.txt
COPY Pat-Code ./Pat-Code

RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install -r Pat-Code/requirements.txt \
    && pip install -e .

EXPOSE 8000

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]