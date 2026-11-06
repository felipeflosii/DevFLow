# Política de segurança

A segurança do DevFlow CLI depende tanto do código da ferramenta quanto das permissões de sua conta Azure DevOps e das políticas do repositório.

## Versões com suporte

| Versão | Status |
|---|---|
| `1.0.x` | Suportada para correções de segurança |
| `0.x` | Versões anteriores: migre para a release estável |

Não há garantia de manutenção indefinida de versões antigas. A seção acima será atualizada com novas releases.

## Relatar uma vulnerabilidade

**Não abra uma issue pública para vulnerabilidades que possam expor credenciais, executar ações não autorizadas ou afetar usuários.** Utilize a opção **Report a vulnerability** na aba **Security** do repositório GitHub, caso habilitada, por meio de GitHub Private Vulnerability Reporting. Se a opção não estiver habilitada, abra uma issue **sem detalhes exploráveis nem segredos** solicitando um canal privado de contato com os mantenedores.

Descreva o cenário e o impacto, a versão utilizada, os passos mínimos para reproduzir em ambiente autorizado e o comportamento esperado. Nunca compartilhe PATs, cookies, URLs privadas com tokens, credenciais de produção ou dados pessoais reais.

Os mantenedores analisarão os relatos e, quando necessário, coordenarão uma correção antes da divulgação pública. Não há promessa de prazo específico de resposta.

## Boas práticas para usuários

1. **Use credenciais de menor privilégio:** consulte somente permissões de leitura quando necessário; evite PAT com acesso total. Separe contas de teste e produção.
2. **Não comite segredos:** `dev save` verifica alguns nomes de arquivos sensíveis, mas não detecta todos os segredos embutidos no conteúdo. Use ferramentas de secret scanning e revise o diff.
3. **Não compartilhe configuração e JSON sem revisar:** o arquivo de configuração não armazena PAT, mas contém organização, projeto e nomes de repositórios.
4. **Proteja a branch principal:** revisões obrigatórias, políticas de build e controles de merge devem ser aplicados no Azure Repos.
5. **Faça download somente de fontes oficiais verificadas:** prefira instalar de uma tag publicada no repositório GitHub correto. Leia scripts antes de executá-los.
6. **Preserve a sessão Azure:** não compartilhe tokens, caches locais ou capturas de tela que exponham informações sensíveis.
7. **Não desative verificações de Git:** o DevFlow evita reset/merge forçados, mas não é uma ferramenta de segurança de endpoint ou de prevenção de exfiltração.

## Escopo e limitações

- O projeto automatiza a API do Azure DevOps e ações Git. **Não** fornece autenticação própria nem guarda segredos em servidor próprio.
- Chamadas de mutação (`new`, `assign`, `claim`, `plan`, `start`, `save`, `finish`) respeitam as permissões fornecidas pela conta Azure DevOps/Git.
- O dashboard TUI é majoritariamente de leitura; ao iniciar uma Task, a ação pede confirmação e aplica as validações do fluxo `dev start`.
- `dev update` usa a API de GitHub Releases e instala via pipx. A barra de progresso informa etapas concluídas, não porcentagem de bytes.
- O software não audita políticas de acesso, não valida o conteúdo completo de commits para detectar segredos e não substitui uma revisão humana.

## Procedimento em caso de credencial exposta

Revogue ou rotacione imediatamente o token na origem; revise permissões e logs da organização; procure referências ao segredo em commits e releases, seguindo as políticas da organização; preserve evidências pertinentes e reporte o incidente pelos canais adequados. Excluir um commit local não basta quando ele já foi publicado.
