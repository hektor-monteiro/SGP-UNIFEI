# SGP-UNIFEI

[![CI](https://github.com/hektor-monteiro/SGP-UNIFEI/actions/workflows/ci.yml/badge.svg)](https://github.com/hektor-monteiro/SGP-UNIFEI/actions/workflows/ci.yml)

Sistema de Gestão de Pesquisa da **Diretoria de Pesquisa e Inovação (DiP) da
UNIFEI** — substitui planilhas e Google Forms no gerenciamento de projetos,
bolsas (PIBIC/PIBITI/PIVIC), editais, equipes, comprovantes e relatórios de
indicadores.

**Stack:** Python + Django + PostgreSQL 15 + Docker.

## Documentação

- [`docs/requisitos.md`](docs/requisitos.md) — requisitos funcionais (§3.1 a §3.17)
- [`docs/der.md`](docs/der.md) — modelo de dados (DER)
- [`docs/permissoes.md`](docs/permissoes.md) — matriz de permissões por rota
- [`docs/indicadores.md`](docs/indicadores.md) — indicadores e relatórios
- [`AGENTS.md`](AGENTS.md) — diretrizes para agentes de IA e desenvolvedores
- [`README-AVALIACAO.md`](README-AVALIACAO.md) — checklist de avaliação (vai dentro do Pacote Docker)

## Execução (desenvolvimento)

```bash
docker compose up -d
# http://localhost:8000
# superusuário: admin/admin123 — usuários demo: aluno1, docente1,
# tecnico1, diretor1, proreitor1 com senha demo123
```

## Verificação (espelho do CI)

```bash
./scripts/verificar.sh   # ruff + 440 testes
```

O workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) roda a cada
push: **lint (ruff) → testes Django (PostgreSQL 15) → build da imagem Docker**.

## Pacote Docker (avaliação)

```bash
./gerar_instalador.sh 1.0   # gera dist/SGP-UNIFEI-avaliacao-1.0.zip
```
