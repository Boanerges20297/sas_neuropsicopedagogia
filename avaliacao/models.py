from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import datetime
from .security_utils import encrypt_data, decrypt_data

# ==================== PERFIL DO USUÁRIO ====================
class PerfilUsuario(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Administrador (Neuropsicopedagoga)'),
        ('user', 'Usuário Comum'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    data_nascimento = models.CharField(max_length=20, blank=True, null=True)
    escolaridade = models.CharField(max_length=100, blank=True, null=True)
    telefone = models.CharField(max_length=30, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_admin(self):
        return self.role == 'admin'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

# Removidas tabelas de testes legadas (CategoriaTeste, Teste) em favor de Pacientes e Atendimentos


# ==================== PACIENTES E ATENDIMENTOS ====================
class Paciente(models.Model):
    nome = models.TextField()
    data_nascimento = models.CharField(max_length=20, blank=True, null=True)
    responsavel = models.TextField(blank=True, null=True)
    telefone = models.TextField(blank=True, null=True)
    email = models.TextField(blank=True, null=True)
    escola = models.CharField(max_length=200, blank=True, null=True)
    serie = models.CharField(max_length=80, blank=True, null=True)
    queixa_principal = models.TextField(blank=True, null=True)
    observacoes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    SENSITIVE_FIELDS = [
        'nome', 'responsavel', 'telefone', 'email', 'queixa_principal', 'observacoes'
    ]

    def save(self, *args, **kwargs):
        for field in self.SENSITIVE_FIELDS:
            val = getattr(self, field, '')
            if val and not str(val).startswith('gAAAAA'):
                setattr(self, field, encrypt_data(str(val)))
        super().save(*args, **kwargs)

    def decrypt_sensitive(self):
        for field in self.SENSITIVE_FIELDS:
            val = getattr(self, field, '')
            if val and str(val).startswith('gAAAAA'):
                setattr(self, field, decrypt_data(val))

    def __str__(self):
        nome_real = decrypt_data(self.nome) if self.nome and self.nome.startswith('gAAAAA') else self.nome
        return nome_real or f"Paciente #{self.id}"


class AnotacaoAtendimento(models.Model):
    TIPO_CHOICES = (
        ('sessao', 'Sessao'),
        ('observacao', 'Observacao'),
        ('orientacao', 'Orientacao familiar/escolar'),
        ('encaminhamento', 'Encaminhamento'),
        ('ia', 'Consulta IA'),
    )
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name='anotacoes')
    profissional = models.ForeignKey(PerfilUsuario, on_delete=models.SET_NULL, null=True, blank=True)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default='sessao')
    titulo = models.CharField(max_length=160, blank=True, null=True)
    conteudo = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    SENSITIVE_FIELDS = ['titulo', 'conteudo']

    def save(self, *args, **kwargs):
        for field in self.SENSITIVE_FIELDS:
            val = getattr(self, field, '')
            if val and not str(val).startswith('gAAAAA'):
                setattr(self, field, encrypt_data(str(val)))
        super().save(*args, **kwargs)

    def decrypt_sensitive(self):
        for field in self.SENSITIVE_FIELDS:
            val = getattr(self, field, '')
            if val and str(val).startswith('gAAAAA'):
                setattr(self, field, decrypt_data(val))

    def __str__(self):
        return self.titulo or f"Atendimento #{self.id}"

# Removido modelo Questao legado

# ==================== AVALIAÇÃO CLÍNICA / ANAMNESE (105 CAMPOS) ====================
class AvaliacaoClinica(models.Model):
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, null=True, blank=True, related_name='avaliacoes')
    timestamp = models.DateTimeField(auto_now_add=True)
    score = models.IntegerField(default=0)
    scored_by = models.ForeignKey(PerfilUsuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='avaliacoes_pontuadas')
    scored_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    # I - Identificação do Estudante
    nome = models.TextField(blank=True, null=True) # Sensitive
    idade_anos = models.CharField(max_length=10, blank=True, null=True)
    idade_meses = models.CharField(max_length=10, blank=True, null=True)
    data_nascimento = models.CharField(max_length=20, blank=True, null=True)
    sexo = models.CharField(max_length=20, blank=True, null=True)
    naturalidade = models.CharField(max_length=100, blank=True, null=True)
    endereco = models.TextField(blank=True, null=True) # Sensitive
    fones = models.TextField(blank=True, null=True) # Sensitive
    celular = models.TextField(blank=True, null=True) # Sensitive
    cep = models.CharField(max_length=20, blank=True, null=True)
    unidade_escolar = models.CharField(max_length=200, blank=True, null=True)
    serie = models.CharField(max_length=50, blank=True, null=True)
    turma = models.CharField(max_length=50, blank=True, null=True)
    turno = models.CharField(max_length=50, blank=True, null=True)
    nome_pai = models.TextField(blank=True, null=True) # Sensitive
    grau_instrucao_pai = models.CharField(max_length=100, blank=True, null=True)
    profissao_pai = models.CharField(max_length=150, blank=True, null=True)
    local_trabalho_pai = models.CharField(max_length=150, blank=True, null=True)
    fone_pai = models.TextField(blank=True, null=True) # Sensitive
    nome_mae = models.TextField(blank=True, null=True) # Sensitive
    grau_instrucao_mae = models.CharField(max_length=100, blank=True, null=True)
    profissao_mae = models.CharField(max_length=150, blank=True, null=True)
    local_trabalho_mae = models.CharField(max_length=150, blank=True, null=True)
    fone_mae = models.TextField(blank=True, null=True) # Sensitive
    outro_responsavel = models.TextField(blank=True, null=True) # Sensitive
    fone_outro_responsavel = models.TextField(blank=True, null=True) # Sensitive
    celular_outro_responsavel = models.TextField(blank=True, null=True) # Sensitive
    email_outro_responsavel = models.TextField(blank=True, null=True) # Sensitive

    # I - Dados da Família
    genograma = models.TextField(blank=True, null=True)
    quantas_pessoas = models.CharField(max_length=20, blank=True, null=True)
    parentesco_idades = models.TextField(blank=True, null=True) # Sensitive

    # II - Dados do Desenvolvimento
    mae_problema_gestacao = models.CharField(max_length=20, blank=True, null=True)
    mae_problema_gestacao_desc = models.TextField(blank=True, null=True)
    parto_tipo = models.CharField(max_length=50, blank=True, null=True)
    parto_problema = models.CharField(max_length=20, blank=True, null=True)
    parto_problema_desc = models.TextField(blank=True, null=True)
    sono_bebe_bem = models.CharField(max_length=20, blank=True, null=True)
    sono_atual = models.CharField(max_length=100, blank=True, null=True)
    andou_anos = models.CharField(max_length=10, blank=True, null=True)
    andou_meses = models.CharField(max_length=10, blank=True, null=True)
    falou_anos = models.CharField(max_length=10, blank=True, null=True)
    falou_meses = models.CharField(max_length=10, blank=True, null=True)
    frases_completas_idade_anos = models.CharField(max_length=10, blank=True, null=True)
    frases_completas_idade_meses = models.CharField(max_length=10, blank=True, null=True)
    problema_saude_primeiros_anos = models.CharField(max_length=20, blank=True, null=True)
    problema_saude_qual = models.TextField(blank=True, null=True)

    # III - Vida Escolar
    ingresso_escola_anos = models.CharField(max_length=10, blank=True, null=True)
    ingresso_escola_meses = models.CharField(max_length=10, blank=True, null=True)
    antes_saber_ler_escrever = models.CharField(max_length=20, blank=True, null=True)
    antes_saber_especifique = models.TextField(blank=True, null=True)
    leitura_comecou_anos = models.CharField(max_length=10, blank=True, null=True)
    leitura_comecou_meses = models.CharField(max_length=10, blank=True, null=True)
    escrita_comecou_anos = models.CharField(max_length=10, blank=True, null=True)
    escrita_comecou_meses = models.CharField(max_length=10, blank=True, null=True)
    calculo_comecou_anos = models.CharField(max_length=10, blank=True, null=True)
    calculo_comecou_meses = models.CharField(max_length=10, blank=True, null=True)
    comparacao_faixa_etaria = models.TextField(blank=True, null=True)
    faz_deveres = models.CharField(max_length=100, blank=True, null=True)
    quem_ajuda_tarefas = models.CharField(max_length=150, blank=True, null=True)
    disciplinas_facilidade = models.TextField(blank=True, null=True)
    disciplinas_dificuldade = models.TextField(blank=True, null=True)
    demonstra_habilidade_em = models.TextField(blank=True, null=True)
    assunto_interesse = models.TextField(blank=True, null=True)
    gosta_de_ler = models.CharField(max_length=20, blank=True, null=True)
    tipo_leitura = models.TextField(blank=True, null=True)
    opiniao_sobre_escola = models.TextField(blank=True, null=True)
    opiniao_por_que = models.TextField(blank=True, null=True)
    o_que_acha_professores = models.TextField(blank=True, null=True)
    o_que_professores_falam = models.TextField(blank=True, null=True)
    o_que_pensa_colegas = models.TextField(blank=True, null=True)
    participou_concursos = models.CharField(max_length=20, blank=True, null=True)
    foi_premiado = models.CharField(max_length=20, blank=True, null=True)
    participou_concursos_especifique = models.TextField(blank=True, null=True)
    foi_acelerado = models.CharField(max_length=20, blank=True, null=True)
    para_qual_serie = models.CharField(max_length=50, blank=True, null=True)
    ja_reprovou = models.CharField(max_length=20, blank=True, null=True)
    em_quais_series_reprovou = models.CharField(max_length=100, blank=True, null=True)

    # IV - Vida Social
    tem_muitos_amigos = models.CharField(max_length=20, blank=True, null=True)
    gosta_de_ficar = models.CharField(max_length=100, blank=True, null=True)
    relacionamento_familia = models.TextField(blank=True, null=True)
    pratica_esporte = models.CharField(max_length=20, blank=True, null=True)
    qual_esporte = models.CharField(max_length=100, blank=True, null=True)
    frequencia_esporte = models.CharField(max_length=100, blank=True, null=True)
    vai_a_cultura = models.CharField(max_length=20, blank=True, null=True)
    frequencia_cultura = models.CharField(max_length=100, blank=True, null=True)
    tem_religiao = models.CharField(max_length=20, blank=True, null=True)
    qual_religiao = models.CharField(max_length=100, blank=True, null=True)
    vai_igreja = models.CharField(max_length=20, blank=True, null=True)
    frequencia_igreja = models.CharField(max_length=100, blank=True, null=True)
    participa_extraescolar = models.CharField(max_length=20, blank=True, null=True)
    extraescolar_especifique = models.TextField(blank=True, null=True)
    horas_lazer_gosta = models.TextField(blank=True, null=True)
    houve_mudanca_significativa = models.CharField(max_length=20, blank=True, null=True)
    mudanca_especifique = models.TextField(blank=True, null=True)
    familia_atividade_comum = models.CharField(max_length=20, blank=True, null=True)
    familia_atividade_especifique = models.TextField(blank=True, null=True)
    familia_atividade_frequencia = models.CharField(max_length=100, blank=True, null=True)

    # V - Descrição Biopsicossocial
    descricao_biopsicossocial = models.TextField(blank=True, null=True)
    caracteristicas_marcantes = models.TextField(blank=True, null=True)
    observed_characteristics = models.TextField(blank=True, null=True)

    # VI - Informações Adicionais
    medicacao_controlada = models.CharField(max_length=20, blank=True, null=True)
    acompanhamento = models.TextField(blank=True, null=True)
    observacoes = models.TextField(blank=True, null=True) # Sensitive
    bairro_data = models.CharField(max_length=150, blank=True, null=True)
    assinatura_psicologo = models.CharField(max_length=150, blank=True, null=True)

    # MÉTODOS DE CRIPTOGRAFIA TRANSPARENTE
    SENSITIVE_FIELDS = [
        'nome', 'endereco', 'fones', 'celular', 'nome_pai', 'fone_pai',
        'nome_mae', 'fone_mae', 'outro_responsavel', 'fone_outro_responsavel',
        'celular_outro_responsavel', 'email_outro_responsavel', 'parentesco_idades',
        'observacoes'
    ]

    def save(self, *args, **kwargs):
        # Criptografa dados sensíveis antes de salvar
        for field in self.SENSITIVE_FIELDS:
            val = getattr(self, field, '')
            if val and not val.startswith('gAAAAA'): # Evita criptografar duas vezes
                setattr(self, field, encrypt_data(val))
        super().save(*args, **kwargs)

    def decrypt_sensitive(self):
        """Descriptografa os dados em memória para exibição na interface administrativa."""
        for field in self.SENSITIVE_FIELDS:
            val = getattr(self, field, '')
            if val and val.startswith('gAAAAA'):
                setattr(self, field, decrypt_data(val))

    def __str__(self):
        # Descriptografa temporariamente o nome para exibir no admin console de forma limpa
        nome_real = decrypt_data(self.nome) if self.nome and self.nome.startswith('gAAAAA') else (self.nome or "Sem Nome")
        return f"Avaliação de {nome_real} em {self.timestamp.strftime('%d/%m/%Y %H:%M')}"

# Removido modelo RespostaQuestao legado

# ==================== LOGS DE AUDITORIA (LGPD) ====================
class LogAuditoria(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(PerfilUsuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.TextField()
    ip_address = models.CharField(max_length=45, blank=True, null=True)

    def __str__(self):
        username = self.user.username if self.user else "Anônimo"
        return f"[{self.timestamp.strftime('%d/%m/%Y %H:%M:%S')}] {username}: {self.action}"
