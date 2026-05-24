FROM python:3.10-slim

WORKDIR /app

# Instalar dependências básicas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código-fonte do serviço
COPY . .

# Criar pasta para banco de dados vetorial local do Palácio da Memória
RUN mkdir -p memory_db

EXPOSE 5001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5001"]
