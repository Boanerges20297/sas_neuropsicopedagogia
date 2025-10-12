# Script para migrar para a nova versão com autenticação
import os
import shutil
from datetime import datetime

ROOT = r"c:\Users\Boanerges\Documents\Testes - Altas Habilidades"

# Criar backup dos arquivos antigos
backup_folder = os.path.join(ROOT, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
os.makedirs(backup_folder, exist_ok=True)

# Fazer backup
files_to_backup = ['app.py', 'static/style.css']
for file in files_to_backup:
    src = os.path.join(ROOT, file)
    if os.path.exists(src):
        dst = os.path.join(backup_folder, file.replace('/', '_'))
        shutil.copy2(src, dst)
        print(f"✓ Backup: {file} -> {dst}")

# Renomear arquivos novos
renames = [
    ('app_new.py', 'app.py'),
    ('static/style_new.css', 'static/style.css'),
    ('templates/login_new.html', 'templates/login.html'),
    ('templates/register_new.html', 'templates/register.html'),
    ('templates/dashboard_new.html', 'templates/dashboard.html')
]

for old, new in renames:
    old_path = os.path.join(ROOT, old)
    new_path = os.path.join(ROOT, new)
    if os.path.exists(old_path):
        # Remove novo se existir
        if os.path.exists(new_path):
            os.remove(new_path)
        os.rename(old_path, new_path)
        print(f"✓ Renomeado: {old} -> {new}")

print("\n✅ Migração concluída!")
print(f"📁 Backup salvo em: {backup_folder}")
print("\n🚀 Para iniciar o servidor:")
print("   python app.py")
print("\n🔑 Login admin padrão:")
print("   Email: admin@admin.com")
print("   Senha: admin123")
