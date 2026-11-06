# Perguntas frequentes — DevFlow CLI

## Posso usar com GitHub Repos?

O repositório GitHub distribui o DevFlow; os comandos `dev init`, `dev start`, `dev finish` e consultas Azure DevOps foram projetados para **Azure Repos**. Eles não abrem Pull Requests no GitHub.

## O `dev tasks` mostra tarefas sem data?

Sim. Desde a v0.3.0, mostra suas Tasks abertas, com ou sem `devday`. Use `--today`, `--week` ou `--date` para filtrar pela tag.

## Qual a diferença entre `dev tasks` e `dev tasks --all`?

Sem `--all`, a ferramenta consulta Tasks atribuídas a você. Com `--all`, consulta todas as Tasks abertas do projeto e mostra também responsável e PBI pai.

## O `dev tasks` lista PBIs?

Não. Consulte `dev pbi`, `dev features`, `dev epics` e `dev workitems` para outros tipos.

## Como colocar uma Task dentro de um PBI pelo terminal?

```bash
dev new 'Criar endpoints' --parent 5
```

Para itens existentes, ajuste o relacionamento no Azure Boards. Veja a seção de hierarquia no manual.

## Como instalar e atualizar com animação?

Use os scripts oficiais `install.sh`/`install.ps1` ou `dev update`. O progresso é por **etapas**, não por porcentagem de bytes baixados.

## A TUI funciona no Zorin OS com kitty e zsh?

Sim, `prompt_toolkit` funciona em terminais ANSI modernos. Para usar a interface precisa de uma sessão TTY. Em terminais de CI/IDE que não suportam modo tela cheia, use `dev dashboard --view summary` ou `--json`.

## Posso automatizar consultas sem abrir a interface visual?

```bash
dev dashboard --view tasks --all --json
dev builds --failed --json
```

## `dev finish` faz o merge da PR?

Não. O comando cria a PR e volta para a branch principal, mas a revisão e o merge continuam sob controle das políticas Azure Repos.

## `dev main` já traz os commits mais recentes?

`dev main` apenas busca referências e troca de branch. Utilize `dev main --update` para avanço fast-forward, quando possível.

## De onde vem a data planejada da CLI?

Da tag `devday:AAAA-MM-DD` usada por `dev plan`, e não de Due Date ou Iteration Path nativos do Azure Boards.

## Por que o DevFlow precisa de `az login`?

É uma das formas de conseguir um token para a API do Azure DevOps. A alternativa é configurar um PAT com escopo restrito em `ADO_PAT`.

## Onde a configuração fica salva?

Linux/macOS: `~/.config/devflow/config.json` ou `XDG_CONFIG_HOME`. Windows: `%LOCALAPPDATA%\DevFlow\config.json`. O arquivo não contém PAT.

## Como excluir a instalação?

```bash
pipx uninstall devflow-ado
```

A pasta de configuração permanece até ser removida manualmente.

## Falhas de pipeline significam que a aplicação está fora do ar?

Não necessariamente. CI/CD, deploy e disponibilidade operacional são dimensões distintas. O DevFlow consulta resultados das APIs, não monitora a saúde externa de serviços em produção.

## O que fazer quando aparecer erro 403 ou 401?

Confirme a organização, o tenant, as permissões de leitura/escrita exigidas e a autenticação. Não envie PATs ou cabeçalhos Authorization em relatos públicos.

## Como apoiar o projeto ou relatar bugs?

Use as Issues e Pull Requests no repositório GitHub; consulte [CONTRIBUTING.md](../CONTRIBUTING.md). Para vulnerabilidades de segurança, leia [SECURITY.md](../SECURITY.md).
