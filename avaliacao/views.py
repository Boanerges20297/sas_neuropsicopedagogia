from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as login_user, logout as logout_user
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.utils import timezone
from django.db.models import Max
from datetime import datetime, timedelta
import requests
import json
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from .models import (
    PerfilUsuario, LogAuditoria, Paciente, AnotacaoAtendimento, AvaliacaoClinica
)
from .security_utils import decrypt_data, encrypt_data

# ==================== DECORADOR ADMIN ====================
def admin_required(view_func):
    """Garante acesso exclusivo para a Neuropsicopedagoga (administradora)."""
    def _wrapped_view_func(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_admin():
            messages.error(request, 'Você não tem permissão para acessar esta área.')
            return redirect('index')
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func

# ==================== REGISTRO DE TRILHA DE AUDITORIA ====================
def register_audit_log(request, action):
    """Grava logs de auditoria automáticos na tabela MySQL para LGPD."""
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '127.0.0.1'))
    LogAuditoria.objects.create(
        user=request.user if request.user.is_authenticated else None,
        action=action,
        ip_address=ip
    )

# ==================== ROTAS DE AUTENTICAÇÃO ====================
def login_view(request):
    """Login que preserva o layout original marrom/dourado e valida cookies seguros."""
    if request.user.is_authenticated:
        return redirect('dashboard' if request.user.is_admin() else 'user_area')

    if request.method == 'POST':
        email = request.POST.get('email')
        senha = request.POST.get('senha')
        remember = request.POST.get('remember') == 'on'

        try:
            user = PerfilUsuario.objects.get(email=email)
            authenticated_user = authenticate(request, username=user.username, password=senha)
        except PerfilUsuario.DoesNotExist:
            authenticated_user = None

        if authenticated_user:
            login_user(request, authenticated_user)
            if not remember:
                request.session.set_expiry(0) # Expira ao fechar navegador
            
            register_audit_log(request, "Realizou login no sistema.")
            messages.success(request, f"Bem-vinda, {authenticated_user.first_name or authenticated_user.username}!")
            return redirect('dashboard' if authenticated_user.is_admin() else 'user_area')
        else:
            messages.error(request, "E-mail ou senha incorretos.")

    return render(request, 'login.html')

def register_view(request):
    """Cadastro de novos usuários com validação forte de senhas."""
    if request.user.is_authenticated:
        return redirect('dashboard' if request.user.is_admin() else 'user_area')

    if request.method == 'POST':
        nome = request.POST.get('nome')
        email = request.POST.get('email')
        senha = request.POST.get('senha')
        data_nascimento = request.POST.get('data_nascimento')
        escolaridade = request.POST.get('escolaridade')
        telefone = request.POST.get('telefone')

        if PerfilUsuario.objects.filter(email=email).exists():
            messages.error(request, "Este e-mail já está cadastrado no sistema.")
            return render(request, 'register.html')

        if len(senha) < 8 or not any(c.isupper() for c in senha) or not any(c.isdigit() for c in senha):
            messages.error(request, "A senha deve ter pelo menos 8 caracteres, contendo pelo menos uma letra maiúscula e um número.")
            return render(request, 'register.html')

        username = email.split('@')[0] + "_" + str(PerfilUsuario.objects.count() + 1)
        user = PerfilUsuario.objects.create_user(
            username=username,
            email=email,
            password=senha,
            first_name=nome,
            role='user',
            data_nascimento=data_nascimento,
            escolaridade=escolaridade,
            telefone=telefone
        )
        
        register_audit_log(request, f"Novo usuário cadastrado: {email}")
        messages.success(request, "Cadastro realizado com sucesso! Faça login para continuar.")
        return redirect('login')

    return render(request, 'register.html')

@login_required
def logout_view(request):
    """Logout seguro do usuário."""
    register_audit_log(request, "Realizou logout do sistema.")
    logout_user(request)
    messages.info(request, "Você saiu da sua conta.")
    return redirect('login')

# ==================== ROTAS PÚBLICAS E REDIRECIONAMENTOS ====================
def index(request):
    """Página inicial com redirecionamento contextual."""
    if request.user.is_authenticated:
        return redirect('dashboard' if request.user.is_admin() else 'user_area')
    return redirect('login')

@login_required
def user_area(request):
    """Área exclusiva para usuários comuns cadastrados."""
    return render(request, 'user_area.html')

# ==================== CONTROLLER ADMINISTRATIVO (DASHBOARD) ====================
@login_required
@admin_required
def dashboard(request):
    """Agrega estatísticas operacionais de alto nível com Django ORM para o Chart.js."""
    total_responses = AvaliacaoClinica.objects.count()
    total_pacientes = Paciente.objects.count()
    
    today = timezone.now().date()
    new_today = AvaliacaoClinica.objects.filter(timestamp__date=today).count()
    
    total_users = PerfilUsuario.objects.count()
    admin_count = PerfilUsuario.objects.filter(role='admin').count()
    
    recent_responses_raw = AvaliacaoClinica.objects.all().order_by('-timestamp')[:5]
    recent_responses = []
    for r in recent_responses_raw:
        r.decrypt_sensitive()
        recent_responses.append(r)

    daily_labels = []
    daily_values = []
    for i in range(7):
        d = today - timedelta(days=6-i)
        daily_labels.append(d.strftime('%d/%m'))
        count = AvaliacaoClinica.objects.filter(timestamp__date=d).count()
        daily_values.append(count)

    last_r = AvaliacaoClinica.objects.all().order_by('-timestamp').first()
    last_response_date = last_r.timestamp.strftime('%d/%m/%Y') if last_r else 'Nenhuma'
    last_response_time = last_r.timestamp.strftime('%H:%M') if last_r else ''

    stats = {
        'total_responses': total_responses,
        'new_today': new_today,
        'total_users': total_users,
        'total_pacientes': total_pacientes,
        'admin_count': admin_count,
        'last_response_date': last_response_date,
        'last_response_time': last_response_time,
        'recent_responses': recent_responses,
        'daily_labels': json.dumps(daily_labels),
        'daily_values': json.dumps(daily_values),
    }

    register_audit_log(request, "Acessou o Dashboard Administrativo.")
    return render(request, 'dashboard.html', {'stats': stats})

@login_required
@admin_required
def admin_avaliacoes(request):
    """Lista todas as avaliações clínicas / anamneses preenchidas."""
    responses_raw = AvaliacaoClinica.objects.all().order_by('-timestamp')
    responses = []
    for r in responses_raw:
        r.decrypt_sensitive()
        responses.append(r)
        
    register_audit_log(request, "Acessou a lista de avaliações clínicas.")
    return render(request, 'admin_responses.html', {'responses': responses})

@login_required
@admin_required
def view_avaliacao(request, avaliacao_id):
    """Detalhes clínicos do prontuário, consultando o microsserviço de IA de Borda."""
    avaliacao = get_object_or_404(AvaliacaoClinica, id=avaliacao_id)
    avaliacao.decrypt_sensitive()
    
    register_audit_log(request, f"Visualizou prontuário de avaliação ID {avaliacao_id} ({avaliacao.nome}).")

    ai_data = None
    ai_error = False
    
    try:
        context_domain = "paciente_" + str(avaliacao.paciente_id if avaliacao.paciente_id else "geral")
        
        payload = {
            "observed_characteristics": avaliacao.observed_characteristics or "",
            "andou_anos": avaliacao.andou_anos or "",
            "andou_meses": avaliacao.andou_meses or "",
            "falou_anos": avaliacao.falou_anos or "",
            "falou_meses": avaliacao.falou_meses or "",
            "escrita_comecou_anos": avaliacao.escrita_comecou_anos or "",
            "escrita_comecou_meses": avaliacao.escrita_comecou_meses or "",
            "leitura_comecou_anos": avaliacao.leitura_comecou_anos or "",
            "leitura_comecou_meses": avaliacao.leitura_comecou_meses or "",
            "pratica_esporte": avaliacao.pratica_esporte or "",
            "qual_esporte": avaliacao.qual_esporte or "",
            "assunto_interesse": avaliacao.assunto_interesse or "",
            "disciplinas_dificuldade": avaliacao.disciplinas_dificuldade or "",
            "context_domain": context_domain
        }
        
        ai_url = f"{settings.AI_SERVICE_URL}/api/v1/analyze"
        ai_resp = requests.post(ai_url, json=payload, timeout=4.0)
        
        if ai_resp.status_code == 200:
            ai_data = ai_resp.json().get('data')
        else:
            ai_error = True
    except Exception as e:
        print(f"⚠ Erro na comunicação com Microsserviço de IA: {e}")
        ai_error = True

    fields_list = []
    for f in AvaliacaoClinica._meta.fields:
        if f.name not in ['id', 'paciente', 'timestamp', 'score', 'scored_by', 'scored_at', 'notes']:
            val = getattr(avaliacao, f.name)
            fields_list.append((f.verbose_name or f.name, val))

    context = {
        'response': avaliacao,  # mantido como 'response' no context para compatibilidade com templates
        'fields_list': fields_list,
        'ai_data': ai_data,
        'ai_error': ai_error,
        'ai_scores_json': json.dumps(ai_data.get('scores')) if ai_data else json.dumps({
            'intelectual': 0, 'criatividade': 0, 'lideranca': 0, 'artes': 0, 'psicomotora': 0
        })
    }
    
    return render(request, 'view_response.html', context)

@login_required
@admin_required
def score_avaliacao(request, avaliacao_id):
    """Salva a pontuação atribuída e anotações clínicas via AJAX."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score', 0)
            notes = data.get('notes', '')

            avaliacao = get_object_or_404(AvaliacaoClinica, id=avaliacao_id)
            avaliacao.score = int(score)
            avaliacao.notes = notes
            avaliacao.scored_by = request.user
            avaliacao.scored_at = timezone.now()
            avaliacao.save()

            register_audit_log(request, f"Pontuou prontuário de avaliação ID {avaliacao_id} com {score} pontos.")
            return JsonResponse({'success': True, 'message': 'Parecer e pontuação salvos com sucesso!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    return JsonResponse({'success': False, 'message': 'Método inválido'}, status=400)

@login_required
@admin_required
def admin_users(request):
    """Lista usuários cadastrados."""
    users = PerfilUsuario.objects.all().order_by('-created_at')
    register_audit_log(request, "Visualizou lista geral de usuários cadastrados.")
    return render(request, 'admin_users.html', {'users': users})

# ==================== PACIENTES E ATENDIMENTOS ====================
@login_required
@admin_required
def pacientes_list(request):
    pacientes = []
    for paciente in Paciente.objects.all().order_by('-updated_at'):
        paciente.decrypt_sensitive()
        pacientes.append(paciente)
    register_audit_log(request, "Acessou a área de pacientes.")
    return render(request, 'pacientes_list.html', {'pacientes': pacientes})

@login_required
@admin_required
def paciente_create(request):
    if request.method == 'POST':
        paciente = Paciente.objects.create(
            nome=request.POST.get('nome', '').strip(),
            data_nascimento=request.POST.get('data_nascimento', '').strip(),
            responsavel=request.POST.get('responsavel', '').strip(),
            telefone=request.POST.get('telefone', '').strip(),
            email=request.POST.get('email', '').strip(),
            escola=request.POST.get('escola', '').strip(),
            serie=request.POST.get('serie', '').strip(),
            queixa_principal=request.POST.get('queixa_principal', '').strip(),
            observacoes=request.POST.get('observacoes', '').strip(),
        )
        register_audit_log(request, f"Cadastrou paciente ID {paciente.id}.")
        messages.success(request, "Paciente cadastrado com sucesso.")
        return redirect('paciente_detail', paciente_id=paciente.id)
    return render(request, 'paciente_form.html')

@login_required
@admin_required
def paciente_detail(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    paciente.decrypt_sensitive()

    if request.method == 'POST':
        anotacao = AnotacaoAtendimento.objects.create(
            paciente=paciente,
            profissional=request.user,
            tipo=request.POST.get('tipo', 'sessao'),
            titulo=request.POST.get('titulo', '').strip(),
            conteudo=request.POST.get('conteudo', '').strip(),
        )
        register_audit_log(request, f"Registrou anotação ID {anotacao.id} no paciente ID {paciente_id}.")
        messages.success(request, "Anotação registrada.")
        return redirect('paciente_detail', paciente_id=paciente.id)

    anotacoes = []
    for item in paciente.anotacoes.all().order_by('-created_at'):
        item.decrypt_sensitive()
        anotacoes.append(item)

    # Buscar avaliações vinculadas
    avaliacoes = paciente.avaliacoes.all().order_by('-timestamp')
    for av in avaliacoes:
        av.decrypt_sensitive()

    return render(request, 'paciente_detail.html', {
        'paciente': paciente, 
        'anotacoes': anotacoes,
        'avaliacoes': avaliacoes
    })

@login_required
@admin_required
def paciente_nova_anamnese(request, paciente_id):
    """Garante redirecionamento para ficha com ID do paciente pré-configurado."""
    return redirect(f"/anamnese/nova/?paciente_id={paciente_id}")

@login_required
@admin_required
def ia_consulta(request):
    selected_paciente_id = request.GET.get('paciente', '')
    pacientes = []
    for paciente in Paciente.objects.all().order_by('-updated_at')[:50]:
        paciente.decrypt_sensitive()
        pacientes.append(paciente)

    resultado = None
    erro = None
    engine_info = {
        'nome': 'Neuro-Diagnosis Edge AI',
        'tipo': 'Microsserviço local FastAPI',
        'modelo': 'Motor heurístico próprio + memória semântica DSM-5-TR',
        'nuvem': 'Não utiliza nuvem nem APIs externas (totalmente local)',
        'url': settings.AI_SERVICE_URL,
    }

    if request.method == 'POST':
        paciente_id = request.POST.get('paciente_id')
        pergunta = request.POST.get('pergunta', '').strip()
        contexto = request.POST.get('contexto', '').strip()
        paciente = Paciente.objects.filter(id=paciente_id).first() if paciente_id else None
        if paciente:
            paciente.decrypt_sensitive()

        payload = {
            'observed_characteristics': contexto or pergunta,
            'andou_anos': '',
            'andou_meses': '',
            'falou_anos': '',
            'falou_meses': '',
            'escrita_comecou_anos': '',
            'escrita_comecou_meses': '',
            'leitura_comecou_anos': '',
            'leitura_comecou_meses': '',
            'pratica_esporte': '',
            'qual_esporte': '',
            'assunto_interesse': pergunta,
            'disciplinas_dificuldade': paciente.queixa_principal if paciente else '',
            'context_domain': f"paciente_{paciente.id}" if paciente else 'consulta_geral',
        }
        try:
            ai_url = f"{settings.AI_SERVICE_URL}/api/v1/analyze"
            ai_resp = requests.post(ai_url, json=payload, timeout=8.0)
            ai_resp.raise_for_status()
            resultado = ai_resp.json().get('data')
            if paciente and pergunta:
                AnotacaoAtendimento.objects.create(
                    paciente=paciente,
                    profissional=request.user,
                    tipo='ia',
                    titulo='Consulta IA',
                    conteudo=f"Pergunta: {pergunta}\n\nResultado: {json.dumps(resultado, ensure_ascii=False)}",
                )
            register_audit_log(request, "Realizou consulta à IA.")
        except Exception as exc:
            erro = f"Não foi possível consultar a IA local: {exc}"

    return render(request, 'ia_consulta.html', {
        'pacientes': pacientes,
        'resultado': resultado,
        'erro': erro,
        'engine_info': engine_info,
        'selected_paciente_id': selected_paciente_id,
    })

# ==================== PREENCHIMENTO E SUBMISSÃO DA ANAMNESE ====================
def nova_anamnese(request):
    """Renderiza a ficha clínica estruturada de 105 campos (Anamnese)."""
    CHECKBOX_OPTIONS = [
        "Facilidade em processar informações, integrar experiências e emitir respostas apropriadas",
        "Aprendizagem rápida/fácil e com pouca repetição",
        "Pensador crítico; lida com problemas abstraatos/complexos",
        "Boa memória e facilidade para acumular conhecimento",
        "Habilidade de raciocínio lógico-matemático",
        "Vocabulário avançado para a idade; verbalmente fluente",
        "Capacidade de generalizar e transferir aprendizagem",
        "Percepções incomuns na resolução de problemas",
        "Facilidade e agilidade para produzir ideias",
        "Flexibilidade ou facilidade para pensar fora dos padrões",
        "Originalidade de pensamento",
        "Capacidade de resolver problemas de forma criativa e efetiva",
        "Abertura a novas experiências e disposição para correr riscos",
        "Vê relações entre ideias diversas",
        "Independência e autonomia de pensamento",
        "Apurado senso de humor",
        "Interesse constante por certos tópicos",
        "Tendência a iniciar suas próprias atividades",
        "Persistência na realização de tarefas de interesse",
        "Auto-imposição para atingir a perfeição",
        "Ocupa seu tempo de forma produtiva",
        "Concentra-se por período prolongado sem aborrecer-se",
        "Preferência por responsabilidade pessoal sobre sua produção",
        "Obstinação em procurar informações sobre tópicos de interesse"
    ]
    
    paciente_id = request.GET.get('paciente_id')
    paciente = None
    if paciente_id:
        paciente = get_object_or_404(Paciente, id=paciente_id)
        paciente.decrypt_sensitive()
        
    return render(request, 'form.html', {
        'checkbox_options': CHECKBOX_OPTIONS,
        'paciente': paciente
    })

def salvar_anamnese(request):
    """Processa e salva as submissões da anamnese clínica no banco de dados MySQL de forma segura."""
    if request.method == 'POST':
        data = {}
        for f in AvaliacaoClinica._meta.fields:
            name = f.name
            if name not in ['id', 'paciente', 'timestamp', 'score', 'scored_by', 'scored_at', 'notes']:
                if name == 'observed_characteristics':
                    vals = request.POST.getlist('observed_characteristics')
                    data[name] = ", ".join(vals)
                else:
                    data[name] = request.POST.get(name, '').strip()

        # Vincular paciente se informado
        paciente_id = request.POST.get('paciente_id')
        if paciente_id and paciente_id.isdigit():
            data['paciente_id'] = int(paciente_id)

        # Se não vier nome preenchido mas vier paciente_id, preencher com o nome do paciente
        if not data.get('nome') and paciente_id:
            p = Paciente.objects.filter(id=paciente_id).first()
            if p:
                p.decrypt_sensitive()
                data['nome'] = p.nome

        new_resp = AvaliacaoClinica.objects.create(**data)
        
        # Dispara aprendizado silencioso no microsserviço de IA (se ativo) sobre este caso
        try:
            ai_learn_url = f"{settings.AI_SERVICE_URL}/api/v1/learn"
            payload = {
                "content": f"Caso clínico com observações: {data.get('observacoes')}. Características notadas: {data.get('observed_characteristics')}",
                "context_domain": f"paciente_{new_resp.paciente_id}" if new_resp.paciente_id else "geral",
                "clinical_category": "casos_clinicos",
                "target_age": "infantil" if int(data.get('idade_anos') or 10) < 12 else "adolescente"
            }
            requests.post(ai_learn_url, json=payload, timeout=2.0)
        except Exception as e:
            print(f"Sem conexão para aprendizado na IA: {e}")

        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '127.0.0.1'))
        LogAuditoria.objects.create(
            user=request.user if request.user.is_authenticated else None,
            action=f"Nova avaliação preenchida na internet e salva. ID do Prontuário: {new_resp.id}",
            ip_address=ip
        )

        return render(request, 'thankyou.html')

    return redirect('nova_anamnese')

# ==================== EXPORTAÇÃO COMPLETA PARA EXCEL ====================
@login_required
@admin_required
def export_excel(request):
    """Gera planilha Excel profissional e estilizada contendo todos os prontuários e respostas."""
    register_audit_log(request, "Exportou a base de dados de avaliações para planilha Excel (.xlsx).")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Avaliações Clínicas"

    ws.views.sheetView[0].showGridLines = True

    fill_header = PatternFill(start_color="315b61", end_color="2a4d52", fill_type="solid")
    font_header = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    
    fill_even = PatternFill(start_color="F9F8F6", end_color="F9F8F6", fill_type="solid")
    fill_odd = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    font_data = Font(name="Segoe UI", size=10)
    
    thin_border = Border(
        left=Side(style='thin', color='E5E0D8'),
        right=Side(style='thin', color='E5E0D8'),
        top=Side(style='thin', color='E5E0D8'),
        bottom=Side(style='thin', color='E5E0D8')
    )

    headers = ["ID Avaliação", "Paciente Vinculado", "Data e Hora", "Pontuação Atribuída", "Parecer Clínico"]
    fields_to_export = []
    
    for f in AvaliacaoClinica._meta.fields:
        if f.name not in ['id', 'paciente', 'timestamp', 'score', 'scored_by', 'scored_at', 'notes']:
            headers.append(f.verbose_name or f.name.replace("_", " ").capitalize())
            fields_to_export.append(f.name)

    ws.append(headers)

    for cell in ws[1]:
        cell.fill = fill_header
        cell.font = font_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    
    ws.row_dimensions[1].height = 28

    responses = AvaliacaoClinica.objects.all().order_by('-timestamp')
    row_num = 2
    
    for resp in responses:
        resp.decrypt_sensitive()
        
        paciente_nome = "Não Vinculado"
        if resp.paciente:
            resp.paciente.decrypt_sensitive()
            paciente_nome = resp.paciente.nome

        row_data = [
            resp.id,
            paciente_nome,
            resp.timestamp.strftime('%d/%m/%Y %H:%M'),
            resp.score,
            resp.notes or "Sem parecer atribuído"
        ]
        
        for field_name in fields_to_export:
            row_data.append(getattr(resp, field_name) or "")

        ws.append(row_data)
        
        row_fill = fill_even if row_num % 2 == 0 else fill_odd
        for cell in ws[row_num]:
            cell.fill = row_fill
            cell.font = font_data
            cell.border = thin_border
            if cell.column in [1, 2, 3, 4]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                
        ws.row_dimensions[row_num].height = 22
        row_num += 1

    for col in ws.columns:
        max_len = 0
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        
        for cell in col:
            val = str(cell.value or '')
            if len(val) > max_len:
                max_len = len(val)
                
        ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 45)

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = f"attachment; filename=avaliacoes_neuropsicopedagogia_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    wb.save(response)
    return response
