# Guia de contribuição — DevFlow CLI

Obrigado por contribuir com o DevFlow CLI. Este projeto é independente, escrito em Python e tem como princípio **automatizar o fluxo Azure DevOps de forma segura, compreensível e verificável**.

## Antes de contribuir

- Leia [README.md](README.md), [docs/MANUAL.md](docs/MANUAL.md), [docs/ARQUITETURA.md](docs/ARQUITETURA.md), [SECURITY.md](SECURITY.md) e [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- Pesquise Issues e PRs existentes para evitar trabalho duplicado.
- Para bugs, crie uma issue com sistema operacional, Python, versão DevFlow, comandos, comportamento esperado, comportamento observado e reprodução mínima **sem segredos**.
- Para recursos grandes ou alterações incompatíveis, abra uma discussão antes de programar.

## Configuração local

```bash
git clone https://github.com/felipeflosii/devflow-cli.git
cd devflow-cli
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

No Windows PowerShell, use `.venv\Scripts\Activate.ps1`.

## Fluxo de contribuição

1. Faça fork ou crie branch no repositório autorizado.
2. Nomeie a branch de forma descritiva, como `feature/add-command-filter` ou `fix/tui-escape-key`.
3. Faça mudanças pequenas e focadas; preserve as interfaces públicas existentes sempre que possível.
4. Adicione testes para novas regras e para regressões corrigidas. Mocks devem evitar dependência de Azure DevOps real nos testes automáticos.
5. Atualize `docs/MANUAL.md`, README e CHANGELOG quando o comportamento dos comandos mudar.
6. Execute os testes e confira o `git diff --check`.
7. Abra uma PR explicando o problema, a solução, os testes executados e possíveis efeitos colaterais.

## Convenções de código

- Python `>=3.10`, anotação de tipos quando útil e mensagens claras ao usuário.
- Evite dependências desnecessárias; `prompt_toolkit` é a dependência adicional usada pela TUI.
- Não inclua segredos, dumps de APIs ou logs de produção nos testes.
- HTTP e Git devem ter tratamento explícito de erro e timeouts adequados.
- Evite comandos de Git destrutivos e alterações automáticas na branch base.
- Preserve saída `--json` para scripts; evite imprimir ANSI nos modos não interativos.
- Não introduza ações mutáveis no dashboard sem um mecanismo claro de confirmação e controle de permissões.
- Use `argparse` e recursos existentes em vez de acrescentar frameworks para tarefas pequenas.

## Testes esperados

```bash
python -m unittest discover -s tests -v
python -m compileall -q src
python -m pip check
```

No Linux/macOS também valide `bash -n install.sh`. Se alterar `install.ps1`, teste no PowerShell em um ambiente compatível. O CI executa testes em Windows, macOS e Linux; builds dependentes de rede não fazem parte da suíte unitária.

## Commits e Pull Requests

Sugestão de mensagens: `feat: ...`, `fix: ...`, `docs: ...`, `test: ...`, `refactor: ...`. Relacione a issue no corpo da PR quando aplicável.

Uma PR deve responder: o que mudou? por quê? como testar? há impacto em autenticação/credenciais? a documentação foi atualizada? a alteração é retrocompatível?

## Releases

Apenas mantenedores autorizados devem criar tags e releases. Use SemVer; em versões futuras atualize `pyproject.toml`, `src/devflow/__init__.py`, instaladores, changelog e documentação antes de taguear. Consulte [docs/PUBLICAR_NO_GITHUB.md](docs/PUBLICAR_NO_GITHUB.md). Não reescreva tags publicadas.

## Segurança e comunicação

Vulnerabilidades devem ser tratadas conforme [SECURITY.md](SECURITY.md), não em issues públicas com detalhes sensíveis. Respeite outros participantes conforme o [Código de Conduta](CODE_OF_CONDUCT.md).

**Este projeto não é afiliado à Microsoft.** É proibido apresentar contribuições como endosso oficial de qualquer fornecedor.
