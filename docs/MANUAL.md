# Manual do usuário — DevFlow CLI v1.0.0

Guia completo de utilização do **DevFlow CLI** para Azure DevOps Services, Azure Boards, Azure Repos e Azure Pipelines. A ferramenta é escrita em Python e fornece o comando `dev` no terminal.

Este manual cobre o ambiente de uso, configurações, todos os comandos principais, exemplos de trabalho cotidiano, permissões, critérios de segurança e formas de diagnóstico.

## Sumário

1. [Visão geral e conceitos](#1-visão-geral-e-conceitos)
2. [Primeiros passos](#2-primeiros-passos)
3. [Fluxo de trabalho diário](#3-fluxo-de-trabalho-diário)
4. [Tasks e Work Items](#4-tasks-e-work-items)
5. [Criar, assumir e planejar tarefas](#5-criar-assumir-e-planejar-tarefas)
6. [Git, branches e PRs](#6-git-branches-e-prs)
7. [Sprints e planejamento](#7-sprints-e-planejamento)
8. [Pipelines, builds e deploys](#8-pipelines-builds-e-deploys)
9. [Dashboard TUI e modo não interativo](#9-dashboard-tui-e-modo-não-interativo)
10. [Instalação, atualização e configuração](#10-instalação-atualização-e-configuração)
11. [Erros comuns e recuperação](#11-erros-comuns-e-recuperação)
12. [Segurança, limitações e boas práticas](#12-segurança-limitações-e-boas-práticas)
13. [Referência rápida](#13-referência-rápida)

## 1. Visão geral e conceitos

O DevFlow é um cliente de terminal que automatiza parte do fluxo de trabalho de desenvolvedores. **Não substitui** o Azure DevOps e não implementa uma plataforma de hospedagem própria; executa consultas e ações por meio das APIs REST do serviço e comandos Git locais.

Entenda os objetos mais importantes:

- **Epic**: objetivo amplo, frequentemente organizado por área do produto.
- **Feature**: capacidade entregue dentro de uma Epic.
- **Product Backlog Item (PBI)**: entrega ou requisito detalhado dentro de uma Feature (em projetos Agile, o equivalente geralmente é *User Story*).
- **Task**: atividade técnica associada a um PBI.
- **Area Path**: área funcional, produto ou equipe responsável.
- **Iteration Path**: Sprint ou período de planejamento.
- **Pull Request (PR)**: proposta de alteração que exige revisão conforme as políticas do repositório.
- **Pipeline**: definição de fluxo automatizado; **Build**: execução associada a integração contínua; **Deployment**: execução de implantação.

Um exemplo de hierarquia no Azure Boards:

```text
Epic #3  Infraestrutura da GS2
  Feature #4  Provisionamento Azure
    PBI #5  Disponibilizar APIs em nuvem
      Task #6  Criar script para API Python
      Task #7  Criar script para API .NET
      Task #8  Validar App Services
```

O DevFlow é mais eficiente quando a equipe mantém essa hierarquia atualizada e registra estados, responsáveis e critérios de aceite no Azure Boards.

## 2. Primeiros passos

### 2.1 Instale a CLI

Consulte [INSTALACAO.md](INSTALACAO.md) para Linux, macOS e Windows, incluindo o instalador com barra de progresso. Exemplo para ambiente já preparado:

```bash
pipx install 'git+https://github.com/felipeflosii/devflow-cli.git@v1.0.0'
dev --version
```

### 2.2 Autentique-se no Azure DevOps

Se usar Azure CLI:

```bash
az login
```

Se usar PAT, armazene-o somente em variável de ambiente. Bash/zsh:

```bash
read -rs ADO_PAT && export ADO_PAT && echo
```

No PowerShell:

```powershell
$env:ADO_PAT = Read-Host 'PAT Azure DevOps'
```

Evite passar PAT diretamente em argumentos de comandos (podem ser registrados no histórico e em listas de processos). Para operações de `git push`, configure acesso ao Git de maneira independente.

### 2.3 Configure a pasta do repositório

```bash
cd ~/Documentos/FIAP/GS2/Java
# Deve ser um clone de um REPOSITÓRIO AZURE REPOS, não GitHub.
git remote -v
dev init
dev config
dev doctor
```

`dev init` reconhece os remotes HTTPS e SSH do Azure Repos. Sem detecção automática:

```bash
dev init --org VetSync --project 'GS2 - Azure DevOps' --repo zeroviagem-api-java --base main --remote origin
```

A configuração é local e **por repositório**, de modo que cada clone pode apontar para um projeto Azure DevOps diferente. A instalação do DevFlow é global ao usuário (`pipx`), mas a configuração é específica do diretório do clone.

### 2.4 Primeira consulta

```bash
dev tasks
dev dashboard
```

Se não aparecerem Tasks, verifique se elas estão atribuídas à sua conta, se ainda estão abertas e se o projeto correto está configurado. `dev tasks --all` mostra as Tasks abertas do projeto, inclusive aquelas atribuídas a outras pessoas e ainda sem responsável.

## 3. Fluxo de trabalho diário

### Cenário: receber, implementar e encaminhar uma Task para revisão

1. Consultar trabalho pendente:

   ```bash
   dev tasks
   dev show 8
   ```

2. Começar Task, criando branch a partir da referência remota da branch base:

   ```bash
   dev start 8
   ```

   Isso verifica atribuição, estado do Work Item, alterações locais e configuração do repositório antes de criar/retomar a branch. Nome típico: `feature/8-validar-app-services`.

3. Alterar código, testar localmente e salvar:

   ```bash
   dev save 'test: valida App Services'
   ```

   O commit inclui o marcador `AB#8` para associação com Azure Boards. Por padrão, o DevFlow pede confirmação antes de adicionar todos os arquivos modificados.

4. Encaminhar para revisão:

   ```bash
   dev finish
   ```

   Se houver alterações ainda não commitadas, pode ser necessário informar `-m 'mensagem'`. Depois da criação da PR, o DevFlow busca atualizações remotas e retorna à branch principal configurada. **Não faz merge da PR, não aprova revisões e não marca a Task como Done.**

5. Consultar a revisão e as pipelines:

   ```bash
   dev prs
dev pr 12
   dev pipelines
   dev builds --failed
   ```

6. Atualizar a branch base, quando conveniente:

   ```bash
   dev main --update
   ```

   Esse comando utiliza **fast-forward somente**. Se a branch local divergiu da referência remota, ele interrompe a atualização para que você decida como resolver.

## 4. Tasks e Work Items

### 4.1 `dev tasks`

Lista **suas Tasks abertas**, inclusive as que não possuem `devday` ou data planejada. **PBIs não aparecem** nessa lista.

```bash
dev tasks
dev tasks --today              # Hoje e atrasadas
dev tasks --week               # Até o fim desta semana e atrasadas
dev tasks --date 2026-11-09
dev tasks --mine               # Explicitamente minhas Tasks
dev tasks --area 'Infraestrutura'
dev tasks --closed             # Inclui concluídas
```

`--today`, `--week`, `--date`, `--mine` e `--all` são filtros alternativos; não os combine. Os filtros de datas usam a tag de planejamento `devday:AAAA-MM-DD`, **não** o campo nativo de Due Date do Azure Boards nem o Iteration Path. A tag serve como convenção da CLI e não altera o cronograma do Azure DevOps.

### 4.2 `dev tasks --all`

Lista **Tasks abertas de todo o projeto**, de outros desenvolvedores ou sem responsável. A tabela inclui responsável abreviado, estado, PBI pai, data planejada e título:

```bash
dev tasks --all
dev tasks --all --area 'Infraestrutura e DevOps'
dev tasks --all --json
```

A coluna `PBI` depende de links de relacionamento `Hierarchy-Reverse` existentes e do pai ser efetivamente do tipo PBI/User Story. Quando a Task está solta, o campo aparece vazio. Em `--json`, a saída é mais apropriada para integrações, mas pode conter informações completas devolvidas pela API — trate-a como dado interno.

### 4.3 `dev pbi`, `dev features`, `dev epics` e `dev workitems`

Consulta Work Items de outro nível sem misturá-los à lista de Tasks.

```bash
dev pbi                 # PBIs atribuídos a você (dependendo do campo Assigned To)
dev pbi --all           # Todos os PBIs abertos do projeto
dev features --all
dev epics --all
dev workitems --all
dev workitems --all --area 'Mobile'
```

Se o processo Azure Boards for Agile, o comando PBI contempla *User Story*. As opções `--closed` e `--json` também estão disponíveis.

### 4.4 `dev show ID`

Mostra os campos do Work Item e os relacionamentos até encontrar o topo da hierarquia, quando as relações existem:

```bash
dev show 8
```

Em um backlog corretamente vinculado, a Task #8 terá PBI pai, Feature avó e Epic ancestral. O comando consulta a API Azure DevOps; não inventa parentes se o Work Item não tiver links.

## 5. Criar, assumir e planejar tarefas

### 5.1 `dev new`

Cria um Work Item no Azure Boards. Por padrão é uma `Task`:

```bash
dev new 'Implementar JWT'
dev new 'Validar integração da IA' --assign pessoa@exemplo.com
dev new 'Criar script de deploy' --parent 5
dev new 'Criar Feature X' --type Feature --parent 3
```

O parâmetro `--parent` cria vínculo de hierarquia com um Work Item pai existente. O tipo de pai permitido depende da configuração/processo do Azure DevOps; a CLI não contorna regras do servidor.

### 5.2 `dev claim ID`

Atribui a você uma **Task aberta sem responsável**. Confirma antes de alterar o Boards:

```bash
dev claim 14
dev claim 14 --yes
```

O Azure DevOps pode negar a alteração por permissões ou se a Task tiver sido atribuída a outra pessoa entre a consulta e a atualização. Recarregue o Work Item antes de repetir.

### 5.3 `dev assign ID EMAIL`

Atribui uma Task existente a outra pessoa. Requer permissões para editar o item:

```bash
dev assign 14 pessoa@exemplo.com
```

### 5.4 `dev plan ID --date ...`

Adiciona ou altera uma tag de planejamento da CLI (`devday:AAAA-MM-DD`) sem eliminar as outras tags:

```bash
dev plan 6 --date 2026-11-09
dev plan 6 7 8 --date 2026-11-09
```

**Não** atualiza Due Date nem cria Iteration Path. Para organizar uma Sprint, configure a iteração no Azure Boards; para usar a agenda simplificada da CLI, use `dev plan`.

## 6. Git, branches e PRs

### 6.1 `dev sync`

```bash
dev sync
```

Executa `git fetch <remote> --prune`. Atualiza referências remotas, removendo referências de branches remotas excluídas; **não muda a branch local** nem modifica arquivos do working tree.

### 6.2 `dev main` e `dev main --update`

```bash
dev main
dev main --update
```

`dev main` verifica se há mudanças locais, faz fetch/prune e troca para a branch principal configurada (`main` por padrão). Se necessário, cria a branch local a partir do remoto. `--update` avança a branch local por fast-forward, sem merge commit.

**Importante:** o fato de a branch estar na `main` não significa que ela tenha recebido os últimos commits, a menos que `--update` seja utilizado ou outra atualização seja feita manualmente.

### 6.3 `dev start ID`

```bash
dev start 8
```

Somente aceita Tasks atribuídas à conta autenticada e ainda abertas. Bloqueia troca de branch com alterações locais e não cria branch para PBIs. Depois do fetch, cria ou retoma uma branch `feature/<ID>-<slug>` (ou `fix/` para tipos suportados). Não faz checkout forçado ou reset da `main`.

### 6.4 `dev current` / `dev status`

```bash
dev current
dev status
```

Mostram a branch atual e identificam o Work Item a partir do nome da branch. `status` também apresenta alterações locais e Pull Request ativa associada à branch quando houver.

### 6.5 `dev save` e `dev finish`

```bash
dev save 'feat: adiciona paginação'
dev finish
dev finish -m 'feat: valida regras de negócio'
```

`save` cria commit com `AB#ID` e executa push. Se houver arquivos modificados, pede confirmação antes de `git add -A`, a menos que use `--yes`. **Faça revisão do `git diff` antes de confirmar**: não confie apenas no bloqueio parcial de nomes de arquivos potencialmente secretos.

`finish` cria PR com a referência `AB#ID`, tenta criar o vínculo no Boards e retorna à branch base somente após a PR existir. A PR permanece aberta. Se a criação da PR falhar, a branch de trabalho é preservada. Se o retorno à branch base falhar, a mensagem informa que a PR já foi criada para não duplicá-la.

### 6.6 `dev prs` e `dev pr ID`

```bash
dev prs                    # PRs ativas
dev prs --mine             # Minhas PRs
dev prs --status completed
dev prs --all              # Inclui PRs concluídas e abandonadas
dev prs --json
dev pr 12                  # Detalhes, revisores e Work Items relacionados
```

Os dados refletem as permissões da sua conta. A CLI não aprova automaticamente Pull Requests nem ignora as regras da branch protegida.

## 7. Sprints e planejamento

```bash
dev sprint
dev sprint --all
dev sprint --team 'MinhaEquipe'
dev sprint --json
```

Consulta as Iterations da equipe e identifica a Sprint atual com base nos dados retornados pelo Azure DevOps. Quando não há Sprint atual, configure **Project settings → Teams → Iterations** e as datas correspondentes. Não confunda Iteration Path com Due Date individual: a primeira é o período de trabalho; a segunda, quando existir no processo, é uma propriedade específica do Work Item.

O progresso apresentado resume Tasks retornadas pela API; não significa que todas as entregas da Sprint foram aceitas, porque os critérios de aceite do PBI precisam ser verificados separadamente.

## 8. Pipelines, builds e deploys

Estas operações são **somente leitura**. A CLI não executa ou cancela pipelines nem aprova deploys.

### 8.1 Listar pipelines

```bash
dev pipelines
dev pipelines --limit 20
dev pipelines --json
```

A visão pode combinar a lista de definições de pipelines com uma amostra de builds recentes, exibindo o último resultado encontrado. O resultado é relativo à amostra consultada, não garante uma varredura integral de todo o histórico.

### 8.2 Consultar builds

```bash
dev builds
dev builds --failed
dev builds --pipeline 9
dev build 81
dev build 81 --json
```

`dev build` examina informações de execução e, quando a timeline está disponível, identifica stages/jobs/steps relevantes. Pode haver limitações conforme permissões, tipo de pipeline ou execução muito antiga.

### 8.3 Consultar pipeline runs

```bash
dev runs 9
dev runs 9 --limit 25
dev run 9 81
dev run 9 81 --json
```

Em `dev run`, o primeiro ID identifica a pipeline; o segundo, a execução. A timeline vinculada pode não estar acessível em todos os tipos de execução; a CLI relata a limitação quando aplicável.

### 8.4 Consultar deploys

```bash
dev deploys
dev deploys --source yaml
dev deploys --source classic
dev deploys --environment prod
dev deploys --json
```

Os deploys podem vir de Azure Pipelines YAML Environments e/ou Classic Releases. O serviço de Classic Releases usa um endpoint diferente e requer permissões próprias; ambientes sem acesso retornam avisos. A ferramenta limita consultas para evitar paginação ilimitada ou requisições excessivas.

## 9. Dashboard TUI e modo não interativo

### 9.1 Iniciar interface em tela cheia

```bash
dev dashboard
```

A TUI utiliza `prompt_toolkit` e apresenta navegação por abas, lista de itens selecionáveis, campo de busca e painel lateral de detalhes.

| Tecla | Comportamento |
|---|---|
| `↑` / `↓` | Mover seleção na lista |
| `Tab` / `Shift+Tab` | Avançar ou retornar entre seções |
| `1` a `8` | Acessar seção diretamente (quando a busca não está focada) |
| `/` | Colocar foco na busca |
| Digitar | Filtrar registros em tempo real no campo de busca |
| `Enter` | Consultar detalhes adicionais, quando disponíveis |
| `Esc` | Limpar pesquisa e retornar à lista |
| `F5` | Recarregar a visão atual |
| `S` | Solicitar início da Task selecionada; confirmação fora da TUI |
| `?` | Exibir/ocultar ajuda |
| `Q` / `Ctrl+C` | Sair |

As seções são: **Resumo**, **Minhas Tasks**, **Equipe**, **Pull Requests**, **Sprint**, **Pipelines**, **Builds** e **Falhas de CI**. A busca ocorre nos campos exibidos e em alguns metadados da entrada (nome, estado, responsável).

Se a consulta falhar, a interface exibe a mensagem de erro e permite nova tentativa com F5. Seleção e navegação são somente leitura; a única operação mutável disponível na TUI é começar uma Task, que exige confirmação depois que a interface é encerrada e continua aplicando as verificações do `dev start`.

**Observação:** o dashboard precisa de terminal real e pode se comportar de forma diferente em consoles de CI, IDEs e terminais reduzidos. Para automações, utilize as opções abaixo.

### 9.2 Consultas diretas e JSON

```bash
dev dashboard --view summary
dev dashboard --view tasks --all
dev dashboard --view tasks --state 'In Progress'
dev dashboard --view tasks --area 'Infraestrutura'
dev dashboard --view prs
dev dashboard --view sprint --team 'MinhaEquipe'
dev dashboard --view pipelines
dev dashboard --view builds --failed
```

Com `--json`:

```bash
dev dashboard --view summary --json
dev dashboard --view tasks --all --json
```

`--json` exige uma `--view`, pois a interface interativa não pode ser serializada de forma confiável. Se stdout ou stdin não for um TTY, `dev dashboard` sem `--view` retorna um resumo textual, sem bloquear aguardando teclas.

### 9.3 Dados de exemplo para automação

```bash
dev dashboard --view summary --json > relatorio.json
```

Os dados retornados podem refletir nomes, IDs, estados e metadados internos de projetos; não compartilhe JSON completo publicamente sem revisão.

## 10. Instalação, atualização e configuração

### `dev update`

```bash
dev update --check
dev update
dev update --tag v1.0.0 --yes
```

`dev update` é um comando global: pode ser executado fora de repositórios Git. Para a tag padrão, consulta a GitHub Release mais recente não marcada como pre-release. O instalador executa `pipx install --force` com a tag escolhida e faz `pipx ensurepath`. A barra indica **etapas concluídas**, e o spinner indica **atividade**, sem prometer um percentual de bytes baixados. Requer `pipx` disponível e acesso ao GitHub.

### `dev config`, `dev doctor`, `dev --version`

```bash
dev --version
dev config
dev doctor
```

`config` exibe configuração de Azure Repos da pasta atual. `doctor` valida o remote, o Git, a conexão/autenticação Azure DevOps e a localização do repositório. Não exiba saídas de diagnóstico contendo dados internos da sua organização sem revisar primeiro.

## 11. Erros comuns e recuperação

### Erro: `fatal: a branch named 'main' already exists`

É resultado de tentar recriar a branch local com `git switch --track origin/main`. Prefira `dev main`, que reconhece a branch existente, ou `git switch main`. Para trazer commits remotos use `dev main --update` após conferir o estado do repositório.

### Erro: `dev tasks` não retorna dados

Verifique se as Tasks estão atribuídas ao seu usuário e abertas. Tente `dev tasks --all` e `dev doctor`. `dev tasks` **não** exige data e não lista PBIs. Itens que estejam somente no backlog sem atribuição aparecem em `--all`, se sua conta puder consultá-los.

### Erro: configuração ausente

Você pode estar em outro clone ou em uma pasta que não pertence a um repositório Azure Repos. Execute `dev init` no clone correto e confira `git remote -v`.

### Erro: falha de autenticação

Confirme `az login` no tenant correto ou configure um PAT válido. Permissões de Git e de Azure Boards podem ser independentes. Use `dev doctor` e teste o acesso pelo navegador da sua organização.

### Erro: `git switch` impedido por alterações locais

Verifique `git status` e `git diff`. Faça commit, stash ou descarte **deliberadamente** as mudanças conforme sua decisão. O DevFlow não força a troca de branch.

### Erro: PR já existe

Use `dev prs` ou `dev pr ID`. Não execute comandos manualmente para duplicar PRs. Se `dev finish` criou a PR mas não conseguiu retornar à `main`, utilize `dev main` quando a pasta estiver limpa.

### Erro: Sprint não encontrada

Configure datas e Iterations na equipe apropriada no Azure Boards e tente `dev sprint --all`. A organização pode ter mais de uma equipe; nesse caso informe `--team`.

### Erro: pipelines/deploys vazios

Confirme que os serviços estão habilitados, que existem execuções e que sua conta tem permissão de leitura. Classic Releases e YAML Environments podem apresentar resultados distintos. Não interprete falha de permissão como inexistência de deploys.

### Erro: terminal não suporta interface interativa

Use `dev dashboard --view summary`, com `--json` se necessário. Garanta stdin/stdout TTY e tamanho razoável do terminal. Em sessões SSH, configure corretamente as capacidades do terminal e a variável `TERM`.

## 12. Segurança, limitações e boas práticas

- **Segredos:** o DevFlow não grava PATs; não use argumentos de linha de comando para transportar credenciais nem comite arquivos sensíveis.
- **Revisão de commits:** antes de `dev save`, use `git diff`, `git status` e revise os arquivos incluídos. O bloqueio de nomes conhecidos de arquivos secretos não é uma varredura abrangente.
- **Branches protegidas:** configure revisores obrigatórios e políticas de PR no Azure Repos; o DevFlow não as configura ou ignora.
- **Associação ao Azure Boards:** `AB#ID` e o vínculo de artefato dependem de repositório e permissões corretas.
- **Histórico de alterações:** as operações de Git não têm uma função de desfazer geral; revise antes de commitar e fazer push.
- **Rede e APIs:** o DevFlow utiliza Azure DevOps REST 7.1, GitHub API de Releases e Git; em redes corporativas, proxies podem interferir.
- **Limites de resultados:** alguns comandos mostram somente amostras recentes ou possuem limites explícitos (`--limit`).
- **Sem garantia de disponibilidade:** o serviço Azure DevOps e as credenciais pertencem à conta/organização do usuário.
- **Publicação:** o pacote pode ser instalado a partir de tags verificadas manualmente. Confirme o repositório oficial antes de executar scripts baixados.

Consulte [SECURITY.md](../SECURITY.md) e [ARQUITETURA.md](ARQUITETURA.md).

## 13. Referência rápida

| Ação | Comando |
|---|---|
| Ver versão | `dev --version` |
| Configurar repo | `dev init` |
| Diagnosticar | `dev doctor` |
| Minhas tarefas | `dev tasks` |
| Tarefas da equipe | `dev tasks --all` |
| Detalhes de WI | `dev show 8` |
| Criar Task vinculada | `dev new 'Título' --parent 5` |
| Assumir Task | `dev claim 14` |
| Atribuir Task | `dev assign 14 pessoa@exemplo.com` |
| Agendar tag de dia | `dev plan 14 --date 2026-11-09` |
| Sprint atual | `dev sprint` |
| Começar trabalho | `dev start 8` |
| Commit + push | `dev save 'mensagem'` |
| Abrir PR e voltar à main | `dev finish` |
| Consultar PRs | `dev prs` |
| Consultar PR | `dev pr 12` |
| Voltar à main | `dev main` |
| Atualizar main (ff-only) | `dev main --update` |
| Apenas fetch/prune | `dev sync` |
| Listar pipelines | `dev pipelines` |
| Ver falhas CI | `dev builds --failed` |
| Consultar deploys | `dev deploys` |
| TUI | `dev dashboard` |
| Dashboard JSON | `dev dashboard --view summary --json` |
| Ver release recente | `dev update --check` |
| Atualizar | `dev update` |

**Suporte:** abra uma issue com logs não sensíveis, versões e passos para reproduzir em [GitHub Issues](https://github.com/felipeflosii/devflow-cli/issues); reporte falhas de segurança de forma privada, conforme [SECURITY.md](../SECURITY.md).
