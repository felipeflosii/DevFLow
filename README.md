# DevFlow CLI — Azure Boards + Azure Repos + Git

**Versão 0.4.1** — Linux (incluindo Zorin OS), macOS e Windows; Python 3.10+; **sem dependências de execução externas à biblioteca padrão**.

O DevFlow permite consultar as Tasks do Azure Boards pelo terminal, iniciar branches associadas ao ID da Task e criar commits e Pull Requests rastreáveis no Azure Repos. **O GitHub hospeda o código deste programa; as integrações Git de trabalho são exclusivamente com Azure Repos.**

## Novidades da v0.4.1

- **`dev finish` agora retorna automaticamente à branch principal** após enviar os commits, criar a PR e tentar vinculá-la ao Azure Boards. O retorno executa `git fetch <remote> --prune` e `git switch <base>` (por padrão `origin` e `main`).
- **A Pull Request continua aberta**, sem merge automático nem alterações no histórico da `main` local.
- **Falha ao trocar de branch não apaga a PR**: o CLI informa o aviso e orienta a executar `dev main`, sem repetir a criação da Pull Request.

## Recursos da v0.4.0

- **Novo `dev main`**: executa `git fetch origin --prune` e depois `git switch main`, usando os nomes de remote e branch base configurados em `dev init` (origin/main por padrão).
- Impede a troca de branch quando há modificações locais não salvas. Se a branch principal já existir localmente, utiliza essa branch (sem recriá-la); caso não exista, cria uma branch local rastreando a principal remota.
- **Sem `pull` automático**: atualizar as referências de `origin/main` não avança a `main` local. Para atualizá-la, execute explicitamente `git pull --ff-only origin main` após `dev main`.
- `dev sync` continua disponível para somente buscar as referências do remoto, mantendo a branch atual.

## Melhorias da v0.3.0

- `dev tasks` agora lista **todas as suas Tasks abertas**, mesmo sem data planejada. Não é necessário editar Due Date ou planejar tags para que apareçam.
- `dev tasks --all` lista **todas as Tasks abertas do projeto**, inclusive de outros membros e sem responsável. Exibe coluna **Responsável** abreviada (ex.: `Luiz F.`) e **PBI** pai (`#5`).
- `dev tasks --mine` equivale à listagem padrão, incluindo as tarefas sem data.
- `dev tasks --today`, `--week` e `--date AAAA-MM-DD` são filtros opcionais de data, usando a tag `devday:AAAA-MM-DD` (mantida por compatibilidade).
- `dev tasks --all --area 'Infraestrutura'` filtra por Area Path; `--closed` inclui finalizadas.
- `dev pbi`, `dev features`, `dev epics` e `dev workitems --all` consultam o backlog por tipo.
- `dev show <ID>` mostra dados do Work Item e sua hierarquia **Epic → Feature → PBI → Task**.
- `dev start <ID>`, `dev save` e `dev finish` exigem **Task**; PBIs, Features e Epics não podem iniciar um fluxo de código.

Exemplo de `dev tasks --all` (ilustrativo; dados reais vêm do Azure DevOps):

```text
Todas as Tasks abertas do projeto
=================================
ID  Estado       Planejada  Responsável    PBI  Título
--  -----------  ---------  -------------  ---  ----------------------------------------
6   To Do        sem data   Luiz F.        #5   Criar script de provisionamento da IA
7   In Progress  sem data   Maria S.       #5   Criar script de provisionamento do .NET
8   To Do        sem data   Não atribuído  #5   Validar provisionamento dos App Services

Total: 3 Task(s). Use: dev start <ID> | dev show <ID>
```

## Instalação e atualização

Requer **Python 3.10+**, Git, `pipx` (recomendado) e, para autenticação no Azure Boards, Azure CLI (`az login`) **ou** um PAT via variável de ambiente. A autenticação do Git (SSH/Git Credential Manager) é independente.

**Linux/macOS (instalação local a partir do ZIP):**

```bash
unzip devflow-cli-v0.4.1.zip
cd devflow-cli-v0.4.1
pipx install --force .
dev --version
```

**Windows / PowerShell (dentro da pasta descompactada):**

```powershell
py -m pipx install --force .
dev --version
```

**Depois de publicar no GitHub** `felipeflosii/devflow-cli`:

```bash
pipx install --force git+https://github.com/felipeflosii/devflow-cli.git
```

Os scripts `install.sh` e `install.ps1` fazem a instalação a partir do GitHub (após publicar o código da versão v0.4.1). Instalam na conta do usuário, sem `sudo`.

## Primeira configuração

Execute a CLI **dentro de um repositório clonado do Azure Repos**, por exemplo `zeroviagem-api-java`:

```bash
az login                            # ou configure ADO_PAT sem armazená-lo no repo
dev init                            # detecta org, projeto e repo a partir do remote origin
dev doctor                          # verifica Git, autenticação e APIs
dev main                            # fetch origin --prune + switch main (sem pull)
dev tasks                           # suas Tasks abertas, com ou sem data
dev tasks --all                     # todas as Tasks do projeto
```

Se a detecção automática falhar:

```bash
dev init --org VetSync --project 'GS2 - Azure DevOps' --repo zeroviagem-api-java
```

A configuração fica em `~/.config/devflow/config.json` no Linux/macOS (ou `$XDG_CONFIG_HOME/devflow/config.json`); no Windows, em `%LOCALAPPDATA%\DevFlow\config.json`. O programa **não salva tokens**.

## Referência de comandos

| Comando | Resultado |
|---|---|
| `dev tasks` | Suas Tasks abertas, incluindo sem data |
| `dev tasks --mine` | Mesmo resultado de `dev tasks` |
| `dev tasks --all` | Todas as Tasks abertas do projeto (coluna Responsável) |
| `dev tasks --today` | Suas Tasks planejadas para hoje e atrasadas |
| `dev tasks --week` | Suas Tasks planejadas até domingo e atrasadas |
| `dev tasks --date 2026-11-10` | Suas Tasks planejadas para uma data exata |
| `dev tasks --all --closed` | Todas as Tasks, incluindo concluídas |
| `dev tasks --all --area 'Infraestrutura'` | Tasks abertas na área informada |
| `dev pbi`, `dev features`, `dev epics` | Backlogs específicos |
| `dev workitems --all` | Tasks, PBIs, Features, Epics, Bugs e Issues |
| `dev show 8` | Detalhes e hierarquia do Work Item #8 |
| `dev dashboard` | Menu de suas Tasks abertas |
| `dev start 8` | Inicia/retoma branch para uma Task atribuída a você |
| `dev current`, `dev status` | Consulta trabalho e PR da branch atual |
| `dev save 'Implementar endpoint'` | Commit + push com `AB#ID` |
| `dev finish` | Faz push, cria PR e retorna à principal (fetch --prune + switch, sem merge/pull) |
| `dev sync` | `git fetch origin --prune` sem mudar sua branch |
| `dev main` | `git fetch origin --prune` + `git switch main` (sem pull) |
| `dev new 'Implementar JWT' --assign email@exemplo.com` | Cria Task |
| `dev plan 8 --date 2026-11-10` | Atribui `devday:2026-11-10` |
| `dev assign 8 email@exemplo.com` | Altera responsável |

Use `--json` com os comandos de listagem para obter os objetos originais da API Azure DevOps. O campo **PBI** da visualização tabular é resolvido a partir dos relacionamentos de hierarquia do Work Item (não de seu título). Caso não exista um PBI pai ou não haja permissão para consultá-lo, aparece `—`.

**Observação sobre datas:** `Iteration Path` define uma Sprint; isso não equivale a prazo de cada Task. O filtro de data do DevFlow usa a tag `devday:`; o padrão **não filtra por data**. O campo opcional `Due Date`, se criado no processo do Azure DevOps, não é requisito para listar Tasks.

## Segurança e limitações

- `dev start` exige uma Task **atribuída ao usuário autenticado**. `--all` pode visualizar Tasks alheias, mas não dá permissão para iniciá-las.
- Os comandos Git não fazem merge, rebase, `reset --hard` nem `push --force`. `dev finish` cria a PR e volta para a principal, mas **não a aprova**, não faz merge e não conclui a Task.
- Ao iniciar outra branch, exige árvore de trabalho limpa. Para `dev save`, solicita confirmação antes de `git add -A`, exceto com `--yes`.
- Bloqueia padrões comuns de arquivos sensíveis (`.env`, `.key`, `.pem`, etc.). Isso não substitui revisão manual nem scanner de segredos.
- O suporte a estados personalizados do Azure Boards é baseado em nomes conhecidos de estados concluídos; valide adaptações específicas do seu processo.
- Work Items do projeto são consultados em lotes (até 200 por pedido), com limite padrão da consulta WIQL de até 1.000 IDs por execução.
- A integração real com sua organização Azure DevOps depende da conectividade e das permissões do seu usuário.

## Testes e contribuição

Na raiz do repositório:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

No PowerShell:

```powershell
$env:PYTHONPATH='src'; py -m unittest discover -s tests -v
```

Todos os testes são locais, sem chamadas reais ao Azure DevOps. Consulte [`CHANGELOG.md`](CHANGELOG.md) para histórico e [`docs/PUBLICAR_NO_GITHUB.md`](docs/PUBLICAR_NO_GITHUB.md) para publicação.

**Licença MIT — Projeto independente, não oficial da Microsoft.**
