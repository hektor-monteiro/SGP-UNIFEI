#!/usr/bin/env bash
# Entrypoint de produção/avaliação do SGP-UNIFEI.
# Espera o banco, aplica migrações, coleta estáticos, cria o administrador,
# semeia dados de demonstração (SEED_DEMO=1) e executa o comando final.
set -e

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-sgp.config.settings}"

echo "==> Aguardando banco de dados..."
python <<'PY'
import sys
import time

import django
from django.db import connections
from django.db.utils import OperationalError

django.setup()
for _ in range(60):
    try:
        connections['default'].ensure_connection()
        break
    except OperationalError:
        time.sleep(1)
else:
    sys.exit('ERRO: banco de dados indisponível após 60 segundos')
print('    Banco de dados OK')
PY

echo "==> Aplicando migrações..."
python manage.py migrate --noinput

echo "==> Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo "==> Preparando usuários e dados..."
python <<'PY'
import os

import django

django.setup()

from django.contrib.auth.models import User

senha = os.environ.get('ADMIN_PASSWORD', 'admin123')
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@unifei.edu.br', senha)
    print('    Superusuário admin criado')
else:
    print('    Superusuário admin já existe')

if os.environ.get('SEED_DEMO', '1') == '1':
    if not User.objects.filter(username='aluno1').exists():
        from django.core.management import call_command

        print('    Semeando dados de demonstração...')
        call_command('populate_demo')
    else:
        print('    Dados de demonstração já presentes')
PY

echo "==> Iniciando aplicação..."
exec "$@"
