# Checkpoint — NeuroCore TEA/TDAH, 02/11/2026

Projeto: sas_neuropsicopedagogia no STI01; main local sincronizada com origin/main antes das alterações.

## Objetivo
Iniciar o motor experimental leve de apoio à organização documental de avaliações de TEA e TDAH, com referências científicas e treinamento OFFLINE de índice textual no STI.

## Entregas
- neurocore/knowledge.json: 2 tópicos, 16 itens documentais, 6 referências verificadas (NICE, CDC, AAP e revisão TEA/TDAH). Estado: requer curadoria da profissional administradora.
- neurocore/engine.py: conferência de lacunas de informação, fontes, estados válidos e justificativas. Não calcula diagnóstico ou risco.
- neurocore/train_index.py: TF-IDF em scikit-learn sobre resumos originais e metadados bibliográficos.
- neurocore/index.json: índice compacto de 14.500 bytes, 231 termos/expressões, gerado no STI; inferência só com biblioteca padrão Python.
- neurocore/retrieval.py: busca por referências com filtro TEA/TDAH e sem persistência de consultas.
- tests/test_neurocore.py: 8 testes unitários de isolamento de tópicos, segurança e busca de fontes.
- NEUROCORE_TEA_TDAH_V0.md: escopo, referências e limitações.
- requirements.neurocore-dev.txt: scikit-learn só no ambiente de treinamento.

## Validações já confirmadas
Ambiente do STI: Python 3.14, NumPy 2.5.4 cp314 e scikit-learn 1.9.1. Houve correção do NumPy instalado previamente para alinhar a arquitetura da biblioteca binária ao interpretador.
Treinamento concluiu com NEUROCORE_INDEX_OK.
8 testes específicos executados com sucesso.

## Segurança e delimitações
Não houve ingestão do texto do DSM, instrumentos protegidos, prontuários ou dados sensíveis.
O treinamento é apenas de recuperação de referências; não classifica pacientes.
Não existem APIs clínicas, integração com contas reais ou mudanças de permissão/BTA.
Nenhuma publicação foi requisitada pelo pipeline; a produção segue sem alterações.
Pendente: revisão pela especialista, validação com casos sintéticos mais abrangentes e recuperação do fluxo funcional do espaço profissional.
