import os
import sys
from waitress import serve
import django

# Adicionar a pasta do projeto ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configurar as settings do Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'neuro_diagnosis.settings')
django.setup()

from django.core.wsgi import get_wsgi_application

if __name__ == '__main__':
    # Obter porta do ambiente ou padrão 8000
    port = int(os.getenv('PORT', 8000))
    host = os.getenv('HOST', '0.0.0.0')

    print("\n" + "="*60)
    print("🚀 SERVIDOR DE PRODUÇÃO DJANGO INICIADO COM WAITRESS WSGI!")
    print("="*60)
    print(f"📍 Endereço local: http://{host}:{port}/")
    print(f"🔧 Threads ativas: Waitress multi-threaded")
    print("="*60 + "\n")

    try:
        application = get_wsgi_application()
        serve(application, host=host, port=port, threads=4)
    except Exception as e:
        print(f"⚠ Erro crítico ao inicializar o servidor Waitress: {e}")
