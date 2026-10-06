# Diagrama Entidade-Relacionamento (DER) — SGP-UNIFEI

**Data:** 03/10/2026
**Status:** Em desenvolvimento

---

## 1. Visão Geral

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DIAGRAMA ENTIDADE-RELACIONAMENTO                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐         ┌──────────────┐         ┌──────────────────┐        │
│  │  Edital  │──1:N──▶│  Proposta    │──N:1──▶│   Projeto        │        │
│  └──────────┘         └──────────────┘         └──────────────────┘        │
│       │                                            │    │    │              │
│       │                                            │    │    │              │
│       ▼                                            ▼    │    ▼              │
│  ┌──────────┐                              ┌──────────┐ │ ┌──────────┐     │
│  │Avaliação │                              │  Bolsa   │ │ │Comprovan-│     │
│  │(proposta)│                              └──────────┘ │ │te        │     │
│  └──────────┘                                   │      │ └──────────┘     │
│                                                  │      │                    │
│  ┌──────────┐         ┌──────────────┐          │      │ ┌──────────┐     │
│  │Modalidade│──1:N──▶│   Bolsa      │◀─────────┘      │ │  Plano   │     │
│  │de Bolsa  │         └──────────────┘                 │ │Trabalho  │     │
│  └──────────┘                                          │ └──────────┘     │
│       ▲                                                │        │         │
│       │                                                │        ▼         │
│  ┌──────────┐         ┌──────────────┐                 │ ┌──────────┐     │
│  │Fomentador│──1:N──▶│   Bolsa      │                 │ │Relatório │     │
│  │(bolsa)   │         └──────────────┘                 │ └──────────┘     │
│  └──────────┘                                          │                    │
│                                                        │                    │
│  ┌──────────┐         ┌──────────────┐    ┌──────────────┐                │
│  │Instituto │──1:N──▶│   Pessoa     │◀───│   Membro     │                │
│  │          │         │(Aluno/Docente)│    │  de Equipe   │                │
│  └──────────┘         └──────────────┘    └──────────────┘                │
│                              │                   │                         │
│                              │                   │                         │
│                              ▼                   ▼                         │
│                       ┌──────────────┐    ┌──────────────┐                │
│                       │   Usuário    │    │   Projeto    │                │
│                       │  (autentica) │    │  (coordena)  │                │
│                       └──────────────┘    └──────────────┘                │
│                                                                             │
│  ┌──────────┐         ┌──────────────┐         ┌──────────────────┐        │
│  │Fomentador│──1:N──▶│   Projeto    │         │  Processo SIPAC  │        │
│  │(projeto) │         │  (fomento)   │         │                  │        │
│  └──────────┘         └──────────────┘         └──────────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Entidades Detalhadas

### 2.1 Edital

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | UUID | PK | Identificador único |
| codigo | VARCHAR(50) | Sim | Código do edital (ex: PIBIC-2024-01) |
| titulo | VARCHAR(255) | Sim | Título do edital |
| descricao | TEXT | Não | Descrição detalhada |
| data_inicio | DATE | Sim | Data de abertura |
| data_fim | DATE | Sim | Data de encerramento |
| status | ENUM | Sim | Status: `rascunho`, `aprovado`, `em_andamento`, `encerrado`, `cancelado` |
| modalidade_id | UUID | FK → ModalidadeBolsa | Modalidade de bolsa associada |
| criado_por | UUID | FK → Usuário | Técnico que criou |
| validado_por | UUID | FK → Usuário | Diretor/Pro-reitor que validou |
| data_validacao | TIMESTAMP | Não | Data de validação |
| criado_em | TIMESTAMP | Sim | Data de criação |
| atualizado_em | TIMESTAMP | Sim | Data de última atualização |

---

### 2.2 ModalidadeBolsa

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | UUID | PK | Identificador único |
| sigla | VARCHAR(20) | Sim | Sigla (ex: PIBIC, PIBITI, PIVIC) |
| nome | VARCHAR(100) | Sim | Nome completo |
| descricao | TEXT | Não | Descrição da modalidade |
| ativo | BOOLEAN | Sim | Se está ativa |
| criado_em | TIMESTAMP | Sim | Data de criação |

---

### 2.3 Fomentador

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | UUID | PK | Identificador único |
| sigla | VARCHAR(20) | Sim | Sigla (ex: FAPEMIG, CNPq, UNIFEI) |
| nome | VARCHAR(100) | Sim | Nome completo |
| tipo | ENUM | Sim | `bolsa` ou `projeto` |
| ativo | BOOLEAN | Sim | Se está ativo |
| criado_em | TIMESTAMP | Sim | Data de criação |

---

### 2.4 Projeto

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | UUID | PK | Identificador único |
| codigo | VARCHAR(50) | Sim | Código do projeto (ex: PVDI494-2024) |
| titulo | VARCHAR(500) | Sim | Título do projeto |
| resumo | TEXT (1000) | Sim no formulário | Texto curto exibido na tela e usado na busca (`?q=` em código/título/resumo). Substitui a antiga `descricao` |
| arquivo_pdf | VARCHAR (upload) | Não¹ | Documento do projeto em PDF (`uploads/projetos/AAAA/MM/`), validado no servidor (extensão, tamanho ≤ 15 MB, assinatura `%PDF-`) |
| data_registro | DATE | Sim | Data de registro na DIP |
| data_inicio | DATE | Sim | Data de início |
| data_termino | DATE | Não | Data de término (pode ser prorrogado) |
| status | ENUM | Sim | `vigente`, `expirado`, `cancelado`, `arquivado`, `concluido` |
| status_avaliacao | ENUM | Sim (default `nao_submetido`) | Ciclo da avaliação por pares: `nao_submetido`, `submetido`, `em_avaliacao`, `avaliada` |
| nota | DECIMAL(4,2) | Não | Nota da avaliação por pares (média das avaliações concluídas) ou **10,00 automática** com financiamento externo — indicador de alocação de bolsas |
| nota_automatica | BOOLEAN | Sim (default `false`) | `true` quando a nota veio da regra de financiamento externo (recursos externos > 0 → nota 10,00 automática) |
| fomentador_id | UUID | FK → Fomentador | Fomentador do projeto (se houver) |
| recursos_internos | DECIMAL(12,2) | Não | Recursos internos (R$) |
| recursos_externos | DECIMAL(12,2) | Não | Recursos externos (R$) |
| coordenador_id | UUID | FK → Pessoa | Docente coordenador |
| processo_sipac_id | UUID | FK → ProcessoSipac | Número do processo SIPAC |
| instituto_id | UUID | FK → Instituto | Instituto vinculado |
| proposta_id | UUID | FK → Proposta | Proposta que originou o projeto |
| grande_area_id | BIGINT | FK → GrandeAreaConhecimento | Grande Área do CNPq¹ |
| area_id | BIGINT | FK → AreaConhecimento | Área do CNPq¹ |
| subarea_id | BIGINT | FK → SubareaConhecimento | Subárea do CNPq¹ |
| criado_em | TIMESTAMP | Sim | Data de criação |
| atualizado_em | TIMESTAMP | Sim | Data de última atualização |

¹ Obrigatório no formulário (cadeia coerente GA → Área → Subárea); nulo no
banco por compatibilidade com registros antigos à migração. A ficha **ODS**
(≥ 1 item) é uma relação N:N — ver §2.16.

² O PDF é obrigatório **apenas na submissão** para avaliação por pares
(`POST /projetos/<pk>/submeter/`); criar e editar fica livre. O arquivo é
entregue por rota autenticada `GET /projetos/<pk>/arquivo/` (mesma
permissão do detalhe) — nunca por `/media/` público (LGPD).

---

### 2.5 Proposta

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | UUID | PK | Identificador único |
| edital_id | UUID | FK → Edital | Edital submetido |
| projeto_id | UUID | FK → Projeto (nulo em registros antigos) | Projeto que solicita as cotas |
| cotas | INT | Sim (default 1) | Cotas de bolsa solicitadas |
| titulo | VARCHAR(500) | Sim | Título da proposta |
| resumo | TEXT | Não | Resumo da proposta |
| submetido_por | UUID | FK → Pessoa | Docente que submeteu |
| data_submissao | TIMESTAMP | Sim | Data de submissão |
| status | ENUM | Sim | `submetida`, `em_avaliacao`, `aprovada`, `reprovada`, `desclassificada` |
| nota_final | DECIMAL(4,2) | Não | Nota final da avaliação |
| criado_em | TIMESTAMP | Sim | Data de criação |

---

### 2.6 Bolsa

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | UUID | PK | Identificador único |
| projeto_id | UUID | FK → Projeto | Projeto vinculado |
| aluno_id | UUID | FK → Pessoa | Aluno bolsista |
| modalidade_id | UUID | FK → ModalidadeBolsa | Modalidade da bolsa |
| fomentador_id | UUID | FK → Fomentador | Fomentador da bolsa |
| data_inicio | DATE | Sim | Data de início da bolsa |
| data_fim | DATE | Sim | Data de término da bolsa |
| status | ENUM | Sim | `ativa`, `encerrada`, `cancelada`, `suspensa` |
| valor_mensal | DECIMAL(8,2) | Não | Valor mensal da bolsa |
| criado_em | TIMESTAMP | Sim | Data de criação |
| atualizado_em | TIMESTAMP | Sim | Data de última atualização |

---

### 2.7 Pessoa

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | UUID | PK | Identificador único |
| nome | VARCHAR(255) | Sim | Nome completo |
| email | VARCHAR(255) | Sim | E-mail institucional |
| cpf | VARCHAR(14) | Não | CPF |
| matricula | VARCHAR(20) | Não | Matrícula (para alunos) |
| tipo | ENUM | Sim | `aluno`, `docente`, `tecnico`, `externo` |
| instituto_id | UUID | FK → Instituto | Instituto vinculado |
| lattes | VARCHAR(255) | Não | Link para currículo Lattes |
| ativo | BOOLEAN | Sim | Se está ativo |
| criado_em | TIMESTAMP | Sim | Data de criação |
| atualizado_em | TIMESTAMP | Sim | Data de última atualização |

---

### 2.8 MembroEquipe

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | UUID | PK | Identificador único |
| projeto_id | UUID | FK → Projeto | Projeto vinculado |
| pessoa_id | UUID | FK → Pessoa | Pessoa membro |
| funcao | ENUM | Sim | `coordenador`, `orientador`, `coorientador`, `docente`, `discente`, `tecnico`, `externo` |
| carga_horaria | INTEGER | Não | Carga horária semanal (horas) |
| data_entrada | DATE | Sim | Data de entrada no projeto |
| data_saida | DATE | Não | Data de saída do projeto |
| ativo | BOOLEAN | Sim | Se está ativo no projeto |
| criado_em | TIMESTAMP | Sim | Data de criação |

---

### 2.9 PlanoTrabalho

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | UUID | PK | Identificador único |
| bolsa_id | UUID | FK → Bolsa | Bolsa vinculada |
| aluno_id | UUID | FK → Pessoa | Aluno responsável |
| titulo | VARCHAR(255) | Sim | Título do plano |
| resumo | TEXT (1000) | Sim no formulário | Texto curto exibido na tela e usado na busca. Substitui `descricao`/`objetivos`/`metodologia`/`cronograma` |
| arquivo_pdf | VARCHAR (upload) | Não¹ | Plano completo em PDF (`uploads/planos/AAAA/MM/`) — obrigatório para sair de `rascunho` |
| status | ENUM | Sim | `rascunho`, `submetido`, `aprovado`, `reprovado` |
| data_submissao | TIMESTAMP | Não | Data de submissão |
| data_aprovacao | TIMESTAMP | Não | Data de aprovação |
| criado_em | TIMESTAMP | Sim | Data de criação |
| atualizado_em | TIMESTAMP | Sim | Data de última atualização |

¹ Redação completa vive no PDF; o sistema guarda apenas metadados +
`resumo`. Entrega por `GET /planos/<pk>/arquivo/` (aluno só vê os
próprios planos) — nunca por `/media/` público (LGPD).

---

### 2.10 Relatorio

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | UUID | PK | Identificador único |
| bolsa_id | UUID | FK → Bolsa | Bolsa vinculada |
| aluno_id | UUID | FK → Pessoa | Aluno responsável |
| tipo | ENUM | Sim | `parcial`, `final` |
| titulo | VARCHAR(255) | Sim | Título do relatório |
| resumo | TEXT (1000) | Sim no formulário | Texto curto exibido na tela e usado na busca. Substituiu `conteudo` |
| arquivo_pdf | VARCHAR (upload) | Não¹ | Relatório completo em PDF (`uploads/relatorios/AAAA/MM/`) — obrigatório para submeter |
| periodo_inicio | DATE | Não | Início do período |
| periodo_fim | DATE | Não | Fim do período |
| status | ENUM | Sim | `rascunho`, `submetido`, `avaliado`, `aprovado`, `reprovado` |
| nota | DECIMAL(4,2) | Não | Nota de avaliação |
| observacoes | TEXT | Não | Observações do avaliador |
| data_submissao | TIMESTAMP | Não | Data de submissão |
| data_avaliacao | TIMESTAMP | Não | Data de avaliação |
| avaliado_por | UUID | FK → Pessoa | Avaliador |
| criado_em | TIMESTAMP | Sim | Data de criação |
| atualizado_em | TIMESTAMP | Sim | Data de última atualização |

¹ Redação completa vive no PDF (link exibido no detalhe **e** na tela de
avaliação). Entrega por `GET /relatorios/<pk>/arquivo/` com a mesma
permissão do detalhe — nunca por `/media/` público (LGPD).

---

### 2.11 Comprovante

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | UUID | PK | Identificador único |
| tipo | ENUM | Sim | `bolsa`, `participacao_projeto`, `avaliacao` |
| pessoa_id | UUID | FK → Pessoa | Pessoa beneficiária |
| projeto_id | UUID | FK → Projeto | Projeto vinculado (se aplicável) |
| bolsa_id | UUID | FK → Bolsa | Bolsa vinculada (se aplicável) |
| edital_id | UUID | FK → Edital | Edital vinculado (se aplicável) |
| descricao | TEXT | Não | Descrição do comprovante |
| data_inicio | DATE | Não | Início do período |
| data_fim | DATE | Não | Fim do período |
| carga_horaria | INTEGER | Não | Carga horária total |
| codigo_verificacao | VARCHAR(32) | Sim | Código de verificação único |
| emitido_por | UUID | FK → Usuário | Usuário que emitiu |
| emitido_em | TIMESTAMP | Sim | Data de emissão |
| arquivo | VARCHAR(255) | Não | Caminho do arquivo PDF |

---

### 2.12 Avaliacao

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | UUID | PK | Identificador único |
| tipo | ENUM | Sim | `proposta`, `relatorio`, `edital`, `projeto` |
| proposta_id | UUID | FK → Proposta | Proposta avaliada (se tipo=proposta) |
| projeto_id | UUID | FK → Projeto | Projeto avaliado por pares (se tipo=projeto) |
| relatorio_id | UUID | FK → Relatorio | Relatório avaliado (se tipo=relatorio) |
| avaliador_id | UUID | FK → Pessoa | Avaliador |
| alocado_por_id | UUID | FK → Usuario | Técnico+ que alocou a avaliação |
| status | ENUM | Sim | `alocada`, `concluida` |
| nota | DECIMAL(4,2) | Sim | Nota da avaliação |
| parecer | TEXT | Não | Parecer do avaliador |
| data_avaliacao | TIMESTAMP | Sim | Data da avaliação |
| criado_em | TIMESTAMP | Sim | Data de criação |

---

### 2.13 Instituto

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | UUID | PK | Identificador único |
| sigla | VARCHAR(20) | Sim | Sigla (ex: IMC, ISEE, IFQ, IRN) |
| nome | VARCHAR(100) | Sim | Nome completo |
| ativo | BOOLEAN | Sim | Se está ativo |
| criado_em | TIMESTAMP | Sim | Data de criação |

---

### 2.14 ProcessoSipac

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | UUID | PK | Identificador único |
| numero | VARCHAR(30) | Sim | Número do processo SIPAC |
| descricao | TEXT | Não | Descrição do processo |
| data_abertura | DATE | Não | Data de abertura |
| criado_em | TIMESTAMP | Sim | Data de criação |

---

### 2.15 Usuario

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | UUID | PK | Identificador único |
| pessoa_id | UUID | FK → Pessoa | Pessoa vinculada |
| username | VARCHAR(150) | Sim | Nome de usuário |
| senha | VARCHAR(255) | Sim | Senha (hash) |
| perfil | ENUM | Sim | `aluno`, `docente`, `tecnico`, `diretor`, `proreitor` |
| ativo | BOOLEAN | Sim | Se está ativo |
| ultimo_login | TIMESTAMP | Não | Último acesso |
| criado_em | TIMESTAMP | Sim | Data de criação |
| atualizado_em | TIMESTAMP | Sim | Data de última atualização |

---

### 2.16 Catálogos de Referência (ODS e Áreas do Conhecimento)

Dados de referência carregados pela migração `projetos.0004`
(fonte: `apps/projetos/data/catalogo_cnpq_ods.json` — Tabela de Áreas do
Conhecimento do CNPq/Lattes de 30/06/2025 e os 17 ODS da ONU em pt-BR).

**ODS** (17 registros)

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | BIGINT | PK | Identificador único |
| numero | SMALLINT | Sim | Número do ODS (1–17, único) |
| nome | VARCHAR(120) | Sim | Nome do ODS |

**GrandeAreaConhecimento** (9 registros) · **AreaConhecimento** (87) ·
**SubareaConhecimento** (366)

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | BIGINT | PK | Identificador único |
| codigo | VARCHAR(10) | Sim | Código CNPq de 8 dígitos (único) |
| nome | VARCHAR(150) | Sim | Nome do nível |
| grande_area_id | BIGINT | FK → GrandeAreaConhecimento | Só em AreaConhecimento |
| area_id | BIGINT | FK → AreaConhecimento | Só em SubareaConhecimento |

---

### 2.17 Indicacao

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | UUID | PK | Identificador único |
| proposta_id | UUID | FK → Proposta | Proposta **aprovada** com cotas disponíveis |
| aluno_id | UUID | FK → Pessoa | Aluno indicado para a cota |
| indicado_por | UUID | FK → Pessoa (nulo) | Docente/técnico que indicou |
| status | ENUM | Sim | `pendente`, `implementada` |
| bolsa_id | UUID | FK → Bolsa (nulo, 1:1) | Bolsa criada na implementação |
| criado_em | TIMESTAMP | Sim | Data de criação |
| atualizado_em | TIMESTAMP | Sim | Data de última atualização |

---

### 2.18 Critério de Avaliação (CriterioAvaliacao)

Catálogo global gerido por técnico+; alimenta a média ponderada das
avaliações (projetos por pares e cotas em editais).

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| id | UUID | PK | Identificador único |
| nome | VARCHAR(100) | Sim (único) | Nome do critério (ex: Impacto e inovação) |
| escopo | ENUM | Sim (default `proposta`) | Onde o critério vale: `proposta`, `projeto`, `ambos` |
| descricao | TEXT | Não | Descrição |
| peso | DECIMAL(5,2) | Sim | Peso na média ponderada (maior que zero) |
| ativo | BOOLEAN | Sim | Se está ativo |
| criado_em | TIMESTAMP | Sim | Data de criação |
| atualizado_em | TIMESTAMP | Sim | Data de última atualização |

---

## 3. Relacionamentos

| Origem | Destino | Cardinalidade | Descrição |
|--------|---------|---------------|-----------|
| Edital | Proposta | 1:N | Um edital tem várias propostas |
| Projeto | Proposta | 1:N | Uma proposta solicita cotas de um projeto do docente |
| Proposta | Indicacao | 1:N | Proposta aprovada gera uma indicação por cota |
| Indicacao | Bolsa | 1:1 | A implementação cria a bolsa da indicação |
| Pessoa | Indicacao | 1:N | Aluno pode ser indicado em várias propostas; docente indica nas dele |
| Projeto | Bolsa | 1:N | Um projeto tem várias bolsas |
| Projeto | MembroEquipe | 1:N | Um projeto tem vários membros |
| Pessoa | MembroEquipe | 1:N | Uma pessoa pode ser membro de vários projetos |
| Bolsa | PlanoTrabalho | 1:1 | Uma bolsa tem um plano de trabalho |
| Bolsa | Relatorio | 1:N | Uma bolsa tem vários relatórios |
| ModalidadeBolsa | Bolsa | 1:N | Uma modalidade tem várias bolsas |
| Fomentador | Bolsa | 1:N | Um fomentador financia várias bolsas |
| Fomentador | Projeto | 1:N | Um fomentador financia vários projetos |
| Instituto | Pessoa | 1:N | Um instituto tem várias pessoas |
| Instituto | Projeto | 1:N | Um instituto tem vários projetos |
| Pessoa | Usuario | 1:1 | Uma pessoa tem um usuário |
| Projeto | ProcessoSipac | 1:1 | Um projeto tem um processo SIPAC |
| Proposta | Avaliacao | 1:N | Uma proposta tem várias avaliações |
| Projeto | Avaliacao | 1:N | Um projeto tem avaliações por pares (tipo=projeto) |
| Relatorio | Avaliacao | 1:N | Um relatório tem várias avaliações |
| Pessoa | Comprovante | 1:N | Uma pessoa tem vários comprovantes |
| Projeto | Comprovante | 1:N | Um projeto tem vários comprovantes |
| Projeto | ODS | N:N | ODS pertinentes ao projeto (mínimo 1) |
| Projeto | GrandeAreaConhecimento | N:1 | Grande Área do CNPq |
| Projeto | AreaConhecimento | N:1 | Área do CNPq |
| Projeto | SubareaConhecimento | N:1 | Subárea do CNPq |
| GrandeAreaConhecimento | AreaConhecimento | 1:N | Uma grande área tem várias áreas |
| AreaConhecimento | SubareaConhecimento | 1:N | Uma área tem várias subáreas |

---

## 4. Restrições de Integridade

### 4.1 Regras de Negócio

| # | Regra | Implementação |
|---|-------|---------------|
| 1 | Aluno pode ter apenas 1 bolsa ativa | UNIQUE constraint em `bolsa(aluno_id)` WHERE `status = 'ativa'` |
| 2 | Docente sem fomento: máximo 2 projetos como coordenador | Validação em `MembroEquipe` |
| 3 | Docente com fomento: sem limite de projetos | Validação em `MembroEquipe` |
| 4 | Aluno: 1 orientador + 1 co-orientador | Validação em `MembroEquipe` |
| 5 | Projeto pode ter múltiplas bolsas de fomentadores distintos | FK múltiplas em `Bolsa` |
| 6 | Técnico propõe → Diretor/Pro-reitor valida | Campo `validado_por` em `Edital` |
| 7 | Uma indicação por aluno por proposta | UNIQUE em `indicacao(proposta_id, aluno_id)` |
| 8 | Indicação só em proposta `aprovada` e dentro do limite de cotas | Validação em `proposta_indicar` |
| 9 | Bolsa nasce da indicação: implementação é só de téc+ | Validação em `indicacao_implementar` |
| 10 | Avaliação por pares: a equipe do projeto (coordenador e membros) não avalia o próprio projeto | Exclusão da equipe em `projeto_alocar` |
| 11 | Nota do projeto = média das avaliações concluídas; exibida como indicador e ordena a fila de indicações (maior nota primeiro) | `_recalcular_projeto` + template de indicação/implementação + `indicacoes_lista` |
| 12 | Critérios de avaliação valem conforme o escopo (`proposta`/`projeto`/`ambos`) | Filtro em `avaliacao_detalhe` |
| 13 | Projeto com financiamento externo (`recursos_externos > 0`) recebe **nota 10,00 automática** e dispensa avaliação por pares; ao remover os recursos volta ao fluxo de avaliação | `Projeto.save()` + `nota_automatica` + bloqueio em `projeto_alocar` |

### 4.2 Constraints

```sql
-- Aluno só pode ter uma bolsa ativa
CREATE UNIQUE INDEX idx_bolsa_ativa_por_aluno
ON bolsa (aluno_id)
WHERE status = 'ativa';

-- Código de verificação único do comprovante
CREATE UNIQUE INDEX idx_codigo_verificacao
ON comprovante (codigo_verificacao);

-- Processo SIPAC único por projeto
CREATE UNIQUE INDEX idx_processo_sipac_projeto
ON projeto (processo_sipac_id);
```

---

## 5. Mapeamento Planilha → Modelo Relacional

| Coluna da Planilha | Entidade | Campo |
|--------------------|----------|-------|
| Código | Projeto | codigo |
| Título do Projeto | Projeto | titulo |
| Data de Registro | Projeto | data_registro |
| Início | Projeto | data_inicio |
| Término | Projeto | data_termino |
| Status | Projeto | status |
| Financiador | Fomentador | nome |
| Recursos Internos | Projeto | recursos_internos |
| Recursos Externos | Projeto | recursos_externos |
| Participação início e fim | MembroEquipe | data_entrada, data_saida |
| Equipe | Pessoa | nome |
| Matrícula | Pessoa | matricula |
| Instituto Vinculado | Instituto | sigla |
| Função | MembroEquipe | funcao |
| Carga Horária | MembroEquipe | carga_horaria |
| Nº Processo SIPAC | ProcessoSipac | numero |
| Entrega de relatório | Relatorio | observacoes |
| Nota | Relatorio | nota |

---

## 6. Índices Sugeridos

| Tabela | Campo | Tipo | Motivo |
|--------|-------|------|--------|
| Projeto | codigo | UNIQUE | Busca por código |
| Projeto | status | INDEX | Filtro por status |
| Projeto | coordenador_id | INDEX | Busca por coordenador |
| Projeto | instituto_id | INDEX | Filtro por instituto |
| Bolsa | aluno_id | INDEX | Busca por aluno |
| Bolsa | status | INDEX | Filtro por status |
| Bolsa | projeto_id | INDEX | Busca por projeto |
| Pessoa | email | UNIQUE | Login |
| Pessoa | matricula | UNIQUE | Busca por matrícula |
| MembroEquipe | projeto_id | INDEX | Busca por projeto |
| MembroEquipe | pessoa_id | INDEX | Busca por pessoa |
| Comprovante | codigo_verificacao | UNIQUE | Verificação |
| Comprovante | pessoa_id | INDEX | Busca por pessoa |

---

## 7. Enumerações

### Status do Projeto
- `vigente` — Em execução
- `expirado` — Prazo encerrado
- `cancelado` — Cancelado
- `arquivado` — Arquivado
- `concluido` — Concluído com sucesso

### Status da Avaliação do Projeto (por pares)
- `nao_submetido` — Ainda não enviado pelo coordenador
- `submetido` — Enviado, aguardando alocação de avaliadores
- `em_avaliacao` — Ao menos um avaliador alocado
- `avaliada` — Todas as alocações concluídas (`nota` preenchida) ou **nota 10,00 automática** por financiamento externo

### Escopo do Critério de Avaliação
- `proposta` — Vale na avaliação de cotas dos editais
- `projeto` — Vale na avaliação por pares de projetos
- `ambos` — Vale nos dois fluxos

### Status do Edital
- `rascunho` — Em elaboração
- `aprovado` — Validado pela Diretoria/Reitoria (ainda não recebe propostas)
- `em_andamento` — Em execução e **aberto para submissão** de propostas
- `encerrado` — Finalizado
- `cancelado` — Cancelado

### Status da Bolsa
- `ativa` — Em vigência
- `encerrada` — Finalizada
- `cancelada` — Cancelada
- `suspensa` — Temporariamente suspensa

### Status da Indicação
- `pendente` — Aluno indicado, aguardando o técnico implementar a bolsa
- `implementada` — Bolsa criada a partir da indicação

### Função do Membro
- `coordenador` — Coordenador do projeto
- `orientador` — Orientador do aluno
- `coorientador` — Co-orientador do aluno
- `docente` — Docente membro da equipe
- `discente` — Aluno membro da equipe
- `tecnico` — Técnico administrativo
- `externo` — Colaborador externo

### Perfil do Usuário
- `aluno` — Aluno
- `docente` — Docente
- `tecnico` — Técnico administrativo
- `diretor` — Diretor de Pesquisa
- `proreitor` — Pro-reitor de Pesquisa e Inovação

### Tipo de Relatório
- `parcial` — Relatório parcial
- `final` — Relatório final

### Tipo de Comprovante
- `bolsa` — Comprovante de bolsa
- `participacao_projeto` — Comprovante de participação em projeto
- `avaliacao` — Comprovante de avaliação

---

## 8. Próximos Passos

- [ ] Validar DER com stakeholders
- [ ] Criar protótipos de telas
- [ ] Definir matriz de permissões detalhada
- [ ] Configurar projeto Django
- [ ] Implementar modelos (models.py)
- [ ] Criar migrações iniciais
