FROM python:3.12-slim

WORKDIR /app/parser

ENV PIP_DEFAULT_TIMEOUT=200 \
    PIP_RETRIES=10 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

COPY parser/requirements.txt ./
RUN pip install --no-cache-dir --timeout 200 --retries 10 -r requirements.txt

COPY parser/app.py ./app.py

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8081
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081"]
