FROM python:3.12-slim

WORKDIR /app/telegrambot

ENV PIP_DEFAULT_TIMEOUT=200 \
    PIP_RETRIES=10 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt ./
RUN pip install --no-cache-dir --timeout 200 --retries 10 -r requirements.txt

COPY bot ./bot

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

CMD ["python3", "-m", "bot"]
