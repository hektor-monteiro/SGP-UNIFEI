# SGP-UNIFEI — Guia de Avaliação

Pacote para **avaliação e análise de problemas** do Sistema de Gestão de Pesquisa
(SGP-UNIFEI) da Diretoria de Pesquisa e Inovação da UNIFEI.

> ⚠️ Ambiente de avaliação: dados fictícios, senhas padrão e chave secreta de
> desenvolvimento. **Não usar em produção** sem ajustes de segurança.

---

## 1. Requisitos

- **Docker** instalado — [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac) ou Docker Engine + Compose v2 (Linux)
- Aproximadamente **1,5 GB** de espaço em disco (imagens + banco)
- Porta **8000** livre (ou defina outra, ver item 4)
- Windows em arquitetura **ARM**: a imagem roda em emulação (mais lenta)

## 2. Instalação

| Sistema | Comando |
|---|---|
| Linux / Mac | `./instalar.sh` (se pedir permissão: `bash instalar.sh`) |
| Windows | duplo clique em **`instalar.bat`** |

Ou manualmente, na pasta do pacote:

```bash
docker load -i sgp-unifei-imagem.tar.gz
docker compose -f docker-compose.prod.yml up -d
```

Aguarde ~30 segundos (o sistema aplica migrações e semeia os dados sozinho).

## 3. Acessos

| URL | Usuário | Senha |
|---|---|---|
| `http://localhost:8000/` | — | — |
| `http://localhost:8000/contas/entrar/` | `aluno1` | `demo123` |
| idem | `docente1` | `demo123` |
| idem | `docente2` | `demo123` |
| idem | `tecnico1` | `demo123` |
| idem | `diretor1` | `demo123` |
| idem | `proreitor1` | `demo123` |
| `http://localhost:8000/admin/` | `admin` | `admin123` |

Perfis: **aluno < docente < técnico < diretor < pro-reitor**. Avalie sempre com
dois perfis diferentes para conferir as permissões.

## 4. Configurações opcionais

Antes de rodar o instalador, variáveis de ambiente alteram o padrão:

```bash
APP_PORT=8100          # outra porta HTTP
DB_PORT=5544           # outra porta para o PostgreSQL
BIND=0.0.0.0           # expor na rede local (padrão: só 127.0.0.1)
ADMIN_PASSWORD=xxx     # senha do admin
SEED_DEMO=0            # sem dados de demonstração
```

Exemplo: `APP_PORT=8100 ./instalar.sh`

No Windows (prompt de comando), antes de rodar o `instalar.bat`:

```bat
set APP_PORT=8100
```

## 5. Checklist de avaliação

Marque o que foi testado e anote o que falhar:

- [ ] **Login/logout** com `aluno1` e `docente1`; painel conforme o perfil
- [ ] **Projetos**: lista com filtros, detalhe, criação (docente/técnico+);
      edição pelo coordenador ou técnico+; aluno só enxerga projetos dos
      quais participa ou tem bolsa; busca por `?q=` em **código, título ou
      resumo**
- [ ] **Documentos em PDF** (editais, projetos, planos e relatórios): campo
      `Documento (PDF)` no formulário; **ação/submissão bloqueada sem o PDF**
      com mensagem clara — no edital é `Aprovar e validar`, nos demais é a
      submissão; o detalhe mostra a **descrição/resumo** e o link **"Abrir o
      PDF"** (rota autenticada — não é `/media/` público — abrindo em nova
      aba); anexar um arquivo que não seja PDF é recusado no servidor
- [ ] **Equipes** (no detalhe do projeto): técnico+ ou coordenador adiciona,
      edita, encerra e exclui membros; aluno não vê os botões
- [ ] **Bolsas**: aluno vê apenas a própria; regra de "1 bolsa ativa" ao editar
- [ ] **Planos de trabalho**: aluno cria/edita conforme o fluxo de status;
      docente vê os planos pelo painel e pelo projeto; status ≠ rascunho
      exige o PDF anexado
- [ ] **Relatórios do aluno**: criação/edição conforme status, submissão
      (exige PDF), nota do orientador/técnico com aprovação automática pela
      nota mínima, apenas um relatório final por bolsa; a **tela de
      avaliação mostra o PDF** a ser lido
- [ ] **Editais**: técnico cria (nascendo *rascunho*), só diretor/publica;
      ações do fluxo conforme perfil (iniciar/encerrar/cancelar);
      **aprovação bloqueada sem o PDF anexado**; busca por `?q=` em código,
      título ou descrição
- [ ] **Propostas**: aluno/docente submetem a edital aberto; técnico vê todas,
      cada um vê só as suas; edição só enquanto *submetida*
- [ ] **Critérios de avaliação**: técnico cria/edita com pesos; aluno só lê
- [ ] **Alocação**: técnico aloca docentes (múltiplos) e remove/realoca;
      painel do `tecnico1` lista propostas/projetos sem avaliador com a
      ação **Alocar Avaliador** (só téc+ vê a seção)
- [ ] **Avaliação**: painel do `docente1` mostra "Propostas a avaliar" com link;
      notas 0–10 por critério + parecer; nota final = média ponderada;
      aprovação automática pela nota mínima do edital
- [ ] **Avaliação por pares de projetos**: `docente1` envia o projeto pelo
      detalhe; `tecnico1` aloca avaliadores (a equipe é excluída) e a nota
      final vira indicador na fila de cotas; projeto com **financiamento
      externo** já nasce com **nota 10,00 automática** (envio e alocação
      dispensados)
- [ ] **Comprovantes**: emissão (bolsa/participação/avaliação) com elegibilidade;
      lista conforme visibilidade; verificação pública por código em
      `/comprovantes/verificar/`; página de detalhe imprimível (Ctrl+P)
- [ ] **Indicadores** (`tecnico1`): painel §5.1/§5.2 e botão **Baixar CSV**
      (aluno/docente recebem 403)
- [ ] **LGPD**: link no painel → `/lgpd/`; registrar consentimento; baixar
      "meus dados" (JSON); `/lgpd/auditoria/` com filtros só para técnico+
- [ ] **Permissões**: usuários sem perfil ou de nível inferior recebem **403**
- [ ] **Busca de nomes** (padrão do projeto): nos formulários com seleção de
      pessoa (avaliador, coordenador, aluno, membro) digite no campo **"Digite
      para filtrar…"** — filtra sem diferenciar acento/caixa, autopreenche
      quando sobra um único nome e mantém o dropdown
- [ ] **Responsividade** básica (tela de notebook/celular) e erros no console

## 6. Reportando um problema

Para cada problema, registre:

1. **Data/hora**, usuário logado e **URL** exata
2. Passos para reproduzir (sequência de cliques)
3. Comportamento esperado × obtido (print de tela)
4. **Logs** (se houver erro):

```bash
# Últimas linhas do log da aplicação
docker compose -f docker-compose.prod.yml logs --tail=200 app > log-app.txt

# Log interno do Django (erros com traceback)
docker compose -f docker-compose.prod.yml exec app tail -n 200 /app/logs/django.log > log-django.txt
```

Anexe os arquivos de log ao relato. A pasta `src/` do pacote contém o
código-fonte (commit gerado) para consulta durante a análise.

## 7. Parar, reiniciar e resetar

```bash
docker compose -f docker-compose.prod.yml stop      # parar (mantém dados)
docker compose -f docker-compose.prod.yml start     # reiniciar
docker compose -f docker-compose.prod.yml down -v   # APAGAR os dados e recomeçar
```

Os dados ficam num volume do Docker (`postgres_data`); `down` sem `-v`
mantém o banco.

## 8. Estrutura do pacote

```
SGP-UNIFEI-avaliacao-1.0/
├── sgp-unifei-imagem.tar.gz    # imagem já construída
├── docker-compose.prod.yml     # definição dos serviços
├── instalar.sh / instalar.bat  # instalação automatizada
├── README-AVALIACAO.md         # este arquivo
└── src/                        # código-fonte (referência)
```
