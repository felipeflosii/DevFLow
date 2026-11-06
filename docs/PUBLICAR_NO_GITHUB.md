# Publicação oficial — DevFlow CLI v1.0.0

Guia para publicar o lançamento oficial em `felipeflosii/devflow-cli`, com código, documentação, tags e distribuição Python. **Nenhuma etapa abaixo é executada automaticamente por este documento.**

## Checklist pré-publicação

- [ ] Leia README, manual, changelog, segurança e contribuição.
- [ ] Revise dependências Python e código do atualizador, sem PATs no Git.
- [ ] Execute todos os testes locais (Windows, Linux ou macOS; CI executará a matriz completa).
- [ ] Verifique `dev --version` retornando `1.0.0`.
- [ ] Teste `dev update --check` **após** publicar a tag/release.
- [ ] Teste TUI em um terminal real; JSON em ambiente sem TTY.
- [ ] Assegure que o workflow de CI passou na `main`.
- [ ] Revise se não há arquivos particulares, configurações pessoais ou segredos no repositório.
- [ ] Confirme a branch base e políticas do repositório GitHub.

## 1. Preparar arquivos

Extraia o ZIP fornecido e copie **o conteúdo** da pasta `devflow-cli-v1.0.0/` para o clone local GitHub do projeto. Preserve a pasta `.git/` existente; não a substitua nem apague. Para ver quais arquivos serão modificados:

```bash
git status
git diff --check
git diff --stat
```

Os scripts e o Python package são versionados no Git. A pasta `dist/` e os arquivos `.whl` construídos localmente devem permanecer ignorados no repositório, pois serão anexados à GitHub Release.

## 2. Testar localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
python -m compileall -q src
python -m pip check
bash -n install.sh
python -m devflow --version
```

PowerShell: `.venv\Scripts\Activate.ps1`; os comandos Python são equivalentes.

## 3. Publicar com Pull Request (recomendado)

Para repositórios com `main` protegida:

```bash
git switch main
git pull --ff-only origin main
git switch -c release/v1.0.0
git add .
git commit -m "release: prepare DevFlow CLI v1.0.0"
git push -u origin release/v1.0.0
```

Abra uma PR no GitHub, aguarde CI e revisão. Depois de integrar a PR, atualize a `main` local e **confira o commit** antes de criar a tag.

Para repositório sem proteção, também é possível fazer commit diretamente na `main`, respeitando as políticas existentes.

## 4. Criar tag da release

Após a atualização da `main`:

```bash
git switch main
git pull --ff-only origin main
git status --short
git tag -a v1.0.0 -m "DevFlow CLI v1.0.0 — Official Release"
git push origin v1.0.0
```

**Não recrie ou mova uma tag pública existente.** Em vez disso, lance uma nova versão. A automação `.github/workflows/release.yml` valida versão, roda testes, constrói Wheel + sdist e cria/atualiza os arquivos anexados à GitHub Release. Não publica no PyPI.

## 5. Conferir GitHub Release

Acesse `https://github.com/felipeflosii/devflow-cli/releases`. A Release deve ter a tag `v1.0.0`, título `DevFlow CLI v1.0.0` e notas do arquivo `RELEASE_NOTES.md`. Valide os anexos `.whl` e `.tar.gz` e marque a release como mais recente. Caso prefira editar a descrição manualmente, mantenha as notas de compatibilidade e de testes.

A Release poderá não ser criada automaticamente se a organização bloquear permissões de GitHub Actions; revise as permissões do workflow `contents: write`, o log da action e publique manualmente se necessário.

## 6. Teste pós-publicação

Num ambiente limpo, instale a tag:

```bash
pipx install --force 'git+https://github.com/felipeflosii/devflow-cli.git@v1.0.0'
dev --version
dev update --check
```

Valide `dev init`, `dev doctor`, `dev tasks` e `dev dashboard` dentro de um clone Azure Repos de teste. A suíte automatizada **não substitui** esta homologação com uma organização real.

## 7. Manutenção após lançamento

- Mantenha issues de segurança privadas.
- Receba PRs com testes e documentação atualizada.
- Corrija bugs em releases `1.0.x` e reserve versões posteriores para novas funcionalidades.
- Versione instaladores com a nova tag; nunca deixe o instalador principal apontando para um commit móvel sem transparência.
- Atualize README, changelog, manual e `RELEASE_NOTES.md` a cada publicação relevante.
