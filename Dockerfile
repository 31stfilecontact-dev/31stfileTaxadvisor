FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY data ./data
COPY scripts ./scripts
COPY alembic.ini ./alembic.ini

EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]