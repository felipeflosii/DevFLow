# DevFlow CLI

**Azure Boards, Azure Repos e Azure Pipelines em um único terminal.**

[![CI](https://github.com/felipeflosii/devflow-cli/actions/workflows/tests.yml/badge.svg)](https://github.com/felipeflosii/devflow-cli/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)](https://www.python.org/)
[![Version](https://img.shields.io/badge/release-v1.0.0-008080)](https://github.com/felipeflosii/devflow-cli/releases)
[![MIT License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

O **DevFlow CLI v1.0.0** reúne consulta e organização de tarefas, automação de branches/commits/Pull Requests, Sprints, monitoramento de CI/CD e um dashboard interativo em tela cheia. Destina-se a equipes que utilizam **Azure DevOps Services**, com repositórios de código no **Azure Repos**.

> **Nota:** o GitHub hospeda e distribui o código-fonte desta ferramenta; o DevFlow opera sobre repositórios *Azure Repos*, não automatiza PRs de repositórios hospedados no GitHub. Projeto comunitário não oficial, sem afiliação com a Microsoft.

## Destaques da v1.0.0

- **Dashboard TUI** com menu, pesquisa, navegação por setas, painel de detalhes, F5 e atalhos, utilizando [`prompt_toolkit`](https://python-prompt-toolkit.readthedocs.io/).
- **Atualizador `dev update`** com spinner e barra de **etapas concluídas**: nunca apresenta porcentagem fictícia de download.
- **Instalação cross-platform** com `pipx`: scripts em Bash para Linux/macOS e PowerShell para Windows.
- **Compatibilidade com automação**: `dev dashboard --view ... --json` mantém resultados estruturados, sem interações.
- **Segurança operacional**: evita comandos Git destrutivos e não armazena credenciais do Azure DevOps nos arquivos de configuração.

## Instalação rápida

Pré-requisitos: **Python 3.10+**, **Git**, **pipx** e uma conta com acesso ao Azure DevOps. Para autenticar, use `az login` (Azure CLI) ou um PAT fornecido pela variável de ambiente `ADO_PAT`.

Instalação recomendada para qualquer sistema, após configurar o `pipx`:

```bash
pipx install 'git+https://github.com/felipeflosii/devflow-cli.git@v1.0.0'
dev --version
```

No **Zorin OS / Ubuntu**, caso ainda não tenha `pipx`:

```bash
sudo apt update
sudo apt install -y git python3 pipx
pipx ensurepath
```

Para usar os instaladores com barra de progresso, **baixe e revise o arquivo antes de executá-lo**:

```bash
curl -fsSLo devflow-install.sh https://raw.githubusercontent.com/felipeflosii/devflow-cli/v1.0.0/install.sh
less devflow-install.sh
bash devflow-install.sh
```

No Windows, use `install.ps1` no PowerShell. Veja [instalação detalhada](docs/INSTALACAO.md), incluindo PATH, permissões, autenticação e soluções de problemas.

> Os links de instalação na tag `v1.0.0` somente funcionarão **após** a tag ser publicada no GitHub.

## Configuração inicial

Dentro de um clone **Azure Repos** (não o clone do repositório GitHub do DevFlow):

```bash
az login
dev init       # Detecta organização, projeto e repositório a partir de origin
dev doctor     # Diagnóstico de Git, Azure DevOps e autenticação
dev tasks      # Tasks abertas atribuídas a você (incluindo sem data)
```

Alternativamente:

```bash
dev init --org MinhaOrg --project 'Meu Projeto' --repo minha-api --base main --remote origin
```

A configuração é salva por repositório, sem tokens. Não é necessário repetir `dev init` ao atualizar a ferramenta.

## Fluxo diário

```bash
dev dashboard          # TUI em tela cheia com pesquisa e detalhes
dev tasks              # Minhas Tasks pendentes
dev tasks --all        # Tasks abertas de toda a equipe + responsável + PBI
dev show 8             # Work Item e cadeia Epic > Feature > PBI > Task
dev start 8            # Branch feature/8-... vinculada à Task
dev save 'Implementa validações'  # Commit com AB#8 e push
dev finish             # Cria PR e retorna à branch base; SEM merge
dev main --update      # Atualiza branch base apenas se fast-forward
```

Comandos disponíveis para consultar o projeto:

| Área | Comandos |
|---|---|
| Work Items | `dev tasks`, `dev pbi`, `dev features`, `dev epics`, `dev workitems`, `dev show ID` |
| Gestão | `dev new`, `dev assign`, `dev claim`, `dev plan`, `dev sprint` |
| Git e PR | `dev start`, `dev save`, `dev finish`, `dev main`, `dev sync`, `dev prs`, `dev pr ID` |
| CI/CD | `dev pipelines`, `dev builds`, `dev build ID`, `dev runs ID`, `dev run ID ID`, `dev deploys` |
| Produtividade | `dev dashboard`, `dev doctor`, `dev status`, `dev current`, `dev update` |

Consulte todos os argumentos com `dev <comando> --help`. O [manual completo](docs/MANUAL.md) contém exemplos, limitações e fluxos para cada comando.

## Dashboard interativo

`dev dashboard` inicia a nova interface TUI quando há terminal interativo. Use **↑ / ↓** para selecionar, **Tab** e **Shift+Tab** para mudar de visão, **/** para pesquisar, **Enter** para detalhes, **F5** para atualizar, **S** para iniciar uma Task com confirmação e **Q** para sair. Digite `?` para abrir a ajuda. O painel oferece oito seções: resumo, minhas Tasks, equipe, PRs, Sprint, pipelines, builds e falhas de CI.

Para execução em CI, pipes, containers sem TTY ou scripts:

```bash
dev dashboard --view summary --json
dev dashboard --view tasks --all --state 'To Do'
dev dashboard --view builds --failed --json
```

## Instalar / atualizar com progresso

```bash
dev update --check       # Apenas consulta última release estável do GitHub
dev update               # Pede confirmação antes de instalar
dev update --tag v1.0.0 --yes  # Instala uma tag especificada, de modo não interativo
```

Durante a instalação, o terminal mostra o avanço das **3 etapas** (release identificada, instalação do pacote, ajuste do PATH), mais uma animação de atividade enquanto o `pipx` trabalha. **Não é uma medição em bytes baixados.** A atualização pode ser feita em qualquer diretório, sem `dev init`.

## Segurança e limites

- Nunca faça commit de `ADO_PAT` ou de qualquer segredo. Para acesso com Azure CLI, use `az login`; `pipx` não autentica o Git no Azure Repos.
- `dev finish` **abre uma PR, mas não faz merge, não aprova revisões e não conclui a Task automaticamente**.
- `dev main --update` faz **somente fast-forward**, se possível, e verifica alterações locais.
- `dev deploys`, `dev builds` e o dashboard apenas **consultam** informações de CI/CD.
- Ações que criam ou alteram Work Items precisam das permissões corretas na organização.
- O teste de integração com um Azure DevOps real depende de credenciais e permissões do usuário; os testes automatizados utilizam mocks.

Leia [SECURITY.md](SECURITY.md) para divulgação responsável de vulnerabilidades e permissões mínimas recomendadas.

## Documentação do projeto

- [Manual completo dos comandos](docs/MANUAL.md)
- [Instalação e atualização](docs/INSTALACAO.md)
- [Arquitetura e decisões técnicas](docs/ARQUITETURA.md)
- [Perguntas frequentes e diagnóstico](docs/FAQ.md)
- [Publicação oficial no GitHub](docs/PUBLICAR_NO_GITHUB.md)
- [Política de segurança](SECURITY.md)
- [Como contribuir](CONTRIBUTING.md)
- [Código de conduta](CODE_OF_CONDUCT.md)
- [Suporte](SUPPORT.md)
- [Histórico de mudanças](CHANGELOG.md)
- [Notas da v1.0.0](RELEASE_NOTES.md)

## Desenvolvimento

```bash
git clone https://github.com/felipeflosii/devflow-cli.git
cd devflow-cli
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

No PowerShell, ative o virtualenv com `.venv\Scripts\Activate.ps1`.

**Licença MIT.** Desenvolvido de forma independente; leia [LICENSE](LICENSE).
