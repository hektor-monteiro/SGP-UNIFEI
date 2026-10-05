# Definição de Indicadores — SGP-UNIFEI

Fórmulas e fontes dos indicadores de `/indicadores/` (§5 dos requisitos),
extraídas de `_dados_indicadores()` (`apps/relatorios/views.py`). Mesmos dados
são exportados no CSV (`/indicadores/csv/`).

**Acesso:** técnico, diretor, pro-reitor e superusuário (`perfil_required`).

Formatação no HTML: moeda `R$ ` com 2 casas (`floatformat:2`), percentuais com
1 casa (`round(x, 1)`), barras proporcionais ao maior valor da série.

## Visão geral (KPIs)

| Indicador | Fórmula | Fonte | Formato |
|---|---|---|---|
| Projetos | `count(Projeto)` | `Projeto` (todas as linhas) | inteiro |
| Bolsas ativas | `count(Bolsa WHERE status='ativa')` | `Bolsa.status` | inteiro |
| Editais | `count(Edital)` | `Edital` | inteiro |
| Taxa de conclusão de projetos | `round(concluídos × 100 / total, 1)` — `0.0` se vazio | `Projeto.status='concluido'` | `%` 1 casa |

## 5.1 Governamentais e de agências de fomento

| Indicador | Fórmula | Fonte | Formato |
|---|---|---|---|
| Bolsas por modalidade | agrupa por sigla: total e `status='ativa'`, ordenado por `-total` | `Bolsa.modalidade__sigla`, `Bolsa.status` | 2 colunas inteiras |
| Bolsas por fomentador | agrupa por sigla, `Count` | `Bolsa.fomentador__sigla` | inteiro (vazio → "Não informado") |
| Projetos concluídos | `concluídos/total` (exibição `X/Y`) | `Projeto.status` | inteiro |
| Alunos que concluíram a bolsa | `count(distinct Bolsa.aluno) WHERE status='encerrada'` | `Bolsa.aluno`, `Bolsa.status` | inteiro |
| Membros externos (ativos/total) | membros `funcao='externo'`; ativos com `ativo=True` | `MembroEquipe.funcao`, `.ativo` | inteiro `X/Y` |
| Recursos internos vinculados | `Sum(Projeto.recursos_internos)` — **todos** os projetos, sem filtro de status | `Projeto.recursos_internos` | moeda `R$` |
| Recursos externos vinculados | `Sum(Projeto.recursos_externos)` — idem | `Projeto.recursos_externos` | moeda `R$` |

### Sem fonte de dados (TODO na tela)
- Projetos por área/departamento do conhecimento (campo não existe)
- Distribuição por gênero, raça e região (campos sensíveis — requer definição LGPD)
- Publicações resultantes de projetos (modelo não existe)
- Execução orçamentária real (hoje: apenas recursos **vinculados**)

## 5.2 Indicadores de efetividade

| Indicador | Fórmula | Fonte | Formato |
|---|---|---|---|
| Evolução — bolsas iniciadas por ano | `count` por `TruncYear(data_inicio)` (sem datas nulas) | `Bolsa.data_inicio` | inteiro + barra |
| Evolução — projetos iniciados por ano | idem | `Projeto.data_inicio` | inteiro + barra |
| Taxa de sucesso em editais | `round(aprovadas × 100 / total, 1)` — `0.0` se vazio | `Proposta.status='aprovada'` | `%` 1 casa |
| Sucesso por edital | por edital com ≥1 proposta: total, aprovadas, `taxa` | `Proposta.edital`, `.status`, `Edital.*` | tabela |
| Orientados por docente | `count(Bolsa WHERE status='ativa')` agrupado por `projeto__coordenador__nome`, top 10 — **conta bolsas**, não alunos distintos | `Bolsa.projeto__coordenador__nome` | inteiro |
| Tempo médio de conclusão | `round(média de (data_termino − data_inicio).days)` em projetos `concluido` com as 2 datas — `None` se vazio | `Projeto.status`, `.data_inicio`, `.data_termino` | inteiro (dias) |
| Retenção de bolsistas | alunos com **≥2 bolsas** (qualquer status) ÷ alunos com bolsa, ×100 | `Bolsa.aluno` (agrupamento) | `%` 1 casa + par `A/T` |

### Sem fonte de dados (TODO na tela)
- Taxa de retenção de alunos em IC (evasão/retensão) — **fórmula oficial a
  definir**; não há campo de origem. (A "retenção de bolsistas" acima é a
  renovação ≥2 bolsas, não a evasão.)

## Exportação CSV

- Mesma base do painel (`_dados_indicadores()`), arquivo
  `indicadores-AAAAMMDD.csv`.
- Formato Excel pt-BR: separador `;`, decimal com vírgula (`_num_csv()`),
  UTF-8 **com BOM**, fim de linha CRLF.
- Seções na ordem da tela: cabeçalho (`Emitido em/Emitido por`) → Visão
  geral → 5.1 → 5.2. Barras/"Proporção" e blocos de TODO **não** vão ao CSV.

## Notas de cálculo

1. Taxas com denominador zero retornam `0.0` (evita divisão por zero — exibe
   `0.0%` mesmo sem dados).
2. "Recursos vinculados" somam **todos** os projetos, inclusive cancelados —
   não é execução orçamentária (confirmado pelo TODO na tela).
3. "Alunos que concluíram a bolsa" conta apenas `status='encerrada'`
   (não inclui `cancelada`/`suspensa`).
4. "Orientados por docente" conta bolsas ativas, não alunos distintos — se o
   orientando tiver 2 bolsas ativas, conta 2.
