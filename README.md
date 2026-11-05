# DevFlow CLI — Azure Boards + Azure Repos + Git

**Versão 0.2.0 — Windows, macOS e Linux.** Ferramenta de linha de comando em Python 3.10+, sem dependências de runtime fora da biblioteca padrão. Instalação recomendada com `pipx` (recomenda-se Python 3.11+ para as versões atuais do pipx).

O líder distribui Work Items no Azure Boards e agenda a data. Cada desenvolvedor consulta as tarefas atribuídas, inicia uma branch com o ID do Work Item, faz commits vinculados e abre uma Pull Request. **Este projeto suporta Azure Repos + Azure Boards, não repositórios hospedados no GitHub.** O GitHub deste projeto serve apenas para distribuir a CLI.

> **Publicação pendente:** os exemplos abaixo apontam para `felipeflosii/devflow-cli`. Somente funcionarão **depois** que esse repositório for criado como público e receber estes arquivos.

## Instalação rápida

| Sistema | Pré-requisitos | Instalador |
|---|---|---|
| **Windows 10/11** | Python 3.11+, Git for Windows, pipx | `install.ps1` via PowerShell |
| **macOS** (Intel/Apple Silicon) | Python 3.11+, Git, pipx | `install.sh` via Bash |
| **Linux** (Zorin/Ubuntu) | Python 3.11+, Git, pipx | `install.sh` via Bash |

### Windows — PowerShell 5.1 ou PowerShell 7+

Instale [Python](https://www.python.org/downloads/windows/), [Git for Windows](https://git-scm.com/downloads/win) e [pipx](https://pipx.pypa.io/latest/how-to/install-pipx.html). Para instalar `pipx` quando o Python Launcher (`py`) estiver disponível:

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

**Abra um novo PowerShell** após configurar o PATH. Faça o download e revise o instalador:

```powershell
Invoke-WebRequest 'https://raw.githubusercontent.com/felipeflosii/devflow-cli/main/install.ps1' -OutFile install.ps1
Get-Content .\install.ps1
.\install.ps1
```

Caso a política de execução da sua máquina bloqueie o arquivo, uma alternativa temporária, **somente após verificar o script**, é:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

Para instalação em uma linha (menos segura, pois executa o conteúdo remoto sem revisão):

```powershell
irm https://raw.githubusercontent.com/felipeflosii/devflow-cli/main/install.ps1 | iex
```

O Windows PowerShell não precisa ter Bash ou WSL instalado. `irm` é o alias de `Invoke-RestMethod`, preferível a `curl` dentro do PowerShell.

### macOS — Terminal (zsh)

Pré-requisitos usando [Homebrew](https://brew.sh/):

```bash
brew install python git pipx
pipx ensurepath
```

Inspecione e execute:

```bash
curl -fsSLo devflow-install.sh https://raw.githubusercontent.com/felipeflosii/devflow-cli/main/install.sh
cat devflow-install.sh
bash devflow-install.sh
```

Ou instale diretamente:

```bash
curl -fsSL https://raw.githubusercontent.com/felipeflosii/devflow-cli/main/install.sh | bash
```

Funciona em macOS Intel e Apple Silicon, usando o Python/Git/pipx da própria máquina. Não é necessário compilar um executável específico.

### Linux — Zorin OS / Ubuntu

```bash
sudo apt update
sudo apt install -y python3 git pipx
pipx ensurepath
curl -fsSL https://raw.githubusercontent.com/felipeflosii/devflow-cli/main/install.sh | bash
```

Se a distro tiver Python 3.10, o pacote DevFlow pode funcionar, mas as versões atuais do pipx recomendam Python 3.11+; nesse caso, instale uma versão mais recente de Python ou use uma versão de pipx compatível.

### Sem instalador remoto, em qualquer sistema

Depois de instalar Git e pipx, use o pacote diretamente do repositório público:

```text
pipx install git+https://github.com/felipeflosii/devflow-cli.git
```

Atualização:

```text
pipx install --force git+https://github.com/felipeflosii/devflow-cli.git
```

Desinstalação:

```text
pipx uninstall devflow-ado
```

Em Windows com `pipx` instalado como módulo, troque `pipx` por `py -m pipx`.

## Configuração inicial (cada desenvolvedor)

1. Instale o [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) ou configure um PAT com permissão de acesso ao Azure DevOps.
2. Execute `az login` e autentique no tenant certo. Se não possuir assinatura Azure, pode tentar `az login --allow-no-subscriptions`.
3. Clone o repositório **hospedado no Azure Repos**, com credenciais Git configuradas por SSH ou Git Credential Manager.
4. Dentro da pasta clonada, rode os comandos abaixo (iguais nos três sistemas):

```bash
dev --version
dev init
dev doctor
dev tasks --all
```

`dev init` detecta organização, projeto e repositório quando o remote utiliza `https://dev.azure.com/ORG/PROJ/_git/REPO` ou `git@ssh.dev.azure.com:v3/ORG/PROJ/REPO`. É possível preencher explicitamente:

```bash
dev init --org MinhaOrg --project 'Meu Projeto' --repo MinhaAPI --base main --remote origin
```

A API do Azure DevOps usa automaticamente a sessão `az login` ou a variável de ambiente `ADO_PAT`. **Não coloque PAT em código nem em arquivos versionados**. A autenticação do Git para `git fetch/push` deve ser configurada separadamente.

Variável de sessão em **PowerShell** (exemplo de formato; não compartilhe o token):

```powershell
$env:ADO_PAT = Read-Host 'Cole seu PAT do Azure DevOps'
```

Em **Bash/zsh**:

```bash
read -rs ADO_PAT && export ADO_PAT && echo
```

## Fluxo de trabalho

Líder, à noite (o comando funciona em Windows, macOS e Linux):

```bash
dev new 'Implementar JWT' --assign pessoa@exemplo.com --date 2026-11-06
dev new 'Corrigir tela de login' --type Bug --assign dev2@exemplo.com --date 2026-11-06
# Tarefas já existentes:
dev assign 142 dev@exemplo.com
dev plan 142 --date 2026-11-06
```

Desenvolvedor, no dia seguinte:

```bash
dev tasks                      # Hoje e atrasadas
dev tasks --week               # Semana
dev tasks --all                # Todas as minhas tarefas abertas
dev dashboard                  # Escolher pelo numero no terminal
dev start 142                  # Cria e publica feature/142-titulo
dev current                    # Tarefa da branch atual
dev status                     # Status do Git e PR atual
dev save 'Adicionar JWT'       # Commit com AB#142 + push
dev finish                     # Push + PR vinculada ao Boards
dev sync                       # Apenas git fetch --prune
```

A agenda diária utiliza uma tag **`devday:AAAA-MM-DD`** nos Work Items. É possível cadastrá-la diretamente pelo Azure Boards ou usar `dev plan`. Tarefas sem essa tag aparecem em `dev tasks --all`. `dev start` exige que o Work Item esteja atribuído à conta autenticada.

## Segurança e restrições

- **Não realiza merge**, rebase, `reset --hard` ou `push --force`; políticas de revisão da `main` permanecem ativas.
- Recusa troca de branch com arquivos locais modificados; retoma branches existentes.
- Antes de commitar todos os arquivos pendentes (`git add -A`), solicita confirmação (a menos que use `--yes`).
- Bloqueia alguns nomes comuns de segredos (`.env`, `.pem`, `.key` etc.), mas isto **não substitui** revisão, `.gitignore` ou varredura de segredos.
- Quando o servidor recusa a associação de branch/PR ao Work Item, informa aviso; operações Git já realizadas não são desfeitas.
- Mantém apenas dados de configuração locais; não grava PAT ou token. As permissões de arquivo no Windows são as da conta do usuário.
- O `dev finish` **não encerra automaticamente a Task** no Azure Boards.

A configuração fica em:

| Sistema | Caminho |
|---|---|
| Windows | `%LOCALAPPDATA%\DevFlow\config.json` |
| macOS e Linux | `~/.config/devflow/config.json` (ou `$XDG_CONFIG_HOME/devflow/config.json`) |

## Testes e publicação

```bash
python -m unittest discover -s tests -v
```

Para executar os testes do código-fonte sem instalar (Bash/zsh): `PYTHONPATH=src python3 -m unittest discover -s tests -v`. No PowerShell: `$env:PYTHONPATH='src'; py -m unittest discover -s tests -v`.

O workflow `.github/workflows/tests.yml` configura **Windows, macOS e Ubuntu**, com Python 3.11 e 3.13, testes offline e verificação do CLI e da sintaxe dos instaladores. Ele só executará após a publicação no GitHub. A integração real com uma organização Azure DevOps ainda deve ser validada com uma Task de teste e `dev doctor` em cada plataforma.

Veja [docs/PUBLICAR_NO_GITHUB.md](docs/PUBLICAR_NO_GITHUB.md) para instruções de publicação, URLs e verificação. MIT License. **Projeto independente, não oficial da Microsoft.**
