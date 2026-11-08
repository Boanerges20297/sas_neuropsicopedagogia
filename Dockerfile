FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt requirements.production.txt ./
RUN python -m pip install --no-cache-dir -r requirements.production.txt
RUN groupadd -g 10001 neuro && useradd -u 10001 -g neuro -r -M neuro
COPY --chown=neuro:neuro app.py schema.py account_management.py bta_license_client.py saas_routes.py saas_scope.py saas_store.py saas_profile_data.py saas_profile_routes.py saas_neurocore_routes.py saas_neurocore_store.py saas_admin_workspace.py saas_care_routes.py saas_care_store.py saas_portal_policy.py saas_patient_intake.py saas_patient_intake_routes.py saas_portal_activation.py saas_portal_activation_routes.py saas_portal_activation_queue.py saas_account_access.py saas_account_provision.py saas_account_admin_routes.py saas_login_policy.py saas_email_otp_transport.py saas_mfa.py saas_mfa_store.py saas_mfa_routes.py saas_login_recovery.py saas_login_recovery_routes.py saas_smtp_settings.py saas_smtp_admin_routes.py ./
COPY --chown=neuro:neuro neurocore/ ./neurocore/
COPY --chown=neuro:neuro templates/ ./templates/
COPY --chown=neuro:neuro static/ ./static/
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "2", "--timeout", "60", "app:app"]
