"""
URL configuration for neuro_diagnosis project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Painel interno de gerência de tabelas do Django (opcional)
    path('django-admin/', admin.site.urls),
    
    # Nossas rotas principais do app de avaliações
    path('', include('avaliacao.urls')),
]

# Servir arquivos estáticos em modo de desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
