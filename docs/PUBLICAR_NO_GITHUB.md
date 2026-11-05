# Publicar DevFlow e habilitar instalacao por curl

O projeto foi preparado para o repositorio publico: `felipeflosii/devflow-cli`.
Enquanto esse repositorio nao existir e nao contiver os arquivos, nenhum comando remoto de instalacao funciona.

## Publicacao inicial via GitHub CLI

Instale e autentique a CLI GitHub (`gh auth login`). Na pasta que contem `pyproject.toml`:

```bash
git init -b main
git add .
git commit -m 'feat: publicar DevFlow CLI com instalador curl'
gh repo create felipeflosii/devflow-cli --public --source=. --remote=origin --push
```

Se `git init` ou commit ja tiverem sido executados, nao repita sem necessidade. Se o repositorio remoto ja existir e estiver vazio, use `git remote add origin https://github.com/felipeflosii/devflow-cli.git` e `git push -u origin main`.

## Comando para usuarios finais (Zorin OS / Ubuntu)

Primeiro, instalar os pre-requisitos:

```bash
sudo apt update
sudo apt install -y python3 git pipx
pipx ensurepath
```

Depois, baixar e inspecionar o instalador (mais seguro):

```bash
curl -fsSLo devflow-install.sh https://raw.githubusercontent.com/felipeflosii/devflow-cli/main/install.sh
cat devflow-install.sh
bash devflow-install.sh
```

Ou, se confia no repositório e quer uma linha:

```bash
curl -fsSL https://raw.githubusercontent.com/felipeflosii/devflow-cli/main/install.sh | bash
```

O instalador nao solicita sudo nem armazena credenciais. O `pipx` instala a ferramenta Python isoladamente a partir do codigo Git. O `dev` fica disponivel apos reabrir o terminal.

Sem curl:

```bash
pipx install 'git+https://github.com/felipeflosii/devflow-cli.git'
```

Atualizar para a versao atual da main:

```bash
pipx install --force 'git+https://github.com/felipeflosii/devflow-cli.git'
```

Desinstalar:

```bash
pipx uninstall devflow-ado
```

## Verificacoes apos publicar

- O repositorio esta **publico** em https://github.com/felipeflosii/devflow-cli
- https://raw.githubusercontent.com/felipeflosii/devflow-cli/main/install.sh retorna o script sem 404
- GitHub Actions `Tests` ficou verde
- `dev --help` funciona em maquina limpa com Git, Python e pipx
- No projeto Azure Repos local, `dev init` e `dev doctor` funcionam depois de configurar autenticacao Azure

**Atencao**: executar `curl | bash` baixa e executa codigo remoto. Leia o script antes; para ambientes controlados prefira instalar um commit/tag especifico usando `pipx`.
