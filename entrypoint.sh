#!/bin/sh
set -e

echo "Aguardando banco de dados MySQL..."
sleep 8

echo "Executando migrações Django..."
python manage.py migrate --noinput

echo "Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo "Criando admin inicial (se não existir)..."
python create_admin.py || true

echo "Iniciando aplicação Django com Gunicorn..."
exec gunicorn neuro_diagnosis.wsgi:application --bind 0.0.0.0:8000 --workers 3
