FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY config ./config
COPY materials ./materials
COPY prompts/ ./prompts/

COPY alembic.ini ./alembic.ini
COPY migrations ./migrations

CMD ["python", "-m", "app"]