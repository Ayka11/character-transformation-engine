FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    CTE_RUNTIME_DB=/tmp/cte-runtime.sqlite3

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

EXPOSE 7860

CMD ["uvicorn", "cte.api:app", "--app-dir", "/app/backend", "--host", "0.0.0.0", "--port", "7860"]
