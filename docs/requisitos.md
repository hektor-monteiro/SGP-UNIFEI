# Sistema de Gestão de Pesquisa (SGP-UNIFEI)

## Documento de Requisitos

**Universidade Federal de Itajubá (UNIFEI)**
**Diretoria de Pesquisa e Inovação**

**Data:** 03/10/2026
**Status:** Em desenvolvimento

---

## 1. Visão Geral

O SGP-UNIFEI é um sistema web para gerenciar os processos de pesquisa da diretoria de pesquisa da UNIFEI. O sistema substitui o gerenciamento atual baseado em planilhas Excel e Google Forms, centralizando o registro e monitoramento de projetos de pesquisa, bolsas de iniciação científica, editais, membros de equipes e emissão de comprovantes.

### Escopo
- **Usuários:** 500-600 docentes, 5000-10000 alunos, técnicos administrativos, diretores e pro-reitor
- **Substitui:** Planilhas Excel, Google Forms
- **Integração futura:** SIGAA (sistema acadêmico da UNIFEI)

---

## 2. Atores e Permissões

### Hierarquia de Perfis (do menor para o maior)

| Perfil | Permissões |
|--------|------------|
| **Aluno** | Cadastro pessoal, plano de trabalho, relatórios específicos |
| **Docente/Orientador** | Tudo do aluno + gestão de projetos e membros da equipe |
| **Técnico Administrativo** | Gestão de processos de discentes e docentes, criar/gerenciar editais e avaliações — **alterações precisam de validação do diretor ou pro-reitor** |
| **Diretor de Pesquisa** | Acesso total + poder de validação |
| **Pro-reitor de Pesquisa e Inovação** | Acesso total + validação geral (nível máximo) |

### Regras de Orientação e Coordenação

| Regra | Detalhe |
|-------|---------|
| Docente sem fomento | Máximo **2 projetos** como coordenador |
| Docente com fomento | **Sem limite** de projetos como coordenador |
| Aluno | **1 orientador + 1 co-orientador** (único) |
| Aluno | **1 bolsa ativa** por vez |
| Projeto | Múltiplos membros (alunos, docentes, técnicos, externos) |

---

## 3. Entidades do Sistema

### 3.1 Edital
- Ciclo de vida: Criação → Aprovação (Diretoria/Reitoria) → Submissão → Avaliação → Resultado → Execução → Prestação de Contas
- Pode ser criado sobre demanda (não apenas por calendário)
- Técnico cria, Diretor/Pro-reitor **aprova** (valida)
- **Recebe propostas apenas quando "Em Andamento"** e no período informado — após a aprovação, um técnico+ (ou perfil superior) inicia a execução
- **Propostas = solicitação de cotas**: submetidas por **docente** (projeto + nº de cotas); o aluno é indicado pelo docente só depois que as cotas são aprovadas (§3.5)
- **Visibilidade**: editais fora de "Em Andamento" não aparecem para perfis abaixo de técnico (aluno e docente veem apenas os em execução; na proposta, a referência ao edital oculto aparece como texto, sem link)

### 3.2 Modalidade de Bolsa
- Configurável pelo técnico (não hardcoded)
- Exemplos: PIBIC, PIBITI, PIVIC
- Permite criação de novas modalidades sem alteração de código

### 3.3 Fomentador
- Para bolsas: FAPEMIG, CNPq, UNIFEI, outros
- Fomento de bolsa ≠ fomento de projeto (conceitos separados)
- Bolsas são cotas institucionais alocadas pelos fomentadores

### 3.4 Projeto
- Código único **gerado pelo sistema** no padrão `PVDI###-AAAA` (sequencial global + ano de registro; pode ser sobrescrito)
- **ODS obrigatório**: ao menos um dos 17 Objetivos de Desenvolvimento Sustentável (checkboxes)
- **Área de Conhecimento obrigatória** conforme a tabela do CNPq: Grande Área → Área → Subárea (cascata com validação de coerência)
- Pode ter fomento (recursos para pesquisa) ou não
- Pode ter múltiplas bolsas de fomentadores distintos
- Pode ter múltiplos membros (internos e externos)
- Docente coordenador: máximo 2 sem fomento, ilimitado com fomento

### 3.5 Bolsa
- Vinculada a um projeto
- Vinculada a um aluno (1 bolsa ativa por aluno)
- Vinculada a uma modalidade
- Vinculada a um fomentador
- **Fluxo de cotas**: o docente submete a proposta no edital em andamento apontando **projeto + nº de cotas**; após a aprovação na avaliação, ele **indica os alunos** (limite = cotas aprovadas; aluno já com bolsa ativa é bloqueado); o **técnico implementa a bolsa** a partir da indicação, com formulário pré-preenchido (projeto, aluno, modalidade do edital)
- **Criação manual de bolsa**: somente técnico+ (casos avulsos, fora de edital) — o docente não cria bolsa, ele indica o aluno

### 3.6 Aluno
- Cadastro pessoal
- Plano de trabalho
- Relatórios específicos
- 1 orientador + 1 co-orientador

### 3.7 Docente
- Coordenador de projetos
- Orientador ou co-orientador de alunos
- Gestão de projetos e membros da equipe

### 3.8 Membro de Equipe
- Tipos: Aluno, Docente, Técnico Administrativo, Colaborador Externo
- Vínculo com projeto: data de entrada, data de saída, função/papel
- **Exclusão de membro exige justificativa obrigatória**, registrada no log de auditoria LGPD (§6)

### 3.9 Plano de Trabalho
- Vinculado ao aluno e ao projeto

### 3.10 Relatório
- Parcial ou final
- Vinculado ao aluno e ao projeto
- Deve gerar indicadores para prestação de contas

### 3.11 Comprovante
- Emitido a partir de dados do sistema
- Tipos:
  1. **Comprovante de Bolsa** → Aluno (IC, voluntária ou com bolsa), Docente (orientador ou co-orientador)
  2. **Comprovante de Participação em Projeto** → Coordenador, Membros da equipe
  3. **Comprovante de Avaliação** → Avaliador de editais, Avaliador de relatórios finais

### 3.12 Avaliação
- De propostas (submetidas a editais)
- De relatórios finais
- De processos de avaliação de editais

### 3.13 Usuário
- Perfil de acesso
- Vínculo com pessoa (aluno, docente, técnico, etc.)

### 3.14 Instituto/Departamento
- Unidade acadêmica vinculada ao projeto ou membro
- Exemplos: IMC, ISEE, IFQ, IRN, EXCEN/PROEX
- Usado para agrupar projetos e indicadores

### 3.15 Processo SIPAC
- Número do processo administrativo federal (SIPAC)
- Vinculado ao projeto
- Formato: número único por projeto

### 3.16 Avaliação de Relatório
- Nota quantitativa (ex: 9.8, 9.1, 8.5)
- Observações sobre entrega de relatório
- Vinculada ao projeto e ao membro avaliador

---

## 4. Análise da Planilha Atual (Dados Existentes)

### 4.1 Estrutura da Planilha

A planilha atual possui **4 abas**:

| Aba | Registros | Descrição |
|-----|-----------|-----------|
| **GERAL** | 2.853 linhas | Projetos ativos/vigentes |
| **ARQUIVADOSEXPIRADOS** | 4.424 linhas | Projetos arquivados ou expirados |
| **Página20** | 1.507 linhas | Projetos mais recentes (com códigos novos) |
| **CANCELADOS** | 1.013 linhas | Projetos cancelados |

### 4.2 Colunas Reais (Campos Existentes)

```
Código | Título do Projeto | Data de Registro | Início | Término | Status
Financiador | Recursos Internos | Recursos Externos | Participação início e fim
Equipe | Matrícula | Instituto Vinculado | Função | Carga Horária
Nº Processo SIPAC | Entrega de relatório (observações) | Nota
```

### 4.3 Descobertas Importantes

**1. Cada linha = um membro da equipe (não um projeto)**
- Um projeto com 5 membros ocupa 5 linhas
- Os dados do projeto se repetem em cada linha
- Isso indica que a estrutura real é: Projeto 1:N Membros

**2. Funções identificadas na planilha:**
- `Coordenador`
- `Docente`
- `Docente externo`
- `Discente`

**3. Códigos de projeto:**
- Antigos: números simples (642, 645, etc.)
- Novos: formato `PVDI494-2024`, `PIDI239-2022` (sigla + número + ano)

**4. Nº Processo SIPAC** — sistema administrativo federal (processo físico/digital)

**5. Campo "Nota"** — avaliação quantitativa (ex: 9.8, 9.1, 8.5)

**6. Campo "Entrega de relatório"** — texto livre com observações

**7. Problemas de qualidade de dados:**
- Datas armazenadas como números seriais em algumas células
- Campo "Participação início e fim" como texto livre (ex: "12/2017 a 05/2024")
- Colunas vazias além da coluna 17 (a maioria das 87 colunas está vazia)

### 4.4 Comparação: Modelo Proposto vs. Realidade

| Aspecto | Modelo Proposto | Realidade (Planilha) |
|---------|-----------------|----------------------|
| **Estrutura** | Uma linha por projeto | Uma linha por membro da equipe |
| **Financiador** | Entidade separada | Texto livre na coluna |
| **Recursos** | Não detalhado | Recursos Internos + Recursos Externos (valores) |
| **Avaliação** | Entidade separada | Coluna "Nota" + texto de observações |
| **Processo** | Não mapeado | Nº Processo SIPAC |
| **Instituto** | Não mapeado | Coluna "Instituto Vinculado" |
| **Carga horária** | Não mapeado | Coluna "Carga Horária" |
| **Matrícula** | Não mapeado | Coluna "Matrícula" |

### 4.5 Entidades Adicionais Identificadas

Com base na planilha, identificamos entidades que não estavam no modelo inicial:

1. **Instituto/Departamento** — "Instituto Vinculado" (IMC, ISEE, IFQ, IRN, etc.)
2. **Processo SIPAC** — número de processo administrativo federal
3. **Avaliação de Relatório** — nota + observações sobre entrega

---

## 5. Indicadores e Relatórios

### 5.1 Indicadores Governamentais e de Agências de Fomento
- Número de bolsas por modalidade e fomentador
- Número de projetos por departamento/área do conhecimento
- Taxa de conclusão de projetos
- Número de alunos que concluíram IC
- Distribuição por gênero, raça, região
- Número de publicações resultantes de projetos
- Número de membros externos em equipes
- Execução orçamentária

### 5.2 Indicadores de Efetividade
- Evolução temporal de projetos e bolsas
- Taxa de sucesso em editais
- Tempo médio de conclusão de projetos
- Número de orientados por docente
- Taxa de retenção de alunos em IC

---

## 6. Conformidade com LGPD

- Consentimento explícito para coleta de dados
- Minimização de dados (coletar apenas o necessário)
- Direito de acesso, correção e exclusão
- Logs de auditoria (quem acessou o quê e quando)
- Política de retenção de dados
- Anonimização para relatórios estatísticos
- Nomeação de um DPO (Data Protection Officer)
- Relatório de Impacto à Proteção de Dados (RIPD)

---

## 7. Stack Tecnológica

| Camada | Tecnologia |
|--------|------------|
| Backend | Python + Django |
| API | Django REST Framework |
| Banco de Dados | PostgreSQL |
| Frontend | Django Templates + HTMX |
| Cache/Filas | Redis |
| Deploy | Docker + Docker Compose |
| Proxy Reverso | Nginx |

---

## 8. Fases de Desenvolvimento

### Fase 1 — Levantamento de Requisitos ✓
- [x] Mapeamento de entidades
- [x] Regras de negócio
- [x] Hierarquia de permissões
- [x] Indicadores necessários
- [x] Requisitos de LGPD

### Fase 2 — Modelagem Detalhada
- [x] Diagrama Entidade-Relacionamento (DER) — `docs/der.md`
- [ ] Protótipos de telas (não aplicável — telas implementadas diretamente;
      o inventário de rotas/quem acessa está em `docs/permissoes.md`)
- [x] Matriz de permissões detalhada — `docs/permissoes.md`
- [x] Definição de indicadores (fórmulas e fontes) — `docs/indicadores.md`

### Fase 3 — Setup do Projeto
- [x] Inicializar repositório git
- [x] Configurar ambiente Docker
- [x] Criar projeto Django + app inicial
- [x] Configurar CI (`.github/workflows/ci.yml` — ativa no primeiro push;
      verificação local via `./scripts/verificar.sh`)

### Fase 4 — Desenvolvimento Incremental
- [x] Autenticação e permissões (§2)
- [x] Módulo de Projetos
- [x] Módulo de Equipes
- [x] Módulo de Bolsas
- [x] Planos de trabalho
- [x] Módulo de Editais
- [x] Avaliação de propostas
- [x] Relatórios do aluno
- [x] Módulo de Comprovantes
- [x] Relatórios e Indicadores
- [x] Conformidade LGPD (§6)

---

## 9. Loop de Controle de Desenvolvimento

1. **Validação de Requisitos** — mapear entidades, regras, atores
2. **Revisão de Design** — modelar banco, arquitetura, segurança
3. **Implementação com Checkpoints** — pequenos incrementos, revisão após cada um
4. **Portões de Qualidade** — testes, type-check, lint, revisão manual
5. **Proteção contra Regressões** — backup, staging, rollback planejado
