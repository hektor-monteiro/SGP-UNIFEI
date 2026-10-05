#!/usr/bin/env bash
# Portão de qualidade do SGP-UNIFEI — espelho local do CI.
# Roda o lint (ruff) e a suíte completa de testes no container de dev.
#
# Uso: ./scripts/verificar.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> 1/2 Lint (ruff)..."
docker compose exec app ruff check .

echo ""
echo "==> 2/2 Testes Django (suíte completa)..."
docker compose exec app python manage.py test

echo ""
echo "Verificação concluída com sucesso ✓"
