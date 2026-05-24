# Estratégia de Teste e Validação

Este documento descreve como o sistema é testado e verificado.

## 🤖 Testes Automatizados

* **Estado Atual**: Praticamente inexistente. O arquivo `avaliacao/tests.py` contém apenas a estrutura padrão vazia criada pelo Django.
* **Necessidade**: Implementar testes unitários para a criptografia/descriptografia de dados (LGPD) e testes de integração para chamadas da API do FastAPI.

## 🧪 Testes de Smoke e Manuais

Existem scripts utilitários em `scripts/` para automação de testes rápidos via terminal:

1. **`remote_test_login.py`**: Simula login HTTP para garantir que a autenticação esteja funcionando.
2. **`remote_smoke_clinic_area.py`**: Realiza requisições para a área clínica e verifica se o código retorna HTTP 200.

## 💻 Ambiente de Teste Local

Para rodar e testar localmente:
1. Instale as dependências: `pip install -r requirements.txt`
2. Certifique-se de que `USE_SQLITE=True` está no seu `.env`
3. Execute migrações: `python manage.py migrate`
4. Rode o app: `python manage.py runserver 8000`
5. Rode a IA (FastAPI): `uvicorn ai_service.main:app --port 5001` (na pasta `ai_service`)
