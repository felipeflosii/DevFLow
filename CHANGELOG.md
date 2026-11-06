# Changelog

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
