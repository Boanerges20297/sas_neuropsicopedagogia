# Neuro-Diagnosis — Conta de acesso e paciente atendido
Data: 2026-11-07. Status: diretriz aprovada; formulário e modelo clínico implementados no STI01. Portal ainda bloqueado.

## Decisão
O titular da conta pode ser o próprio paciente adulto ou seu responsável legal quando o atendido é menor. Nunca criar obrigatoriamente duas contas de acesso para atender uma criança.

| Situação | Conta de acesso | Registro clínico |
|---|---|---|
| Adulto independente | Uma conta do próprio adulto | Um perfil de paciente |
| Menor de idade | Uma conta do responsável legal | Um perfil clínico do menor, sem login próprio |
| Dois menores com mesmo responsável | A mesma conta do responsável | Dois perfis clínicos, separados por criança |

**Uma conta não significa um único paciente.** Registros clínicos pertencem aos respectivos pacientes, isolados por profissional e tenant.

## Formulário profissional implementado
- Tipo: Adulto (responde por si) ou Menor (responsável legal).
- Dados do paciente: nome, data de nascimento (idade calculada, não estática) e observações iniciais sintomáticas.
- Menor: nome e e-mail opcional do responsável, no MESMO formulário; um contato interno é criado com status não verificado. Isso não cria outra conta de acesso.
- Adulto: e-mail opcional do próprio paciente. Nenhum contato de responsável é criado.
- Observações são relato inicial, não diagnóstico. São criptografadas em repouso usando Fernet e subchave HKDF com propósito distinto, derivada do SECRET_KEY; troca da chave exige migração/recifração controlada.
- Pacientes anteriores continuam acessíveis sem inventar dados de nascimento ou responsáveis.

## Tabelas
- clients: paciente atendido, nome, DOB e escopo de acesso profissional.
- care_patient_intakes: 1:1 com paciente, tipo de representação e relato criptografado; DOB permanece exclusivamente em clients; FK composta ao contato do responsável quando menor.
- care_client_contacts: vínculo do responsável com a criança, NÃO segunda identidade de login.
- users: identidade de login; não criar automaticamente usuários para menores.
- care_portal_identity_links / care_portal_grants: política preparada para responsáveis, sem portal liberado. **Adulto independente ainda requer fluxo próprio de autenticação, vínculo e autorização para portal.**

## Fluxo de portal FUTURO (não implementado)
Adulto: autenticar única conta, verificar identidade, vincular ao próprio paciente e conceder acesso estritamente por escopo e profissional.
Responsável: autenticar única conta, declarar criança, comprovar vínculo legal, obter autorização profissional por criança, escopo e validade; pode ter múltiplos filhos sem logins duplicados.
Nenhum e-mail coincidente concede acesso. Ao completar 18 anos, revisar os vínculos, revogar/revalidar grants e permitir eventual migração à autonomia, sem concessão automática.

## Segurança
Apenas profissional titular do paciente lê relato inicial. A rota exige sessão e licença, respeita tenant, e desabilita cache do detalhe. A equipe administrativa não ganha acesso ao relato clínico dos profissionais. Não enviar dados de saúde a sistemas de IA, BTA ou logs. Observações não podem ser interpretadas como diagnóstico.

## Validação e gates
- Homologar a migração aditiva no MySQL 8.4 do STI e todas as regras de integridade.
- Executar suíte completa de testes, simulações de adulto e menor e checagem de autorização cruzada.
- Verificação de vínculo legal, consentimentos e fluxo real de login único ainda pendentes, assim como revisão visual e clínica.
- Somente publicar após conciliar o script instalado na VPS e cumprir o pipeline canônico; não modificar o request de release nesta etapa.
