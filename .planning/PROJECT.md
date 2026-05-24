# 🎯 Projeto SaS_NeuroPsicopedagogia (GSD-AH/SD)

Sistema web completo para aplicação, gestão e diagnóstico neuropsicopedagógico de questionários de Altas Habilidades / Superdotação (AEE-AH/SD).

## 📌 Contexto do Projeto
Este projeto visa digitalizar e otimizar a avaliação de estudantes com suspeita de Altas Habilidades / Superdotação (AH/SD) para o Atendimento Educacional Especializado (AEE), integrando um formulário clínico robusto (105 campos sensíveis), gestão de usuários, dashboard administrativo e uma IA de Borda (Heuristic & Local Cognitive Profiler) para auxílio ao diagnóstico clínico pela Neuropsicopedagoga.

## 👥 Papéis e Atores
- **Neuropsicopedagoga (Administradora)**: Visualiza e analisa respostas, utiliza os gráficos de perfil cognitivo da IA de Borda, atribui pontuações, gerencia usuários e exporta relatórios.
- **Família / Estudante (Usuários)**: Preenchem o formulário detalhado na interface web (pública ou logada).

## 🛠️ Tecnologias Principais
- **Backend**: Flask
- **Autenticação**: Flask-Login + Flask-Bcrypt
- **Banco de Dados**: SQLite3 (migrando para Flask-SQLAlchemy para pooling e suporte a PostgreSQL/MySQL)
- **Frontend**: HTML5, CSS3 (Vanilla), JavaScript, Chart.js (gráficos interativos)
- **IA de Borda**: Mecanismo Heurístico de Diagnóstico Clínico + Gráfico de Radar de Multi-habilidades (Joseph Renzulli) rodando 100% no cliente/servidor local sem dependências de nuvem.

## 🔐 Requisitos de Segurança & LGPD
- **Dados Sensíveis**: Armazena histórico médico, familiar, comportamental e cognitivo de menores de idade.
- **Conformidade**: Requer criptografia de dados de identificação, trilha de auditoria (audit log), proteção contra CSRF e sessões HTTP seguras.
