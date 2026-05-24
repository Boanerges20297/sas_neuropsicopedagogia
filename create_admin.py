import os
import sys
import django
from dotenv import load_dotenv

# Carregar as variáveis do .env
load_dotenv()

# Boot do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'neuro_diagnosis.settings')
django.setup()

from avaliacao.models import PerfilUsuario

def create_initial_admin():
    print("=" * 60)
    print("[INFO] CRIANDO USUARIO ADMINISTRADOR INICIAL")
    print("=" * 60)

    admin_email = os.getenv('ADMIN_EMAIL', 'admin@admin.com')
    admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
    admin_name = os.getenv('ADMIN_NAME', 'Administradora')

    # Verifica se já existe um usuário com esse e-mail
    if PerfilUsuario.objects.filter(email=admin_email).exists():
        print(f"[INFO] Usuario administrador ja existe no banco: {admin_email}")
        return

    try:
        username = "admin_" + admin_email.split('@')[0]
        # Criação do usuário superuser no Django
        admin_user = PerfilUsuario.objects.create_superuser(
            username=username,
            email=admin_email,
            password=admin_password,
            first_name=admin_name,
            role='admin'
        )
        print(f"[INFO] Administrador inicial criado com sucesso!")
        print(f"  - E-mail: {admin_email}")
        print("[WARNING] IMPORTANTE: A senha inicial foi lida do ambiente e nao sera exibida em logs.")
        print("=" * 60 + "\n")
    except Exception as e:
        print(f"⚠ Falha ao criar administrador inicial: {e}")

if __name__ == '__main__':
    create_initial_admin()
