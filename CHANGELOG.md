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

# Changelog

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
