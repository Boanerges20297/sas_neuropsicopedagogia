FROM python:3.10-slim

WORKDIR /code

# Instalar dependências do sistema para o mysqlclient
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar projeto
COPY . .
RUN chmod +x /code/entrypoint.sh

# Expõe a porta do Django/Gunicorn
EXPOSE 8000

CMD ["/code/entrypoint.sh"]
