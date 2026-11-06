# DevFlow CLI v0.6.0 — Sprint & Work Item Management

Inclui tudo da v0.5.0 e adiciona gestão de Sprints, atribuição de Tasks e vínculos de Work Items.

## Added
- `dev sprint`, `dev sprint --all`, `dev sprint --team NOME`, `dev sprint --json`.
- `dev claim ID` e `dev claim ID --yes` para assumir Tasks sem responsável.
- `dev new "Título" --parent ID` para criar itens já relacionados à hierarquia.

## Safeguards
- Tasks atribuídas ou concluídas não podem ser assumidas com `dev claim`.
- Atribuição utiliza revisão do Work Item para detectar alterações concorrentes.
- Valida tipo e projeto do item pai antes de criar o filho.
- Mantém `dev finish` sem merge automático.

## Testes
56 testes automatizados passaram. A integração ao Azure DevOps exige validação no tenant do usuário.
