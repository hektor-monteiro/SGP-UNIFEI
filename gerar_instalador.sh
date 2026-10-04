#!/usr/bin/env bash
# Gera o pacote de avaliação do SGP-UNIFEI para entrega a um colaborador.
#
# Uso:  ./gerar_instalador.sh [versão]     (padrão: 1.0)
#
# Saída: dist/SGP-UNIFEI-avaliacao-<versão>.zip
#   - imagem Docker já construída (o avaliador NÃO precisa de código nem Docker Build)
#   - compose de produção, instaladores (Linux/Mac e Windows)
#   - código-fonte para consulta na análise de problemas
#   - README-AVALIACAO.md (checklist e coleta de logs)
set -euo pipefail
cd "$(dirname "$0")"

VERSAO="${1:-1.0}"
IMAGEM="sgp-unifei:${VERSAO}"
PKG="dist/SGP-UNIFEI-avaliacao-${VERSAO}"

echo "==> 1/5 Construindo imagem ${IMAGEM}..."
docker build -t "$IMAGEM" .

echo "==> 2/5 Exportando imagem (isso pode demorar)..."
rm -rf "$PKG"
mkdir -p "$PKG"
docker save "$IMAGEM" | gzip > "$PKG/sgp-unifei-imagem.tar.gz"

echo "==> 3/5 Copiando arquivos do pacote..."
cp docker-compose.prod.yml instalar.sh instalar.bat README-AVALIACAO.md "$PKG/"

echo "    Incluindo código-fonte (referência para análise)..."
mkdir -p "$PKG/src"
if git rev-parse --git-dir >/dev/null 2>&1; then
    if [ -n "$(git status --porcelain)" ]; then
        echo "    AVISO: há alterações não commitadas; o pacote conterá o último commit."
    fi
    git archive --format=tar HEAD | tar -xf - -C "$PKG/src"
else
    tar -cf - \
        --exclude=.git --exclude=.venv --exclude=dist \
        --exclude=__pycache__ --exclude=logs . | tar -xf - -C "$PKG/src"
fi

echo "==> 4/5 Compactando..."
if command -v zip >/dev/null 2>&1; then
    (cd dist && zip -qr "SGP-UNIFEI-avaliacao-${VERSAO}.zip" "SGP-UNIFEI-avaliacao-${VERSAO}")
    ARQUIVO="dist/SGP-UNIFEI-avaliacao-${VERSAO}.zip"
else
    echo "    'zip' não encontrado; gerando .tar.gz"
    tar -czf "dist/SGP-UNIFEI-avaliacao-${VERSAO}.tar.gz" -C dist "SGP-UNIFEI-avaliacao-${VERSAO}"
    ARQUIVO="dist/SGP-UNIFEI-avaliacao-${VERSAO}.tar.gz"
fi

echo "==> 5/5 Concluído!"
du -h "$ARQUIVO"
echo ""
echo "Pacote pronto: $ARQUIVO"
echo "Entregue ao avaliador; as instruções estão no README-AVALIACAO.md (dentro do pacote)."
