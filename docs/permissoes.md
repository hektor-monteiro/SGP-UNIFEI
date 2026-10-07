# Matriz de Permissões — SGP-UNIFEI

Especificação derivada do código implementado (`apps/core/permissions.py` e as
views de cada app). Equivalente visual das regras do §2 dos requisitos.

Hierarquia: **aluno (1) < docente (2) < técnico (3) < diretor (4) < pro-reitor (5)**.

## 1. Helpers de autorização (`apps/core/permissions.py`)

| Helper | Regra |
|---|---|
| `perfil_de(user)` | superusuário → `None` (acesso total); autenticado **sem** Perfil → 403 |
| `pode_gerir(perfil)` | superusuário **ou** nível ≥ técnico — gerencia todos os processos |
| `pode_criar(user)` | `pode_gerir` **ou** docente — aluno não cria registros |
| `perfil_required(...)` | exige um dos perfis informados; superusuário sempre passa; 403 (template `core/403.html`) |
| `_pode_gerir(user, projeto)` (equipes) | técnico+ **ou** coordenador daquele projeto |

**Superusuário**: acesso total a dados e gestão; porém **não é titular** — não
abre solicitações LGPD, não registra consentimento e não submete propostas
(é administração, não participante).

## 2. Matriz resumo por operação

| Operação | aluno | docente | técnico | diretor | pro-reitor | super |
|---|---|---|---|---|---|---|
| Ver projetos | só os que participa/tem bolsa | todos | todos | todos | todos | todos |
| Criar projeto | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| Criar bolsa (manual) | — | — | ✅ | ✅ | ✅ | ✅ |
| Editar projeto | — | só os que coordena | ✅ | ✅ | ✅ | ✅ |
| Editar bolsa | — | só as de projetos que coordena | ✅ | ✅ | ✅ | ✅ |
| Gerenciar equipe (membros) | — | só do projeto que coordena | ✅ | ✅ | ✅ | ✅ |
| Criar/editar edital, critérios, modalidades | — | — | ✅ | ✅ | ✅ | ✅ |
| **Aprovar** edital (Diretoria/Reitoria) | — | — | — | ✅ | ✅ | ✅ |
| Iniciar/encerrar/cancelar edital | — | — | ✅ | ✅ | ✅ | ✅ |
| Submeter proposta a edital (projeto + cotas) | — | ✅ | — | — | — | — |
| Editar proposta (até decisão) | — | própria | ✅ | ✅ | ✅ | ✅ |
| Indicar aluno para cota aprovada | — | da proposta que submeteu | ✅ | ✅ | ✅ | ✅ |
| Implementar bolsa (a partir da indicação) | — | — | ✅ | ✅ | ✅ | ✅ |
| Alocar/remover avaliadores | — | — | ✅ | ✅ | ✅ | ✅ |
| Avaliar proposta | — | se alocado | se alocado | se alocado | se alocado | — |
| Enviar projeto para avaliação por pares | — | só do projeto que coordena | ✅ | ✅ | ✅ | ✅ |
| Avaliar projeto (por pares) | — | se alocado | se alocado | se alocado | se alocado | — |
| Criar plano de trabalho | próprio (sem plano) | bolsas coordenadas | todos | todos | todos | todos |
| Avaliar plano/relatório | — | orientandos + co-orientados | ✅ | ✅ | ✅ | ✅ |
| Emitir comprovantes | bolsa própria, participação própria, avaliações que fez | bolsas orientadas + os acima | tudo | tudo | tudo | tudo |
| Indicadores + CSV / auditoria / tratar solicitações LGPD | — | — | ✅ | ✅ | ✅ | ✅ |
| Verificar comprovante (código) | público (sem login) | idem | idem | idem | idem | idem |

## 3. Detalhamento por módulo

### 3.1 Core — painel, LGPD, auditoria (`apps/core/`)

| Rota | Ação | Quem pode | Regra especial |
|---|---|---|---|
| `/painel/` | visualizar | autenticado | conteúdo por perfil; fila de relatórios: técnico+ vê todos, docente orientandos e co-orientandos; **seção "Aguardando alocação de avaliador"** (só téc+): propostas submetidas e projetos submetidos sem avaliador, com a ação **Alocar Avaliador** |
| `/lgpd/` | visualizar | autenticado | consentimento e direitos do titular |
| `/lgpd/consentimento/` (POST) | editar | autenticado com Perfil | superusuário não é titular → redirect |
| `/lgpd/consentimento/revogar/` (POST) | editar | autenticado com Perfil | idem |
| `/lgpd/meus-dados/` | exportar | autenticado | somente dados próprios (JSON) |
| `/lgpd/auditoria/` | visualizar | **téc+** (`perfil_required`) | aluno/docente → 403 |
| `/lgpd/solicitacoes/` | visualizar | autenticado | técnico+ vê todas (+filtros); demais só as próprias |
| `/lgpd/solicitacoes/nova/` | criar | autenticado com Perfil | superusuário → redirect (não é titular) |
| `/lgpd/solicitacoes/<pk>/` | visualizar | titular ou técnico+ | terceiros → 404 |
| `/lgpd/solicitacoes/<pk>/tratar/` (POST) | editar | **téc+** | concluir exclusão exige **zero vínculos ativos** (§6/art.16) |

### 3.2 Projetos (`apps/projetos/`)

| Rota | Ação | Quem pode | Regra especial |
|---|---|---|---|
| `/projetos/` | visualizar | autenticado | aluno: só projetos onde é membro ou tem bolsa (sem Pessoa → vazio) |
| `/projetos/novo/` | criar | docente ou téc+ | aluno → 403; docente vira coordenador |
| `/projetos/<pk>/` | visualizar | autenticado | aluno precisa de vínculo (membro ou bolsa) → senão 403 |
| `/projetos/<pk>/editar/` | editar | téc+ **ou** coordenador do projeto | coordenador não altera o campo coordenador; `resumo` obrigatório; aceita upload do PDF (opcional) |
| `/projetos/<pk>/arquivo/` | baixar o PDF | autenticado | **mesma permissão do detalhe** (aluno com vínculo); sem arquivo → 404; entrega `application/pdf` + `nosniff`, nunca por `/media/` público |
| `/projetos/<pk>/submeter/` (POST) | enviar para avaliação por pares | **coordenador do projeto ou téc+** | só de `nao_submetido`; **exige PDF anexado e resumo** (erro claro + nada muda); reenvio bloqueado; aluno/docente-de-fora → 403; nota automática (financiamento externo) → envio dispensado |

### 3.3 Equipes (`apps/equipes/`)

| Rota | Ação | Quem pode | Regra especial |
|---|---|---|---|
| `/projetos/<pk>/equipe/novo/` | criar | téc+ ou coordenador do projeto | aluno/docente não-coordenador → 403 |
| `/equipes/<pk>/editar/` | editar | idem | |
| `/equipes/<pk>/encerrar/` (POST) | editar | idem | deriva `ativo` de `data_saida` |
| `/equipes/<pk>/excluir/` (POST) | excluir | idem | auditado como `exclusao` |

### 3.4 Bolsas (`apps/bolsas/`)

| Rota | Ação | Quem pode | Regra especial |
|---|---|---|---|
| `/bolsas/` | visualizar | autenticado | aluno: só as próprias |
| `/bolsas/nova/` | criar | **só téc+** | criação manual/avulsa (fora do fluxo de cotas); regra de 1 bolsa ativa no form |
| `/bolsas/<pk>/` | visualizar | autenticado | aluno só a própria → senão 403 |
| `/bolsas/<pk>/editar/` | editar | téc+ ou coordenador do projeto da bolsa | |
| `/indicacoes/` | visualizar | téc+ veem todas; docente só as de suas propostas | aluno → 403; pendentes primeiro, depois **maior nota de projeto** (nulas por último) |
| `/indicacoes/<pk>/implementar/` | criar | **só téc+** | form de bolsa pré-preenchido (projeto/aluno/modalidade/datas); marca a indicação como `implementada` |
| `/bolsas/modalidades/` (+nova/editar) | CRUD | **téc+** (`perfil_required`) | aluno/docente → 403 |

### 3.5 Planos de trabalho e relatórios (`apps/relatorios/`)

| Rota | Ação | Quem pode | Regra especial |
|---|---|---|---|
| `/planos/` | visualizar | autenticado | aluno: só os próprios |
| `/planos/novo/` | criar | com Perfil | aluno: própria bolsa sem plano; docente: bolsas coordenadas; téc+: todas |
| `/planos/<pk>/editar/` | editar | téc+, coordenador ou **aluno dono** | aluno dono só em rascunho/reprovado e **não muda status**; `resumo` obrigatório; **status ≠ rascunho exige PDF** |
| `/planos/<pk>/arquivo/` | baixar o PDF | autenticado | **aluno só o próprio plano** → senão 403; sem arquivo → 404 |
| `/relatorios/` | visualizar | autenticado | aluno: só os próprios; docente: editáveis/avaliáveis só os coordenados |
| `/relatorios/novo/` | criar | com Perfil | mesmo escopo de bolsas (aluno próprio / docente coordenadas / téc+ todas) |
| `/relatorios/<pk>/editar/` | editar | téc+ sempre; aluno próprio e orientador em rascunho/reprovado | status final trava edição; `resumo` obrigatório; aceita upload do PDF (opcional) |
| `/relatorios/<pk>/arquivo/` | baixar o PDF | autenticado | **aluno só o próprio relatório** → senão 403; sem arquivo → 404 |
| `/relatorios/<pk>/submeter/` (POST) | editar | dono, orientador ou téc+ | **exige PDF anexado** (erro claro + nada muda); limpa avaliação anterior |
| `/relatorios/<pk>/avaliar/` | editar | **téc+ ou orientador ou co-orientador ativo** (função em `MembroEquipe`) | exige status `submetido`; exibe o **PDF do relatório** + resumo; nota ≥ mínima → aprovação automática |
| `/indicadores/` e `/indicadores/csv/` | visualizar | **téc+** (`perfil_required`) | |

### 3.6 Editais, propostas e avaliação (`apps/editais/`)

| Rota | Ação | Quem pode | Regra especial |
|---|---|---|---|
| `/editais/` e `/editais/<pk>/` | visualizar | autenticado | abaixo de técnicos: **só status em andamento** (lista filtrada + detalhe 403); busca `?q=` em **código, título ou descrição**; propostas: téc+ todas; demais só as próprias |
| `/editais/novo/`, `/editar/` | criar/editar | **téc+** | cria como `rascunho`; status só via ações; aceita upload do PDF (livre até a aprovação) |
| `/editais/<pk>/arquivo/` | baixar o PDF | autenticado | **mesma permissão do detalhe** (abaixo de técnicos, só `em_andamento` → 403); sem arquivo → 404; entrega `application/pdf` + `nosniff`, nunca por `/media/` público |
| `/editais/<pk>/acao/<acao>/` (POST) | fluxo | `aprovar` → **diretor+**; `iniciar/encerrar/cancelar` → téc+ | origem/destino do status validados; **`aprovar` exige PDF anexado** (erro claro + status não muda) |
| `/editais/<pk>/propostas/nova/` | criar | **somente docente** | aluno, téc+ e superusuário → 403 (não submetem); exige edital em andamento e no período, Pessoa vinculada e projeto do docente (coordena ou é membro) |
| `/propostas/<pk>/` | visualizar | téc+ OU submetente OU avaliador alocado | senão 403 |
| `/propostas/<pk>/editar/` | editar | téc+ ou submetente | só enquanto `submetida` |
| `/propostas/<pk>/indicar/` | criar indicação | téc+ OU submetente da proposta | só proposta `aprovada` e com cotas disponíveis; bloqueia aluno com bolsa ativa ou já indicado |
| `/propostas/<pk>/alocar/` | editar | **téc+** | banca múltipla; remoção/realocação |
| `/projetos/<pk>/alocar/` | alocar avaliadores de projeto | **téc+** | só após envio para avaliação; exclui a equipe do projeto (paridade) da lista; banca múltipla; **bloqueado** para projeto com nota automática (financiamento externo) |
| `/avaliacoes/<pk>/` | GET: avaliador ou téc+; POST: **só o avaliador** | | notas 0–10 por critério do **escopo** (`proposta`/`projeto`/`ambos`) + parecer; média ponderada; concluída recalcula a nota da proposta ou do projeto |
| `/avaliacoes/<pk>/remover/` (POST) | excluir | téc+ | recalcula proposta ou projeto (sem alocações → `submetido`) |
| `/criterios/` (+novo/editar) | CRUD | **téc+** | escopo (`proposta`/`projeto`/`ambos`) + pesos → nota final; aprovação por `Edital.nota_minima` |

### 3.7 Comprovantes (`apps/comprovantes/`)

| Rota | Ação | Quem pode | Regra especial |
|---|---|---|---|
| `/comprovantes/` | visualizar | autenticado | téc+ vê todos; demais: beneficiário ou emissor |
| `/comprovantes/<pk>/` | visualizar | idem | senão 403; página imprimível |
| `/comprovantes/emitir/bolsa/` | criar | elegível via queryset do form | aluno → bolsa própria; orientador/coorientador → orientandos; téc+ → todas |
| `/comprovantes/emitir/participacao/` | criar | coordenador/membro do projeto ou téc+ | não-gerente: beneficiário fixo = ele próprio; téc+ escolhe pessoa da equipe (validação `integra_equipe` no form) |
| `/comprovantes/emitir/avaliacao/` | criar | téc+ todas; demais só as que fez | beneficiário derivado do registro avaliado |
| `/comprovantes/verificar/<codigo>/` | visualizar | **público** (sem login) | verificação por código |

## 4. Observações conhecidas

1. **Superusuário não submete proposta** — `_pode_submeter` exige perfil
   aluno/docente; é consistente com o papel de administração (não titular).
2. **Emissão de comprovantes** barra elegibilidade pela *queryset* dos campos
   do formulário (validação do Django) — não há `raise PermissionDenied`
   explícito; POST direto com pk inválido → erro de form.
3. **Co-orientador avalia relatórios** desde que o vínculo em `MembroEquipe`
   (`funcao='coorientador'`) esteja **ativo** — encerrado o vínculo, perde o
   acesso (testado em `sgp/tests/test_relatorios.py`).
