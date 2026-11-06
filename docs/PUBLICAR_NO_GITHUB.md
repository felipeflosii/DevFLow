# Publicar DevFlow v0.5.0 no GitHub

O ZIP deste pacote é o **código-fonte completo**, não contém tokens nem a configuração pessoal de `dev init`.

1. Descompacte o ZIP.
2. Dentro do clone atual de `felipeflosii/devflow-cli`, copie o conteúdo da pasta `devflow-cli-v0.5.0/` por cima dos arquivos existentes. Preserve o diretório `.git/` do repositório (não sobrescreva nem apague).
3. Execute os testes: `PYTHONPATH=src python3 -m unittest discover -s tests -v`.
4. Confira as diferenças: `git status` e `git diff`.
5. Publique:

```bash
git switch main
git pull --ff-only origin main
git add .
git commit -m 'release: DevFlow CLI v0.5.0'
git push origin main
git tag v0.5.0
git push origin v0.5.0
```

Caso a `main` esteja protegida, crie uma branch e abra uma Pull Request no GitHub antes de criar a tag.

Após publicar, cada desenvolvedor atualiza:

```bash
pipx install --force git+https://github.com/felipeflosii/devflow-cli.git
# alternativa: pipx upgrade devflow-ado, conforme a origem da instalação
```

O comando `dev init` **não precisa ser refeito** ao atualizar, pois a configuração v0.2.0 é compatível.

O GitHub deste projeto é apenas um distribuidor da CLI. `dev init` deve ser executado num **clone Azure Repos**.

### Release v0.5.0

Após publicar a tag `v0.5.0` no GitHub, crie uma Release usando a mesma tag.
O código deve ser mesclado à `main` antes da publicação da tag.
Teste a instalação fixando a versão:

```bash
pipx install --force git+https://github.com/felipeflosii/devflow-cli.git@v0.5.0
dev --version
```
