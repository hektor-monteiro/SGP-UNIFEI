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
- Ciclo de vida: Criação → Publicação → Submissão → Avaliação → Resultado → Execução → Prestação de Contas
- Pode ser criado sobre demanda (não apenas por calendário)
- Técnico cria, Diretor/Pro-reitor valida

### 3.2 Modalidade de Bolsa
- Configurável pelo técnico (não hardcoded)
- Exemplos: PIBIC, PIBITI, PIVIC
- Permite criação de novas modalidades sem alteração de código

### 3.3 Fomentador
- Para bolsas: FAPEMIG, CNPq, UNIFEI, outros
- Fomento de bolsa ≠ fomento de projeto (conceitos separados)
- Bolsas são cotas institucionais alocadas pelos fomentadores

### 3.4 Projeto
- Pode ter fomento (recursos para pesquisa) ou não
- Pode ter múltiplas bolsas de fomentadores distintos
- Pode ter múltiplos membros (internos e externos)
- Docente coordenador: máximo 2 sem fomento, ilimitado com fomento

### 3.5 Bolsa
- Vinculada a um projeto
- Vinculada a um aluno (1 bolsa ativa por aluno)
- Vinculada a uma modalidade
- Vinculada a um fomentador

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

---

## 4. Indicadores e Relatórios

### Indicadores Governamentais e de Agências de Fomento
- Número de bolsas por modalidade e fomentador
- Número de projetos por departamento/área do conhecimento
- Taxa de conclusão de projetos
- Número de alunos que concluíram IC
- Distribuição por gênero, raça, região
- Número de publicações resultantes de projetos
- Número de membros externos em equipes
- Execução orçamentária

### Indicadores de Efetividade
- Evolução temporal de projetos e bolsas
- Taxa de sucesso em editais
- Tempo médio de conclusão de projetos
- Número de orientados por docente
- Taxa de retenção de alunos em IC

---

## 5. Conformidade com LGPD

- Consentimento explícito para coleta de dados
- Minimização de dados (coletar apenas o necessário)
- Direito de acesso, correção e exclusão
- Logs de auditoria (quem acessou o quê e quando)
- Política de retenção de dados
- Anonimização para relatórios estatísticos
- Nomeação de um DPO (Data Protection Officer)
- Relatório de Impacto à Proteção de Dados (RIPD)

---

## 6. Stack Tecnológica

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

## 7. Fases de Desenvolvimento

### Fase 1 — Levantamento de Requisitos ✓
- [x] Mapeamento de entidades
- [x] Regras de negócio
- [x] Hierarquia de permissões
- [x] Indicadores necessários
- [x] Requisitos de LGPD

### Fase 2 — Modelagem Detalhada
- [ ] Diagrama Entidade-Relacionamento (DER)
- [ ] Protótipos de telas
- [ ] Matriz de permissões detalhada
- [ ] Definição de indicadores (fórmulas e fontes)

### Fase 3 — Setup do Projeto
- [ ] Inicializar repositório git
- [ ] Configurar ambiente Docker
- [ ] Criar projeto Django + app inicial
- [ ] Configurar CI (GitHub Actions ou GitLab CI)

### Fase 4 — Desenvolvimento Incremental
- [ ] Módulo de Editais
- [ ] Módulo de Projetos
- [ ] Módulo de Bolsas
- [ ] Módulo de Equipes
- [ ] Módulo de Comprovantes
- [ ] Relatórios e Indicadores

---

## 8. Loop de Controle de Desenvolvimento

1. **Validação de Requisitos** — mapear entidades, regras, atores
2. **Revisão de Design** — modelar banco, arquitetura, segurança
3. **Implementação com Checkpoints** — pequenos incrementos, revisão após cada um
4. **Portões de Qualidade** — testes, type-check, lint, revisão manual
5. **Proteção contra Regressões** — backup, staging, rollback planejado
