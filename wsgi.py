import sys
import os
from pathlib import Path

# Adiciona o repo ao path
project_home = Path(__file__).parent
sys.path.insert(0, str(project_home / "webapp"))
sys.path.insert(0, str(project_home))

# Variáveis de ambiente (substitua as passwords antes de fazer push, ou defina no painel)
os.environ.setdefault("SECRET_KEY", "csm-decor-secret-2025-altere-isto")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")
os.environ.setdefault("CLIENT_PASSWORD", "cliente123")

from app import app as application
