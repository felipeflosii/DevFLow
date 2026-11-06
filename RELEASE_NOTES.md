# DevFlow CLI v0.5.0 — Git & Pull Request Management

A versão v0.5.0 permite consultar Pull Requests e atualizar a branch principal de forma segura, preservando todos os comandos existentes.

## Added
- `dev prs` (com `--mine`, `--all`, `--status`, `--limit` e `--json`).
- `dev pr ID` para detalhar revisão, estado, merge status e Work Items.
- `dev main --update` realiza somente fast-forward para a referência remota.

## Safeguards
- Sem merge automático de PRs, reset, rebase ou force push.
- Commits divergentes impedem o fast-forward.

## Testes
42 testes automatizados de unidade e fluxo local passaram. A integração ao Azure DevOps exige validação no tenant do usuário.
