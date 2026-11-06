# Instalação, atualização e remoção do DevFlow CLI v1.0.0

O DevFlow é um pacote Python de linha de comando. `pipx` cria um ambiente isolado para ele, sem modificar as dependências do Python de seus projetos.

## 1. Antes de começar

Requisitos: **Git**, **Python >=3.10**, **pipx**, conexão para instalar o pacote e acesso autorizado ao Azure DevOps Services. A interface em tela cheia depende de um terminal TTY; os demais comandos funcionam sem interface. Dependência de execução instalada pelo pipx: `prompt_toolkit>=3.0.36,<4`.

**Atenção:** `az` (Azure CLI) é necessário quando você usa autenticação Entra com `az login`. Também é possível utilizar um PAT, definido na variável de ambiente `ADO_PAT` ou `AZURE_DEVOPS_EXT_PAT`. Não compartilhe o PAT e nunca salve em `.env` versionado, scripts ou arquivos do repositório.

## 2. Linux (Zorin OS / Ubuntu)

```bash
sudo apt update
sudo apt install -y python3 git pipx
pipx ensurepath
```

Abra um novo terminal após `pipx ensurepath`. Instale a release fixada:

```bash
pipx install 'git+https://github.com/felipeflosii/devflow-cli.git@v1.0.0'
dev --version
```

Se preferir o instalador animado (Bash), **inspecione antes de executar**:

```bash
curl -fsSLo install-devflow.sh https://raw.githubusercontent.com/felipeflosii/devflow-cli/v1.0.0/install.sh
cat install-devflow.sh
bash install-devflow.sh
```

O instalador procura Python, Git e pipx, executa o `pipx install --force` e ajusta o PATH. A barra representa **três etapas concluídas**, não a velocidade ou percentual de bytes baixados.

## 3. macOS

Com Homebrew:

```bash
brew install python git pipx
pipx ensurepath
pipx install 'git+https://github.com/felipeflosii/devflow-cli.git@v1.0.0'
```

O mesmo `install.sh` é compatível com macOS. Em instalações com múltiplos Pythons, valide `python3 --version` e `pipx list`.

## 4. Windows 10/11 (PowerShell)

Instale Python 3.10+ e Git for Windows. Instale `pipx` conforme seu gerenciador de pacotes; por exemplo, com Python Launcher:

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

Abra uma nova sessão PowerShell e execute:

```powershell
pipx install 'git+https://github.com/felipeflosii/devflow-cli.git@v1.0.0'
dev --version
```

Para usar o instalador com `Write-Progress`:

```powershell
Invoke-WebRequest 'https://raw.githubusercontent.com/felipeflosii/devflow-cli/v1.0.0/install.ps1' -OutFile install.ps1
Get-Content .\install.ps1
.\install.ps1
```

O PowerShell pode bloquear a execução de arquivos conforme a política local. Revise o arquivo e consulte a política de execução do sistema antes de alterar configurações. O instalador não solicita privilégios administrativos.

## 5. Autenticação no Azure DevOps

### Opção A — Azure CLI (recomendada quando disponível)

```bash
az login
```

Em tenants sem assinatura Azure, o comando `az login --allow-no-subscriptions` pode ajudar. O token para Azure DevOps é obtido pelo CLI quando necessário; a autenticação Git ao realizar `git fetch/push` pode exigir configuração adicional (Git Credential Manager ou SSH).

### Opção B — PAT

Configure um PAT da sua organização com somente os escopos necessários. Exemplo no Bash/Zsh:

```bash
read -rs ADO_PAT && export ADO_PAT && echo
```

Exemplo no PowerShell:

```powershell
$env:ADO_PAT = Read-Host 'PAT do Azure DevOps'
```

Nunca publique o valor em logs, README, mensagens, capturas de tela ou relatórios. O DevFlow **não** salva PATs na configuração. Ajuste os escopos às operações necessárias: leitura de Work Items, repositórios e builds para consultas; escrita de Work Items e Code para as ações mutáveis.

## 6. Inicializar um repositório de trabalho

Entre em um clone hospedado no **Azure Repos**:

```bash
cd caminho/para/seu-repo-azure-repos
dev init
dev doctor
dev tasks
```

O DevFlow reconhece remotes do tipo `https://dev.azure.com/ORG/PROJETO/_git/REPO` e SSH `git@ssh.dev.azure.com:v3/ORG/PROJETO/REPO`.

Caso não consiga detectar os dados:

```bash
dev init --org MinhaOrg --project 'Meu Projeto' --repo minha-api --base main --remote origin
```

A configuração usa um arquivo local, por caminho absoluto de repositório: Linux/macOS `~/.config/devflow/config.json` (ou `XDG_CONFIG_HOME`); Windows `%LOCALAPPDATA%\DevFlow\config.json`.

## 7. Atualizar

Use a CLI em qualquer diretório:

```bash
dev update --check
dev update
```

Para fixar uma versão específica:

```bash
dev update --tag v1.0.0 --yes
```

`--check` consulta a tag da última GitHub Release estável sem instalar nada. O comando `dev update` utiliza `pipx` e mostra uma barra de **etapas concluídas** e um spinner enquanto o pipx instala. A saída detalhada de falhas de instalação é exibida em caso de erro.

Alternativamente:

```bash
pipx install --force 'git+https://github.com/felipeflosii/devflow-cli.git@v1.0.0'
```

Como o comando pode substituir a versão instalada enquanto está em execução, o aviso final recomenda abrir uma nova sessão para confirmar a versão.

## 8. Desinstalação

```bash
pipx uninstall devflow-ado
```

A desinstalação via pipx não remove automaticamente o arquivo de configuração, que pode ser apagado separadamente por você. **Não remova** repositórios Git nem `.git/` ao desinstalar.

## 9. Solução de problemas

| Sintoma | Verificação e solução |
|---|---|
| `dev: command not found` | `pipx ensurepath` e reiniciar o terminal; verifique `pipx list`. |
| `az login` / token falhou | Entre no tenant correto ou configure PAT válido no ambiente. |
| `Nenhum repo configurado` | Execute `dev init` dentro de um clone Azure Repos. |
| `Remote não é Azure Repos` | O GitHub deste projeto distribui a ferramenta; use um clone Azure Repos para as operações. |
| `dev dashboard` não abre TUI | Certifique-se de que stdin/stdout são TTY; em CI use `--view summary --json`. |
| `git switch` bloqueado | Verifique alterações locais com `git status`; faça commit ou stash conscientemente. |
| `dev update` não encontra release | Verifique conexão com GitHub, se a tag foi publicada, e tente `--tag v1.0.0`. |
| `PR não pode ser criada` | Verifique autorização de escrita, políticas do Azure Repos e se já existe uma PR ativa. |
| `dev sprint` sem resultado | Configure iterações na equipe e suas datas no Azure Boards. |

Mais diagnósticos: [FAQ](FAQ.md) e [Manual](MANUAL.md).
