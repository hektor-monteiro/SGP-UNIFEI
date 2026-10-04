#!/usr/bin/env bash
# Instalador do SGP-UNIFEI para avaliação (Linux/Mac/Git-Bash).
# Requer Docker (Docker Desktop ou Docker Engine com Compose v2).
set -euo pipefail
cd "$(dirname "$0")"

echo "=== SGP-UNIFEI — Instalação para avaliação ==="

if ! command -v docker >/dev/null 2>&1; then
    echo ""
    echo "ERRO: Docker não encontrado."
    echo "Instale o Docker Desktop: https://www.docker.com/products/docker-desktop/"
    exit 1
fi

echo "1/3 Carregando a imagem do sistema..."
docker load -i sgp-unifei-imagem.tar.gz

echo "2/3 Subindo o sistema (migrações + dados de demonstração)..."
docker compose -f docker-compose.prod.yml up -d

echo "3/3 Aguardando o sistema ficar disponível..."
PORTA="${APP_PORT:-8000}"
for _ in $(seq 1 60); do
    if curl -fsS "http://localhost:${PORTA}/" >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

echo ""
echo "=== Pronto! ==="
echo "  Sistema:  http://localhost:${PORTA}/"
echo "  Admin:    http://localhost:${PORTA}/admin/          (admin / admin123)"
echo "  Login:    http://localhost:${PORTA}/contas/entrar/  (aluno1, docente1,"
echo "            tecnico1, diretor1, proreitor1 — senha demo123)"
echo ""
echo "  Logs:            docker compose -f docker-compose.prod.yml logs --tail=100 app"
echo "  Parar:           docker compose -f docker-compose.prod.yml stop"
echo "  Ler o checklist: README-AVALIACAO.md"
