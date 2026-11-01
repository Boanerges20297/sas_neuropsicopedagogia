FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt requirements.production.txt ./
RUN python -m pip install --no-cache-dir -r requirements.production.txt
RUN groupadd -g 10001 neuro && useradd -u 10001 -g neuro -r -M neuro
COPY --chown=neuro:neuro app.py schema.py account_management.py bta_license_client.py saas_routes.py saas_scope.py saas_store.py ./
COPY --chown=neuro:neuro templates/ ./templates/
COPY --chown=neuro:neuro static/ ./static/
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2", "--timeout", "60", "app:app"]
