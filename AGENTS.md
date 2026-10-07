# AGENTS.md

Este arquivo fornece diretrizes para agentes de IA (e desenvolvedores) trabalhando neste repositório.

---

## Objetivo do Projeto

Sistema de Gestão de Pesquisa (SGP-UNIFEI) para a Diretoria de Pesquisa e Inovação da Universidade Federal de Itajubá. Gerencia projetos de pesquisa, bolsas de iniciação científica (PIBIC, PIBITI, PIVIC), editais, membros de equipe, emissão de comprovantes e relatórios de indicadores.

**Stack:** Python + Django + PostgreSQL + Docker

**Documento de requisitos:** `docs/requisitos.md`

---

## Comandos de Execução

```bash
# Subir ambiente de desenvolvimento
docker compose up -d

# Criar migrações
docker compose exec app python manage.py makemigrations

# Aplicar migrações
docker compose exec app python manage.py migrate

# Criar superusuário
docker compose exec app python manage.py createsuperuser

# Acessar shell do Django
docker compose exec app python manage.py shell

# Parar ambiente
docker compose down
```

---

## Comandos de Testes / Lint / Typecheck / Build

```bash
# Testes
docker compose exec app python manage.py test

# Lint (ruff — configurado em ruff.toml; dependência em requirements-dev.txt)
docker compose exec app ruff check .

# Verificação completa local (lint + testes) — espelho do CI
./scripts/verificar.sh

# Typecheck (TODO: configurar mypy)
# docker compose exec app mypy .

# Build de produção
docker compose -f docker-compose.prod.yml build
```

---

## Regras de Estilo de Código e Organização de Arquivos

### Python / Django
- Seguir PEP 8
- Usar type hints em funções públicas
- Docstrings em português para funções e classes
- Nomes de modelos em português (ex: `Projeto`, `Bolsa`, `Edital`)
- Nomes de campos em português (ex: `data_inicio`, `titulo`, `status`)
- `snake_case` para variáveis e funções
- `PascalCase` para classes

### Organização de Arquivos
```
sgp/
├── config/             # Configurações do Django (settings, urls, wsgi)
├── apps/
│   ├── core/           # Modelos base, mixins, utilitários
│   ├── projetos/       # App de projetos
│   ├── bolsas/         # App de bolsas
│   ├── editais/        # App de editais
│   ├── equipes/        # App de membros de equipe
│   ├── comprovantes/   # App de comprovantes
│   └── relatorios/     # App de relatórios e indicadores
├── templates/          # Templates HTML
├── static/             # Arquivos estáticos (CSS, JS, imagens)
└── tests/              # Testes organizados por app
```

### Commits
- Mensagens em português
- Formato: `tipo: descrição curta`
- Tipos: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
- Um commit por mudança lógica

---

## Regras de Aprovação para Comandos de Shell

### Comandos que NÃO exigem aprovação (safe)
- `git status`, `git log`, `git diff`
- `ls`, `find`, `grep`, `cat`
- `python manage.py migrate --check`
- `python manage.py check`
- `docker compose ps`
- `docker compose logs`

### Comandos que EXIGEM aprovação do usuário
- Qualquer comando que modifique arquivos fora do diretório do projeto
- `docker compose down` (pode perder dados não persistidos)
- `docker compose exec app python manage.py flush`
- `git push` para branch principal (atual: `main` em `origin` → GitHub)
- `git reset --hard`
- `rm` ou `rm -rf`
- Comandos que instalam pacotes (`pip install`, `npm install`)
- Comandos que modificam configurações do sistema

---

## Regras para Edições Seguras de Arquivos

1. **Sempre ler o arquivo antes de editar** — nunca editar sem ver o conteúdo atual
2. **Usar a ferramenta `edit` para mudanças pontuais** — não reescrever arquivos inteiros desnecessariamente
3. **Preservar indentação e estilo existente** — não misturar tabs e espaços
4. **Não editar arquivos de configuração do sistema** (`.env`, `docker-compose.yml`) sem revisão explícita
5. **Não editar arquivos gerados automaticamente** (migrations, `requirements.txt` via pip) sem entender o impacto
6. **Fazer backup antes de edições amplas** — usar git stash ou commit antes
7. **Não commitar arquivos sensíveis** — `.env`, credenciais, dados pessoais

---

## Regra para Inspecionar e Planejar Antes de Edições Amplas

Antes de fazer edições que afetam mais de 3 arquivos ou que mudam a estrutura do projeto:

1. **Inspecionar** — ler todos os arquivos que serão afetados
2. **Planejar** — descrever o que será alterado e por quê
3. **Validar** — confirmar com o usuário se o plano está correto
4. **Executar** — fazer as edições em commits pequenos e separados
5. **Verificar** — rodar testes/lint após as edições

**Para edições amplas (refatoração, mudança de arquitetura, renomeação de modelos):**
- Criar um plano por escrito antes de executar
- Obter aprovação explícita do usuário
- Executar em branches separadas
- Fazer rollback se algo der errado

---

## Regra para Manter Cada Milestone Pequeno e Revisável

- **Um milestone = uma funcionalidade completa e testável**
- Não misturar funcionalidades não relacionadas no mesmo milestone
- Cada milestone deve ser revisável em menos de 30 minutos
- Commits pequenos e frequentes (a cada mudança lógica concluída)
- Se um milestone está grande demais, dividir em sub-milestones

**Exemplos de milestones adequados:**
- [OK] "Modelo de dados de Projetos com CRUD completo"
- [OK] "Autenticação e permissões básicas"
- [MUITO GRANDE] "Sistema completo de bolsas com editais e comprovantes"

---

## Regra para Evitar Refatorações Não Relacionadas

- **Não refatorar código que não está sendo modificado** na tarefa atual
- **Não reformatar arquivos inteiros** apenas por preferência estética
- **Não renomear variáveis/classes** sem motivo funcional
- **Não atualizar dependências** em commits de funcionalidade
- Se encontrar código problemático durante uma tarefa, **anotar e discutir** antes de refatorar

---

## Expectativas de Verificação no Navegador

Após implementar uma funcionalidade:

1. **Subir o ambiente** — `docker compose up -d`
2. **Acessar a aplicação** — `http://localhost:8000`
3. **Testar o fluxo manualmente** — criar, editar, visualizar e excluir registros
4. **Verificar permissões** — testar com diferentes perfis de usuário
5. **Verificar responsividade** — testar em diferentes tamanhos de tela
6. **Verificar erros no console** — abrir DevTools e checar erros de JS/console
7. **Testar edge cases** — campos vazios, dados inválidos, permissões negadas

---

## Expectativas de Revisão de Diff

Antes de considerar qualquer tarefa concluída:

1. **Revisar o diff completo** — `git diff` ou `git diff --cached`
2. **Verificar se não há arquivos sensíveis** — sem `.env`, sem credenciais
3. **Verificar se não há código debug** — sem `print()`, `console.log()`, `breakpoint`
4. **Verificar se não há imports não utilizados**
5. **Verificar se as mensagens de commit são claras**
6. **Verificar se os testes estão passando**
7. **Verificar se o lint está limpo**

---

## Convenções de Código

### Python
- Type hints em funções públicas
- Docstrings em português
- `snake_case` para variáveis e funções
- `PascalCase` para classes

### HTML/Templates
- Indentação com 2 espaços
- Atributos em português quando aplicável
- Comentários em português

### CSS
- `kebab-case` para classes
- Comentários em português

### JavaScript
- `camelCase` para variáveis e funções
- Comentários em português
- **Seleção de nomes em formulários** segue o padrão do projeto: declarar
  `campos_busca = ('campo',)` no form (mixin `BuscaNomeMixin` de
  `apps/core/forms.py`) marca o `<select>` com a classe `busca-nome`; o
  `templates/base.html` carrega `static/js/busca_nome.js`, que insere o campo
  "Digite para filtrar…" acima do dropdown (filtro sem acento/caixa +
  autopreenchimento com um único resultado). Usar em **qualquer** campo que
  liste pessoas — ex.: `avaliador`, `coordenador`, `aluno`, `pessoa`

### Upload de documentos (PDF)
- **Campo de arquivo**: `FileField(upload_to='uploads/<tipo>/AAAA/MM/', blank=True, validators=[validar_pdf])`
  em `apps/core/validators.py` (extensão `.pdf` + assinatura `%PDF-` +
  limite de 15 MB) + `campo_arquivo = 'arquivo_pdf'` na classe, que deve
  herdar `ModeloComArquivo` (`apps/core/models.py`) para apagar o arquivo
  substituído/órfão do disco
- **`request.FILES`**: toda view que usa formulário com arquivo precisa de
  `Form(request.POST, request.FILES, ...)` e o `<form>` precisa de
  `enctype="multipart/form-data"` — sem isso o upload é **silenciosamente
  ignorado**
- **Nunca servir `/media/`**: usar `servir_pdf(caminho)`
  (`apps/core/arquivos.py`) em uma rota autenticada que aplique a mesma
  permissão da tela de detalhe (LGPD). Arquivos ficam em `MEDIA_ROOT`
  (volume `media_data` no `docker-compose.prod.yml`; já no `.gitignore` e
  `.dockerignore`)
- **Testes de upload**: arquivo vai **dentro do dict de dados** do client
  do Django (`data['arquivo_pdf'] = SimpleUploadedFile(...)`, não há
  parâmetro `files=`); `sgp/tests/arquivos_teste.py` traz o mixin
  `MediaTemporariaMixin` (evita gravar em `media/`), `PDF_EXEMPLO` e
  `anexar_pdf(objeto)`

---

## TODOs Pendentes

- [x] Definir ferramenta de lint (ruff — `ruff.toml` + `requirements-dev.txt`)
- [ ] Definir ferramenta de typecheck (mypy, pyright, etc.)
- [x] Configurar CI/CD (`.github/workflows/ci.yml` — no ar no GitHub: run #1 verde em 07/10/2026, com lint (ruff), 440 testes e build da imagem; badge no `README.md`; **branch protegida ainda pendente — só se configura na UI do GitHub**)
- [ ] Definir cobertura de testes mínima
- [ ] Configurar ambiente de staging
- [ ] Definir processo de deploy
- [ ] Configurar Sentry ou similar para monitoramento de erros
