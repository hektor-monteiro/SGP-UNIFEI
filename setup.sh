#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "=== SGP-UNIFEI Setup ==="
echo ""

echo "1. Subindo containers Docker..."
docker compose up -d --build

echo ""
echo "2. Aguardando aplicação ficar pronta..."
sleep 5

echo ""
echo "3. Rodando migrações..."
docker compose exec app python manage.py migrate

echo ""
echo "4. Populando dados simulados..."
docker compose exec app python manage.py populate_demo

echo ""
echo "5. Criando superusuário (admin/admin123)..."
docker compose exec app python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@unifei.edu.br', 'admin123')
    print('Superusuário admin criado')
else:
    print('Superusuário admin já existe')
"

echo ""
echo "=== Setup concluído! ==="
echo ""
echo "Acesse:"
echo "  - Admin: http://localhost:8000/admin/ (admin / admin123)"
echo "  - Home:  http://localhost:8000/"
echo ""
