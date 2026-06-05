from django.urls import path
from . import views

urlpatterns = [
    # Públicas / Landing
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('area-do-usuario/', views.user_area, name='user_area'),
    path('perfil/', views.perfil_usuario, name='perfil_usuario'),

    # Fichas Clínicas e Anamneses (Preenchimento)
    path('anamnese/nova/', views.nova_anamnese, name='nova_anamnese'),
    path('anamnese/salvar/', views.salvar_anamnese, name='salvar_anamnese'),

    # Área Administrativa (Exclusivo Neuropsicopedagoga)
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Gestão de Pacientes
    path('admin/pacientes/', views.pacientes_list, name='pacientes_list'),
    path('admin/pacientes/novo/', views.paciente_create, name='paciente_create'),
    path('admin/pacientes/<int:paciente_id>/editar/', views.paciente_update, name='paciente_update'),
    path('admin/pacientes/<int:paciente_id>/', views.paciente_detail, name='paciente_detail'),
    path('admin/pacientes/<int:paciente_id>/nova-anamnese/', views.paciente_nova_anamnese, name='paciente_nova_anamnese'),

    # Gestão de Avaliações / Anamneses
    path('admin/consultas/', views.consultas_list, name='consultas_list'),
    path('admin/consultas/<int:consulta_id>/editar/', views.consulta_update, name='consulta_update'),
    path('admin/atendimento/', views.atendimento_list, name='atendimento_list'),
    path('admin/atendimento/<int:consulta_id>/', views.atendimento_detail, name='atendimento_detail'),
    path('admin/avaliacoes/', views.admin_avaliacoes, name='admin_avaliacoes'),
    path('admin/avaliacao/<int:avaliacao_id>/', views.view_avaliacao, name='view_avaliacao'),
    path('admin/avaliacao/<int:avaliacao_id>/pontuar/', views.score_avaliacao, name='score_avaliacao'),
    path('admin/usuarios/', views.admin_users, name='admin_users'),
    path('admin/usuarios/novo/', views.admin_user_create, name='admin_user_create'),
    path('admin/usuarios/<int:user_id>/status/', views.admin_user_toggle_active, name='admin_user_toggle_active'),
    path('admin/usuarios/<int:user_id>/perfil/', views.admin_user_change_role, name='admin_user_change_role'),
    
    # Consulta IA de Borda (Local)
    path('admin/ia/', views.ia_consulta, name='ia_consulta'),
    path('admin/ia/<int:consulta_id>/feedback/', views.feedback_consulta_ia, name='feedback_consulta_ia'),
    
    # Exportação
    path('exportar/', views.export_excel, name='export_excel'),
]
