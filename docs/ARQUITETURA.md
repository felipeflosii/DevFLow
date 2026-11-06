# Arquitetura do DevFlow CLI v1.0.0

## Visão de alto nível

```text
Terminal (Zorin/Linux, macOS, Windows)
      |
      v
Comando `dev` (argparse; cli.py)
      |                 |
      |                 +-- TUI (`dashboard.py` + `tui.py` + prompt_toolkit)
      |                 +-- Modo de relatório/JSON (`dashboard.py`)
      |
      +-- Cliente AzureDevOps (`ado.py`) --HTTPS--> Azure DevOps Services REST 7.1
      |                                             Boards / Repos / Pipelines
      +-- Consultas CI/CD (`ci.py`) ---------------^
      +-- Git (`gitops.py`) ----------------------- Git local --> Azure Repos
      +-- Atualização (`updater.py`) --> GitHub Releases API + pipx + Git
      +-- Modelos/regras (`core.py`)
```

## Responsabilidades de módulos

| Módulo | Responsabilidade |
|---|---|
| `cli.py` | Argumentos, validação do fluxo, comandos e mensagens. |
| `core.py` | Formatação, datas, links, filtros, configuração e regras puras. |
| `ado.py` | Cliente HTTP Azure DevOps, autenticação, consultas e mutações de Work Items/PRs. |
| `gitops.py` | Execução de Git como subprocesso sem shell e bloqueios de ações perigosas. |
| `ci.py` | Normalização de pipelines, builds, runs e deployments. |
| `dashboard.py` | Consulta e agregação de dados, modos não interativos e JSON. |
| `tui.py` | Navegação por teclado, busca, layout, seleção e prévia dos registros. |
| `updater.py` | Consulta de releases oficiais no GitHub e instalação via pipx. |

## Segurança de execução

- A camada Git não executa comandos por interpolação de shell (`shell=True`), reduzindo riscos de injeção por argumentos de usuário.
- O comando `dev main --update` utiliza `--ff-only` para não criar merge commit inesperadamente.
- O Azure DevOps usa cabeçalhos `Authorization` obtidos da sessão Azure CLI ou PAT em variável de ambiente; **não armazena** tokens em configuração local.
- O projeto não registra logs detalhados de requisições contendo Authorization em saídas normais.
- A TUI realiza consultas em tarefas assíncronas para preservar responsividade; os dados são carregados sob demanda.
- A criação de PR é separada da aprovação/merge; a ferramenta não suprime políticas Azure Repos.
- O sistema de atualização executa `pipx` somente em releases identificadas por tag e **não** faz `curl | bash` internamente.

## Observabilidade e limitações

- Resumos de pipelines usam amostragem de builds, não buscas históricas ilimitadas.
- Deploys YAML e Classic Releases usam APIs distintas e podem ter permissões diferentes.
- `--json` permite integração com ferramentas externas, mas os dados podem conter metadados internos da organização.
- A configuração de identidade/remote é guardada por raiz do repositório.
- A UI não substitui suporte a leitores de tela; utilize os comandos textuais e JSON quando necessário.

## Dependências

- Python `>=3.10`.
- Execução: `prompt_toolkit>=3.0.36,<4` (TUI).
- Externos: Git e, para instalação/atualização, pipx; Azure CLI é opcional se houver PAT.
- Testes: `unittest` da biblioteca padrão, mocks da camada HTTP/Git e testes de lógica de interface.

## Estrutura de release

A tag `vX.Y.Z` identifica uma versão de código. Os instaladores usam explicitamente a tag `v1.0.0`; a página GitHub Releases é a fonte de consulta do `dev update`. O fluxo de CI testa o pacote em Linux, Windows e macOS. Ao publicar versões seguintes, atualize a versão do pacote e os instaladores, execute os testes e publique a tag somente depois da revisão de código.
