# DevFlow — Azure Boards + Git + Azure Repos no terminal

CLI em **Python 3.10+**, sem bibliotecas externas de runtime. Desenvolvida para o fluxo:

1. Lider planeja e atribui tarefas no Azure Boards.
2. Cada desenvolvedor roda `dev tasks` e ve as suas tarefas do dia.
3. `dev start 142` sincroniza `origin`, cria/publica `feature/142-titulo`, associa a branch ao Work Item e tenta mudar o estado para *Doing/In Progress/Active*.
4. Programador trabalha normalmente; `dev save "mensagem"` faz commit com `AB#142` e push.
5. `dev finish` cria commit pendente (apos confirmacao), faz push, abre PR para `main` e associa a PR a Task.

**Esta versao e para Azure Repos + Azure Boards (Azure DevOps Services).** GitHub nao esta integrado. A CLI nao faz merge, nao desativa branch policies e nao guarda tokens em arquivos de configuracao.

## Instalacao rapida pelo GitHub (apos publicacao)

Repositorio pretendido: https://github.com/felipeflosii/devflow-cli (este link so funcionara quando o repositorio publico for criado e os arquivos enviados).

Prerequisitos no Zorin OS / Ubuntu:

```bash
sudo apt update
sudo apt install -y git python3 pipx
pipx ensurepath
```

Instalacao via curl:

```bash
curl -fsSL https://raw.githubusercontent.com/felipeflosii/devflow-cli/main/install.sh | bash
```

O script usa `pipx` para instalar o programa diretamente do GitHub. **Antes de executar scripts baixados pela internet, prefira inspecionar o conteudo.** As instrucoes de publicacao e instalacao revisavel estao em [docs/PUBLICAR_NO_GITHUB.md](docs/PUBLICAR_NO_GITHUB.md).

Sem curl: `pipx install git+https://github.com/felipeflosii/devflow-cli.git`.

## 1. Instalacao local no Zorin OS / Ubuntu

Pre-requisitos: Git, Python 3.10+, Azure CLI ou um PAT de acesso ao Azure DevOps, e um clone local do repo **Azure Repos**.

```bash
sudo apt update
sudo apt install -y git python3 python3-venv pipx
pipx ensurepath
# Abra outro terminal para atualizar o PATH, ou rode: source ~/.zshrc
cd /CAMINHO/ONDE/EXTRAIU/devflow_cli
pipx install .
# Se ja estiver instalado: pipx reinstall devflow-ado
dev --help
```

Opcional, `uv tool install .` caso use [uv](https://docs.astral.sh/uv/).

**Azure CLI**: caso ja tenha instalada, faca:

```bash
az login
# se o usuario nao tiver assinatura Azure, tente: az login --allow-no-subscriptions
```

A autenticacao nas APIs usa automaticamente o token Entra da sua sessao Azure CLI. A conta deve ter acesso ao Azure DevOps **e ao tenant correto**. Para PAT como alternativa:

```bash
# Nao grave o PAT no repositorio, na linha de comando ou em um .env versionado.
read -rs 'ADO_PAT?Cole seu PAT Azure DevOps: ' && echo
export ADO_PAT
```

O `read -rs '...?'` acima e do **zsh**. No Bash: `read -rs -p 'Cole seu PAT: ' ADO_PAT; echo; export ADO_PAT`.

A conta tambem precisa de permissao de leitura/escrita no Boards, criacao de branches e criacao de PRs. Para uso com PAT, conceda apenas os escopos necessarios (Work Items Read/Write e Code Read/Write). Para `git push`, configure autenticacao do Git **separadamente**, por SSH ou Git Credential Manager; o token usado pela REST API nao autentica automaticamente os comandos Git.

## 2. Configuracao por repositorio (uma unica vez por desenvolvedor)

```bash
cd /CAMINHO/DO/REPOSITORIO
# Se o remote for https://dev.azure.com/ORG/PROJETO/_git/REPO, detecta automaticamente:
dev init
# Ou preencha explicitamente:
dev init --org MinhaOrganizacao --project 'Meu Projeto' --repo MinhaAPI --base main --remote origin

dev doctor
dev config
```

A configuracao fica em `~/.config/devflow/config.json`, associada ao caminho absoluto do repositório. Nao contem segredos e nao modifica arquivos do projeto.

Os remotes aceitos sao HTTPS `dev.azure.com/.../_git/...`, HTTPS legado `*.visualstudio.com` ou SSH `git@ssh.dev.azure.com:v3/...`.

## 3. Lider: planejar a noite anterior

Crie tarefas pela **interface Azure Boards** ou diretamente pelo CLI:

```bash
# Criar ja atribuida e agendada
# Exemplo de data, substitua pelo dia real do sprint
dev new 'Implementar JWT' --type Task --assign dev1@empresa.com --date 2026-11-06
dev new 'Corrigir erro de login' --type Bug --assign dev2@empresa.com --date 2026-11-06

# Atribuir uma Task existente e planejar o dia
dev assign 142 dev1@empresa.com
dev plan 142 --date 2026-11-06

# Planejar varias tarefas no mesmo dia
dev plan 142 143 144 --date 2026-11-06
```

**Como funciona a data?** Para evitar configurar campos personalizados, o DevFlow usa uma tag padronizada nos Work Items: `devday:2026-11-06`. O lider pode abrir a Task na interface do Azure Boards e adicionar essa tag manualmente, sem usar CLI. O `dev plan` substitui automaticamente outras tags de data `devday:` anteriores, mas preserva todas as demais. Tarefas sem essa tag aparecem em `dev tasks --all`, nao na agenda do dia.

## 4. Desenvolvedor: consultar, iniciar e finalizar

```bash
dev tasks                # Minhas tarefas agendadas para hoje + atrasadas
dev tasks --week         # Minha semana + atrasadas
dev tasks --all          # Todas as tarefas abertas (inclusive nao planejadas)
dev tasks --date 2026-11-06  # Apenas uma data
dev tasks --json         # Dados estruturados para automacoes
dev dashboard            # Menu interativo para escolher uma tarefa

dev start 142            # Valida atribuicao, fetch --prune, cria/publica branch, vincula ao Boards
dev current              # Mostra task da branch atual
dev status               # Mostra alteracoes locais e PR ativa
dev sync                 # Atualiza referencias remotas, sem rebase/merge/reset

dev save 'Implementar refresh token'  # Pede confirmacao para git add -A, commita AB#142 e faz push
dev finish                           # Comita mudancas pendentes, envia e abre PR vinculada
dev finish -m 'Concluir auth' --yes  # Sem confirmacao de inclusao de arquivos (use com cuidado)
```

O `dev start` sempre faz o checkout a partir de `origin/main` **nao mexe na main local**. Se a branch ja existir (local ou remota), ele a retoma em vez de recriar. Ao executar `dev finish`, o commit fica relacionado com a Task por `AB#ID`; a PR tambem recebe link de Work Item no Azure Boards via ArtifactLink.

`dev finish` **nao fecha** o Work Item nem mescla a PR: a revisao e o merge continuam governados pelas regras do Azure Repos. Apos o merge, o lider pode fechar a Task no Boards ou configurar automacao propria da organizacao.

## 5. Seguranca / cuidados

- Nunca roda `reset --hard`, `push --force`, rebase ou merge automatico.
- Rejeita troca de branch com alteracoes locais.
- Recusa `dev start ID` quando o Work Item nao esta atribuido ao usuario autenticado.
- Antes de `dev save` ou `dev finish`, lista arquivos pendentes e pede confirmacao para adicionar **todos** via `git add -A` (exceto com `--yes`). Revise a listagem.
- Bloqueia commit se identificar `.env`, chaves `.pem/.key/.p12/.pfx`, `secrets.json`, etc. ja no stage. Isso e uma verificacao limitada, **nao substitui .gitignore nem secret scanning**. Se bloquear, retire do stage (`git restore --staged <arquivo>`) e corrija `.gitignore`.
- Nenhum token/PAT e persistido pelo DevFlow. Restrinja permissoes Azure DevOps ao minimo necessario.
- O estado muda para *Doing*, *In Progress* ou *Active* somente se o fluxo de trabalho suportar uma dessas opcoes. Se nao suportar, a branch continua disponivel e aparece aviso.
- Se a API de vinculo do Boards falhar, a branch/PR permanece criada e sera informado um aviso. Verifique o Work Item manualmente.

## 6. Diagnostico

| Sintoma | Acao |
|---|---|
| `Nao foi possivel obter token` | `az login` no tenant correto, ou `export ADO_PAT` |
| `HTTP 401/403` | Verifique acesso a organizacao e escopos do PAT/permissoes |
| `git push` pede senha | Configure SSH ou Git Credential Manager; a autenticacao da API e independente |
| Task nao aparece em `dev tasks` | Confira `Assigned To`, status aberto e tag `devday:AAAA-MM-DD`; tente `dev tasks --all` |
| `Task nao atribuida a voce` | Lider precisa preencher `Assigned To` com a identidade da conta conectada |
| `Estado nao alterado` | Processo Boards possui estados personalizados; ajuste no ADO |
| `Repositorio/remote divergente` | Execute `dev init` com o nome correto de projeto/repositorio |
| PR ja existe | Continue pela PR existente no Azure Repos; DevFlow nao cria duplicadas ativas |

## 7. Testes locais

```bash
cd devflow_cli
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

As suites sao **offline**, com mocks para Azure DevOps. O projeto nao possui dados nem credenciais de clientes. A integracao com uma organizacao real do Azure DevOps deve ser validada pelo time com `dev doctor` e uma Task de teste antes de adotar em producao.

## Documentacao tecnica / endpoints

- Microsoft: Azure DevOps WIQL e Work Items Batch, REST 7.1.
- Microsoft: acesso com token Azure CLI via recurso `499b84ac-1321-427f-aa17-267ca6975798`.
- Microsoft: Azure Git Repos Pull Requests API, REST 7.1.
- Relacoes ArtifactLink de branch e PR no formato `vstfs:///Git/...`.

## Licenca

MIT. Ferramenta independente, nao oficial da Microsoft.
