# NeuroCore v0.1 — TEA e TDAH (STI, 02/11/2026)

Estado: protótipo experimental no STI01, ainda não publicado nem incorporado ao atendimento.

O primeiro motor organiza evidências de avaliações e indica documentos ou informações pendentes. O recuperador bibliográfico usa TF-IDF treinado no STI com scikit-learn sobre seis resumos ORIGINAIS e metadados de referências. O runtime usa apenas Python padrão e um índice JSON; nenhum caso real é usado para treinamento.

Referências rastreáveis: NICE CG128, NICE NG87, CDC TEA, CDC TDAH, AAP ADHD 2019 (PMID 31570648) e revisão sobre TEA+TDAH 2023 (PMID 37065905). Textos integrais, DSM e instrumentos protegidos NÃO foram importados. Verificar licença por obra antes de qualquer incorporação.

Nenhum diagnóstico, probabilidade, pontuação clínica, predição de risco ou prescrição é gerado. A revisão da administradora é necessária para validar campos e terminologia. O protótipo não captura dados de pacientes.

Comandos no STI, dentro da raiz do projeto:
- python -m neurocore.train_index
- python -m unittest discover -s tests -p test_neurocore.py -v
- python -m unittest discover -s tests -q

Antes de integrar: consertar fluxos do espaço profissional, revisar autorização e isolamento por tenant; validar vocabulário e fontes com a profissional habilitada; criar protocolo de avaliação de segurança com casos sintéticos. Publicação somente pelo pipeline canônico mediante release aprovada. Sem mudar BTA ou a versão em produção.
