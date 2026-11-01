# Checkpoint — Neuro-Diagnosis Flask SaaS em produção

**Data:** 2026-11-01 (America/Fortaleza)  
**Estado:** implantação Flask concluída, Django legado removido definitivamente da VPS.  
**Repositório canônico:** `Boanerges20297/sas_neuropsicopedagogia`, branch `main`.  
**Commit da aplicação verificado na VPS antes deste checkpoint:** `80a9cb3bf4fdbaef384a4891bf0679899624367f`.

## Decisões consolidadas

- A aplicação oficial é **Flask + Gunicorn + MySQL**, integrada ao **BTA License Platform**.
- **Django foi descontinuado e removido**, por solicitação expressa do responsável pelo projeto.
- Os dados antigos eram **exclusivamente de teste**; não há pacientes reais legados a migrar.
- O primeiro administrador SaaS foi inicializado no MySQL mediante transferência cifrada do hash bcrypt da conta administrativa de teste do notebook. A senha em texto puro não foi exposta.
- O profissional se cadastra inicialmente inativo, precisa de aprovação administrativa e pode receber **trial BTA de 14 dias**, conforme emissão real da BTA.
- A conta administrativa SaaS tem acesso permanente independente de licença BTA, sem acesso irrestrito a tenants de terceiros.

## Implantação atual

| Item | Localização / situação |
|---|---|
| VPS — código | `/opt/neuro-diagnosis` |
| Compose Flask | `/opt/neuro-diagnosis/docker-compose.saas.yml` |
| Compose project | `neuro-flask` |
| Container Flask | `neuro-diagnosis-flask`: **healthy** |
| Porta interna de teste | `127.0.0.1:8781 -> container:8000` |
| Domínios HTTPS | `https://neuro-diagnosis.tech` e `https://www.neuro-diagnosis.tech` |
| Traefik | roteador dedicado `neuro-flask`, prioridade 1000, ativo |
| MySQL compartilhado preservado | `neuro-diagnosis-db`: **healthy** |
| Banco SaaS | `neuro_diagnosis` |
| BTA | `bta-license-api`, rede `bta-license-s2s` |
| SQLite de apoio do Flask | volume Docker `neuro-flask_neuro_data`, migração concluída |
| Configuração sensível | `/etc/neuro-diagnosis/flask.env` e `/etc/neuro-diagnosis/keys` (não versionar nem imprimir conteúdos) |
| Alternância Traefik | `NEURO_TRAEFIK_ENABLED=true` no `.env` local da VPS (ignorado pelo Git) |

## Verificações comprovadas na VPS

- `https://neuro-diagnosis.tech/health/live` → HTTP **200**.
- `https://neuro-diagnosis.tech/health/ready` → HTTP **200**.
- `https://neuro-diagnosis.tech/saas/saude` → HTTP **200** (MySQL).
- `https://neuro-diagnosis.tech/saas/entrar` → HTTP **200**, certificado válido (`ssl_verify_result=0`).
- `https://www.neuro-diagnosis.tech/saas/cadastro` → HTTP **200**, certificado válido.
- `/` → HTTP **302** para `/saas/entrar`.
- Rotas antigas em `SAAS_PRIMARY=true` são redirecionadas ou desativadas.
- O teste integrado `scripts/smoke_saas.py`, executado no container com dados sintéticos, retornou `SMOKE_OK`: profissional inicialmente pendente, aprovação administrativa, trial BTA ativo e páginas de profissional acessíveis.
- Comunicação Ed25519 S2S com a BTA testada. A ausência de licença para uma identidade fictícia foi reconhecida corretamente como `license_not_found`.
- Suíte unitária no notebook: **25 testes aprovados** após a última correção de teste de arquivo temporário no Windows.

## Exclusão definitiva do Django legado — comprovada

- Container `neuro-diagnosis-app`: parado e removido.
- Container `neuro-diagnosis-ai` (IA antiga associada ao Django): parado e removido.
- Imagens `neuro-diagnosis-app:latest` e `neuro-diagnosis-ai:latest`: removidas.
- Volumes exclusivos `neuro-diagnosis_neuro-diagnosis-static` e `neuro-diagnosis_neuro-diagnosis-ai-memory`: removidos.
- Diretório `/home/neuro-diagnosis`: removido.
- Banco MySQL legado de testes `neuro_diagnosis_db`: excluído; verificação posterior mostrou apenas `neuro_diagnosis` entre os dois schemas da aplicação.
- **Preservados intencionalmente**: container `neuro-diagnosis-db`, seu volume de dados `neuro-diagnosis_neuro-diagnosis-mysql-data`, e a rede `neuro-diagnosis_neuro-diagnosis-network`, porque o Flask depende deles.
- Verificação final após a exclusão: diretório legado ausente, nenhum container `neuro-diagnosis-app`/`neuro-diagnosis-ai`, nenhuma imagem/volume legado exclusivo, Flask e MySQL ambos **healthy**, login HTTPS **200** com certificado válido.

## Fluxo operacional

```text
HTTPS -> Traefik (neuro-flask) -> Gunicorn/Flask :8000
                                          |-> MySQL neuro_diagnosis
                                          |-> BTA License Platform (Ed25519 S2S)
                                          |-> SQLite auxiliar em volume próprio
```

Atualização canônica: push na `main` -> `git pull --ff-only origin main` em `/opt/neuro-diagnosis` -> `docker compose -f docker-compose.saas.yml build web` -> `docker compose -f docker-compose.saas.yml up -d web` -> validar saúde interna e HTTPS externo. Os comandos privilegiados exigem autorização específica do NEXO.

**Atenção:** não executar `docker compose down -v` no projeto antigo ou `docker volume prune` sem verificar dependências. Não remover o container MySQL nem o volume compartilhado. A remoção do Django foi definitiva; reconstruí-lo demandaria nova implantação e não faz parte do plano.
