# frontend

> A interface web do construtor de formulários: React, TypeScript (`strict`), Vite e Tailwind.

## Responsabilidade

Só apresentação. O front **não reimplementa** o avaliador de fórmulas nem a validação: usa `/definicoes/validar`, `/definicoes/previa` e os erros por campo que a API devolve (AGENTS.md §2.4). Textos em português.

## O que tem aqui

| Caminho                          | Papel                                                                                                                                                                                                                                                                                                                 |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/main.tsx`, `src/config.ts`  | Entrada e a configuração em tempo de execução: `/config.json` (escrito pelo `logto-setup`) ou, no `npm run dev`, as variáveis `VITE_*`                                                                                                                                                                                |
| `src/auth/`                      | Login com `@logto/react` (`Autenticacao.tsx`), a sessão (`sessao.ts`: `GET /eu`, equipe ativa, `pode(permissao)`), as telas de antes do login (entrada, termos, sem equipe, convite) e a página pública dos textos legais                                                                                             |
| `src/shell/`                     | A moldura: menu lateral a partir de 640 px, barra de baixo com o botão de novo registro no celular, busca, sino de notificações e `permissoes.tsx` (`ComPermissao`/`Bloqueado`: some ou fica bloqueado com a frase da permissão que falta). `navegacao.ts` deriva os itens das **permissões**, nunca do nome do cargo |
| `src/telas/`                     | Início (com passeio e "Primeiros passos"), equipe e convites, cargos e permissões, IA, assistente (chat por SSE), central de ajuda, galeria de exemplos, busca, perfil e direitos LGPD                                                                                                                                |
| `src/rotas.ts`                   | Navegação por `#hash` (sem biblioteca de rotas)                                                                                                                                                                                                                                                                       |
| `src/api/cliente.ts`             | Cliente `fetch`: `Authorization: Bearer`, `X-Equipe`, renovação do token **uma vez** ao receber `401 token_expirado`, erro uniforme tipado (`ErroDaApi` com `codigo`)                                                                                                                                                 |
| `src/api/esquema.d.ts`           | Tipos **gerados** do OpenAPI (`npm run api:tipos`); não editar                                                                                                                                                                                                                                                        |
| `src/components/FormRenderer/`   | Renderiza qualquer versão de formulário **por `id`**: texto, número, data, seleção, sim/não, calculado, seção, referência e localização (com "Usar minha localização"). A prévia dos calculados vem do servidor                                                                                                       |
| `src/construtor/`                | O construtor: paleta do `/catalogo`, arrastar e soltar, propriedades, editor de fórmulas, **rascunho compartilhado** com salvamento automático, "Validar" e "Publicar versão N"                                                                                                                                       |
| `src/mapa/`                      | O mapa de vínculos: grafo, layout, zoom, inspetor, **criação de vínculo pelas portas** (campo `referencia` no rascunho do dependente) e a lista indentada para telas estreitas                                                                                                                                        |
| `src/registros/`, `src/paginas/` | Editor de registro (revisão, conflito 409, histórico, barra de salvar fixa), listagem (cartões no celular, tabela a partir de 640 px, chips por estado com contagens do servidor, "só os meus", CSV), formulários e pastas                                                                                            |
| `src/ui/`                        | Componentes base sobre os tokens de `src/index.css`: `Botao`, `Gaveta` (folha de baixo no celular), `SeloDeEstado` (sempre ícone **e** texto), `Interruptor`, `Marca`...                                                                                                                                              |
| `src/lib/`                       | Formatação, `Markdown.tsx` (renderizador próprio, sem HTML cru) e utilitários                                                                                                                                                                                                                                         |
| `public/`                        | `manifest.webmanifest`, ícones, `logo.svg` (usado pela tela de login) e `sw.js`: service worker que guarda **só arquivos estáticos**                                                                                                                                                                                  |
| `e2e/`                           | Playwright contra a pilha real (celular e desktop): primeiro acesso pelo convite, fluxo do dia a dia, acessibilidade (axe) e orçamento de JS                                                                                                                                                                          |

## Como se conecta

- **Depende de:** a API (pelo proxy em `/api`, ou `VITE_API_URL` no desenvolvimento) e do Logto (OIDC).
- **Contrato:** os tipos da API são **gerados** do OpenAPI, nunca escritos à mão.

## Como rodar

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173 (a API libera CORS só para essa origem)
npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
npm run e2e        # com a pilha no ar: docker compose up -d --build
```

Para o `npm run dev`, aponte o front para a API e para o Logto do compose: `VITE_API_URL`, `VITE_LOGTO_ENDPOINT`, `VITE_LOGTO_APP_ID` e `VITE_LOGTO_RESOURCE` (o `logto-setup` já cadastra `http://localhost:5173` como origem permitida no ambiente de desenvolvimento).

O `npm run e2e` precisa de `E2E_INVITE_URL` (o link do primeiro convite, que a API escreve no log na primeira subida) na primeira execução; ele guarda a sessão em `frontend/.auth/` para as seguintes. Para refazer o cadastro, apague `frontend/.auth` e suba a pilha do zero. O proxy limita o login a 30 tentativas por minuto, de propósito: por isso os testes reaproveitam a sessão.

## Tipos da API

Os tipos vêm do `openapi.json`, que o backend exporta. Depois de mudar a API:

```bash
uv run forms-openapi --saida frontend/openapi.json   # na raiz do repositório
cd frontend && npm run api:tipos
```

O CI falha se `openapi.json` ou `src/api/esquema.d.ts` estiverem desatualizados.

## Decisões que moldam este código

- **Design tokens num só lugar** (`@theme` em `src/index.css`): paleta (Gelo, Papel, Preto e **um** azul de ação; Conforme, Não conforme e Atenção), fontes, raios, sombras e movimento. Os nomes (`papel`, `pedra-*`, `sinal-*`) vêm da primeira versão; os valores são os do sistema de design de `data-collect-design-pattern.pdf`.
- **Dependências `@fontsource/*` (Archivo, IBM Plex Sans e Mono):** as fontes vão **dentro do pacote**: nenhum terceiro (Google Fonts, CDN) vê o IP de quem usa o app (LGPD). Só os pesos latinos usados.

- **O servidor é a fonte da verdade:** o front não valida nem calcula. Os erros chegam por `id` de campo e aparecem no campo certo; o construtor valida pelo `/definicoes/validar` e a prévia pelo `/definicoes/previa`.
- **Erros presos à identidade estável, não à posição:** no construtor cada campo tem uma `chave` própria; reordenar não desloca os erros (AGENTS.md §5.3). Depois de um publicar que falhou, a validação pausa até a próxima edição, para não apagar erros que só o publicar conhece (contrato entre versões).
- **Criar com IA nunca salva sozinho:** o rascunho é dado não confiável (pode ter tipo desconhecido ou lixo), e `deRascunho` nunca lança. Cada entrada de `campos` vira um campo, mesmo malformada, para o índice dos erros (`campos[3].id`) continuar certo. O construtor em modo rascunho **não valida enquanto edita**: o conjunto só pode ser validado junto, na publicação em lote, porque os rascunhos podem depender uns dos outros. Os erros do lote voltam com o nome do formulário como prefixo e são devolvidos ao rascunho certo.
- **Editar registro antigo usa a definição da versão dele**, não a atual.
- **Busca e ordem são do cliente:** a lista de formulários e pastas é pequena e já está na tela, então `filtros.ts` (funções puras e testadas) filtra e ordena sem ir ao servidor. A busca ignora acento e maiúsculas, exige todas as palavras e procura em todas as pastas (ou só na aberta e nas descendentes); o resultado mostra o caminho de cada item. O filtro da árvore lateral mantém o caminho até a pasta achada e expande os ramos. O layout da linha de formulário muda pela largura da lista (container query), não da janela.
- **O mapa não calcula nem consulta nada novo:** os valores vêm das listagens (já calculados pelo servidor) e o grafo é montado no cliente. A listagem da API traz uma versão por vez, então `registrosDoFormulario.ts` lê todas as versões; há um limite de 200 registros por versão, e o mapa avisa quando corta. O layout é por camadas (o caminho mais longo até cada nó, a mesma ordem da cascata de recálculo) e as dimensões dos cartões são fixas, para as ligações caírem no lugar certo.
- **Gavetas empilhadas:** o campo de referência abre o editor da origem num portal (`Gaveta`), por isso o `<form>` dela não fica dentro do formulário de baixo e o envio não sobe pela árvore do React (`stopPropagation`). Sem o `ProvedorDeGavetas` (por exemplo, num `FormRenderer` isolado), o campo só oferece escolher.
- **Pastas só organizam:** a API devolve a lista plana e o front monta a árvore (`pastas.ts`, funções puras e testadas). Ciclo e nome repetido são regras do servidor; o front só esconde o que o servidor recusaria (mover uma pasta para dentro dela mesma) e mostra o erro dele no campo. Mover um formulário funciona por menu ("Mover para…") e arrastando para a árvore ou para um cartão de pasta; os anúncios do arraste são em português. Ao recarregar depois de mover, duplicar ou excluir, a tela mantém os dados anteriores em vez de voltar ao esqueleto.
- **Arrastar no construtor** (`construtor/arraste.ts`, funções puras e testadas): o item no ar é um `DragOverlay` (elevação e borda na cor de sinal), a origem fica como "fantasma" tracejado, e um indicador mostra a posição em que um tipo da paleta vai entrar; reordenar anima os vizinhos. O campo recém-criado entra com animação e já fica selecionado. Os anúncios para leitor de tela e as instruções são em português, e `useMovimentoReduzido` tira a animação de soltar (feita em JavaScript, fora do alcance do CSS) quando a pessoa pede menos movimento.
- **Editor de fórmulas** (`EditorDeFormula.tsx`, `formulaTexto.ts`): combobox acessível (setas, Enter/Tab aceitam, Esc fecha), dica da função com o argumento atual em destaque (assinatura, descrição e exemplo vêm do `/catalogo`), par automático de parênteses e destaque do par ao lado do cursor. O front **não parseia** a fórmula: `formulaTexto.ts` só olha parênteses e vírgulas, para ajudar a digitar e sinalizar parêntese sem par antes de validar; o erro "oficial", com a posição, continua vindo do servidor. Os campos compartilhados pelas origens (`<referência>__<campo>`, §2.7) vêm da versão atual de cada origem (`useCamposDeOrigem`), só os tipos que uma fórmula pode usar.
- **Fórmula por blocos** (`blocos.ts`, `EditorDeBlocos.tsx`): os blocos são **fichas léxicas** do texto (campo, número, operador, função, parênteses, vírgula), sempre derivadas dele a cada render; o texto só é reescrito (com espaçamento normal) quando se edita um bloco, então alternar entre Texto e Blocos sem editar não muda nada, nem os espaços. O que não tem bloco (`outro`) é preservado e avisado. Não há gramática nem tipos no front: o servidor valida e calcula, e o erro dele é destacado nos blocos pela `posicao`. Inserir pela paleta (clique, no cursor) ou arrastando, reordenar arrastando ou com Alt+setas, remover com × ou Delete.
- **Dependência `@dnd-kit`:** arrastar e soltar com sensores de teclado e leitor de tela prontos; escrever isso à mão seria bem mais código e pior em acessibilidade. Todo campo também tem botões de mover, que servem ao teclado e aos testes.

- **`@logto/react`:** identidade e renovação do token (OIDC com PKCE) sem escrever criptografia nem fluxo de login. O token vive 10 minutos; o SDK o renova com refresh token. **A sessão é memoizada** pelos dados, porque o SDK liga `isLoading` a cada busca de token e uma sessão recriada fazia as telas refazerem as chamadas em laço.
- **Permissão no front é conveniência:** `ComPermissao`/`Bloqueado` escondem ou bloqueiam com explicação; quem barra é sempre o servidor.
- **`@playwright/test` e `@axe-core/playwright`:** os testes ponta a ponta contra a pilha real e a verificação de acessibilidade (WCAG A e AA) entram no mesmo fluxo.
- **PWA:** o service worker nunca cacheia resposta da API, token, `/config.json` nem dados da equipe; não há uso offline de dados.

## Cuidados

- Sem `any` nem `@ts-ignore` sem motivo comentado (AGENTS.md §9, item 12).
- Estado do servidor vem da API; não duplicar regra de negócio aqui.
- Biblioteca nova só com justificativa.
