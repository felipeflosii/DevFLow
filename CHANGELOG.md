# Changelog

Este arquivo registra mudanças relevantes por versão. O DevFlow adota versionamento semântico (SemVer).

## 1.0.0 — 2026-11-06

### Adicionado
- Dashboard TUI em tela cheia com `prompt_toolkit`, menu de visões, busca, navegação por teclado e painel de detalhes.
- `dev update`, `--check`, `--tag` e `--yes` para instalação/atualização via pipx e releases GitHub.
- Barra de etapas + spinner em `dev update`, `install.sh` e `install.ps1` sem representar falsamente bytes baixados.
- Documentação de lançamento: README, manual completo, instalação, arquitetura, FAQ, SECURITY, CONTRIBUTING, COLLABORATING e CODE_OF_CONDUCT.
- Templates de issues/PRs e fluxos GitHub Actions para CI e release a partir de tags.
- Novos testes de regressão da interface e do atualizador.

### Alterado
- Dependência de runtime: `prompt_toolkit>=3.0.36,<4`.
- `dev dashboard` abre TUI em um terminal interativo e mantém o modo textual/JSON sem TTY.
- Instaladores fixados na tag `v1.0.0` para instalações reproduzíveis.

### Mantido
- Fluxos Azure Boards/Repos/Pipelines, comandos e semântica de Git da v0.8.0.
- `dev finish` não aprova ou faz merge automático e não fecha a Task.

## v0.7.0 — Monitoramento de CI/CD (2026-11-06)
- `dev pipelines`: lista pipelines e cruza os últimos builds conhecidos por ID.
- `dev builds [--pipeline ID] [--failed]`: consulta builds, estados, duração e branches.
- `dev build ID`: mostra timeline de stages, jobs e tarefas com falhas.
- `dev runs PIPELINE_ID`, `dev run PIPELINE_ID RUN_ID`: consulta execuções de pipelines.
- `dev deploys [--source all|yaml|classic] [--environment NOME]`: consulta implantações dos Azure Environments e Classic Releases.
- Novos comandos suportam `--json` resumido, com foco em dados operacionais.
- Operações CI/CD são estritamente somente leitura e toleram falhas parciais de fontes de deploy.
- Compatibilidade com os comandos das versões anteriores.

## v0.6.0 — Gerenciamento de Sprints e Work Items
- `dev sprint [--team] [--all] [--json]` lista iterações e progresso das Tasks atuais.
- `dev claim ID [--yes]` atribui Tasks livres com confirmação e validação de revisão.
- `dev new "Título" --parent ID` cria itens relacionados com vínculo pai-filho.
- Compatível com comandos e configurações anteriores.

## v0.5.0 — Pull Requests e Git
- `dev prs` lista PRs do repositório, com filtros por autor/estado e JSON.
- `dev pr ID` mostra estado, merge status, revisores e Work Items associados.
- `dev main --update` efetua fast-forward seguro da branch base após `fetch --prune`.
- Nenhuma operação altera políticas de branch ou faz merge automático de PRs.

## 0.8.0 — 2026-11-06

### Adicionado
- Novo `dev dashboard` interativo com resumo das Tasks, PRs ativas, Sprint atual e amostra de builds recentes.
- Atalhos `t`, `a`, `p`, `s`, `l`, `b`, `f`, `w ID`, `pr ID`, `start ID`, `r` e `q`.
- Filtros rápidos `t state="To Do" area="Infraestrutura"` no menu e `--view tasks --state ... --area ...` no modo direto.
- Visões `summary`, `tasks`, `prs`, `sprint`, `pipelines` e `builds` em modo de leitura com `--view` e `--json`.
- `--all` na visão geral, Tasks e PRs, com separação de dados do usuário e do projeto.
- Saída não interativa automática ao executar em scripts, sem travar esperando respostas.
- Resumo tolerante a falhas parciais das APIs (valor indisponível + aviso).

### Mantido
- Sem dependências Python de execução adicionais; funciona em Python 3.10+ nos três sistemas.
- `dev start`, `dev finish`, `dev main`, gerenciamento de PRs, Sprints e Pipelines existentes.
- Nenhum novo fluxo faz merge automático, aprova PRs ou executa deploys.


## 0.4.1 — 2026-11-06

### Alterado
- `dev finish` agora executa `git fetch <remote> --prune` e `git switch <base>` automaticamente depois da criação da Pull Request, reutilizando a lógica segura de `dev main`.
- Em caso de falha na troca da branch, mostra aviso sem perder a informação da PR recém-criada.
- Não executa pull, merge ou rebase automático nem fecha a Task.

## 0.4.0 — 2026-11-06

### Adicionado
- `dev main`: executa `git fetch origin --prune` e troca para a `main` local (ou a branch base configurada).
- Criação com tracking da branch principal local quando só existir no remoto.
- Verificação de alterações locais antes da troca de branch.

### Mantido
- `dev sync` continua buscando referências sem trocar de branch.
- Nenhuma atualização automática dos commits da branch local; `git pull --ff-only origin main` permanece explícito.
- Recursos da v0.3.0, incluindo Tasks da equipe, PBI e hierarquia.

## 0.3.0 — 2026-11-05

### Adicionado
- `dev tasks` mostra todas as Tasks abertas atribuídas à conta autenticada (incluindo sem data).
- `dev tasks --all` mostra Tasks de todo o projeto com nome do responsável abreviado e ID do PBI pai.
- `dev tasks --mine` e filtros explícitos `--today`, `--week`, `--date`.
- `dev tasks --area`, `--closed` e saída `--json` mantida.
- `dev show ID` para visualizar a hierarquia de Work Items.
- `dev pbi`, `dev features`, `dev epics` e `dev workitems`.
- Recuperação de vínculos de hierarquia via API Azure DevOps.
- Impedimento de `dev start` em Work Items diferentes de Task.

### Corrigido
- PBIs deixam de aparecer na listagem `dev tasks`.
- `--all` não restringe resultados ao usuário autenticado.
- Listagem padrão não depende de datas ou tags `devday:`.

## 0.2.0
- CLI compatível com Linux/macOS/Windows, Azure Boards, Azure Repos, branches, commits e PRs.
