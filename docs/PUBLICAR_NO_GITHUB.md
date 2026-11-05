# Publicação pública do DevFlow CLI 0.2.0

O projeto foi preparado para o endereço `https://github.com/felipeflosii/devflow-cli`, que **precisa existir e estar público** antes de qualquer instalação remota funcionar.

## Primeiro upload

Na pasta extraída, contendo `pyproject.toml`:

```bash
git init -b main
git add .
git commit -m 'feat: adicionar instaladores Windows, macOS e Linux'
gh auth login
gh repo create felipeflosii/devflow-cli --public --source=. --remote=origin --push
```

Se já existe um repositório Git local, não repita `git init`. Se o GitHub já tiver um repositório vazio `devflow-cli`, use `git remote add origin https://github.com/felipeflosii/devflow-cli.git` e `git push -u origin main`, depois de verificar a branch.

## Instalação dos desenvolvedores

**macOS/Linux** (Terminal/zsh/Bash):

```bash
curl -fsSL https://raw.githubusercontent.com/felipeflosii/devflow-cli/main/install.sh | bash
```

**Windows** (PowerShell):

```powershell
irm https://raw.githubusercontent.com/felipeflosii/devflow-cli/main/install.ps1 | iex
```

Antes desses comandos, é necessário instalar Python 3.11+, Git e pipx. Veja instruções específicas no README. Para evitar executar código remoto sem revisão, faça download e leia o script antes.

## Verificações depois de publicar

- Repositório público acessível pelo navegador.
- `install.sh` e `install.ps1` acessíveis por `raw.githubusercontent.com` sem erro 404.
- GitHub Actions `Cross-platform tests` verde para Ubuntu, macOS e Windows.
- Instalação em uma máquina de cada sistema, `dev --version` e `dev --help` funcionando.
- Após `az login`, validar `dev doctor` e o ciclo `dev tasks` / `dev start` / `dev finish` com uma tarefa de teste no **Azure Repos**.

## Atualizações

Após cada commit publicado, quem tiver DevFlow pode atualizar via:

```bash
pipx install --force git+https://github.com/felipeflosii/devflow-cli.git
```

No Windows também é válido `py -m pipx install --force git+https://github.com/felipeflosii/devflow-cli.git`.

## Recomendações de distribuição

- Crie tags versionadas (`v0.2.0` etc.) e releases para que equipes possam fixar uma versão confiável.
- O instalador padrão acompanha a `main` e, portanto, o conteúdo remoto pode mudar. Leia os scripts ou instale a partir de um commit/tag específico.
- Não inclua tokens ou credenciais no repositório público.
