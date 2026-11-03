# frontend

> A interface web do construtor de formulários: React, TypeScript (`strict`), Vite e Tailwind.

## Responsabilidade

Só apresentação. O front **não reimplementa** o avaliador de fórmulas nem a validação: usa `/definicoes/validar`, `/definicoes/previa` e os erros por campo que a API devolve (AGENTS.md §2.4). Textos em português.

## O que tem aqui

| Caminho                        | Papel                                                                                                                                                                                                                                                           |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/main.tsx`, `src/App.tsx`  | Entrada, layout e a troca de tela pela rota                                                                                                                                                                                                                     |
| `src/rotas.ts`                 | Navegação por `#hash` (sem biblioteca de rotas: são poucas telas e o backend serve só o `index.html`)                                                                                                                                                           |
| `src/api/cliente.ts`           | Cliente `fetch` da API: URL base e token configuráveis, erro uniforme tipado (`ErroDaApi`)                                                                                                                                                                      |
| `src/api/contexto.tsx`         | `ApiProvider`/`useApi`: injeta o cliente (os testes o trocam por um falso)                                                                                                                                                                                      |
| `src/api/esquema.d.ts`         | Tipos **gerados** do OpenAPI (`npm run api:tipos`); não editar                                                                                                                                                                                                  |
| `openapi.json`                 | O OpenAPI do backend (`uv run forms-openapi --saida frontend/openapi.json`)                                                                                                                                                                                     |
| `src/components/FormRenderer/` | Renderiza qualquer versão de formulário **por `id`**: texto, número, data, seleção, sim/não, calculado, seção, referência, localização e foto. A prévia dos calculados vem do servidor, com debounce                                                            |
| `src/construtor/`              | O construtor: paleta vinda do `/catalogo`, arrastar e soltar (`dnd-kit`), painel de propriedades guiado pelo catálogo, editor de fórmulas com erro sublinhado por `posicao` e publicação                                                                        |
| `src/ia/`                      | "Criar com IA": pedido, rascunhos propostos com os erros de cada um, edição de cada rascunho no construtor e "Publicar todos" (`POST /formularios/lote`)                                                                                                        |
| `src/mapa/`                    | O mapa de dependências (`#/mapa`): grafo de formulários e de registros (`grafo.ts`), layout em camadas da origem para os dependentes (`layout.ts`), zoom e ajuste (`geometria.ts`), cartões, ligações e inspetor; tudo puro e testado, sem biblioteca de grafos |
| `src/registros/`               | O editor de registro reutilizável (página e gaveta) e a pilha de gavetas (`ProvedorDeGavetas`): criar ou editar a origem de uma referência sem sair do preenchimento                                                                                            |
| `src/paginas/`                 | Telas: formulários e pastas (árvore lateral com filtro, busca por nome e ordenação, trilha, mover por menu ou arrastando), preencher/editar registro, listagem com filtros, paginação e CSV                                                                     |
| `src/ui/`                      | Componentes base (`Botao`, `CampoDeTexto`, `CampoDeBusca`, `Aviso`, `Cartao`, `Gaveta`, `Conformidade`, `Selo`, `EstadoVazio`, `Icone`) sobre os tokens de `src/index.css`; as telas usam estes, nunca valores soltos                                           |
| `src/lib/`                     | `formatarNumero` (arredondamento decimal exato, meio para cima, só para exibição) e formatação de células                                                                                                                                                       |
| `src/test/`                    | Configuração do Vitest e o cliente falso dos testes                                                                                                                                                                                                             |

## Como se conecta

- **Depende de:** a API do backend (`uv run uvicorn forms.api:app --host 127.0.0.1 --port 8000`). Em desenvolvimento ela libera CORS só para `http://localhost:5173` e `http://127.0.0.1:5173`, por isso a porta do Vite é fixa (`strictPort`).
- **Contrato:** os tipos TypeScript da API são **gerados** do OpenAPI, nunca escritos à mão.

## Como rodar

```bash
cd frontend
npm ci
npm run dev        # http://localhost:5173
npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
```

## Tipos da API

Os tipos vêm do `openapi.json`, que o backend exporta. Depois de mudar a API:

```bash
uv run forms-openapi --saida frontend/openapi.json   # na raiz do repositório
cd frontend && npm run api:tipos
```

O CI falha se `openapi.json` ou `src/api/esquema.d.ts` estiverem desatualizados.

**Token e URL da API:** no app instalado vêm do _preload_ do Electron (`window.formsApi`); em desenvolvimento, de `VITE_API_URL` e `VITE_FORMS_TOKEN` (ou deixe a API com `FORMS_SKIP_TOKEN=1`).

## Decisões que moldam este código

- **Design tokens num só lugar** (`@theme` em `src/index.css`): paleta, fontes, raios, sombras e movimento. Direção: papel quente e tinta (`papel`, `superficie`, escala `pedra-*`), uma só cor de sinal (`sinal-*`, laranja) reservada a foco, seleção e destino de arraste, e cores de estado (`erro`, `sucesso`, `aviso`) com contraste AA. Foco visível global e `prefers-reduced-motion` desliga animações e transições. Não há modo escuro (fora do escopo desta fase).
- **Dependência `@fontsource/ibm-plex-sans` e `-mono`** (licença OFL): a fonte vai **dentro do pacote**, porque o app instalado funciona offline e não pode depender de CDN. Só os pesos latinos usados (400, 500, 600 e mono 400, 500), que cobrem o português.

- **O servidor é a fonte da verdade:** o front não valida nem calcula. Os erros chegam por `id` de campo e aparecem no campo certo; o construtor valida pelo `/definicoes/validar` e a prévia pelo `/definicoes/previa`.
- **Erros presos à identidade estável, não à posição:** no construtor cada campo tem uma `chave` própria; reordenar não desloca os erros (AGENTS.md §5.3). Depois de um publicar que falhou, a validação pausa até a próxima edição, para não apagar erros que só o publicar conhece (contrato entre versões).
- **Criar com IA nunca salva sozinho:** o rascunho é dado não confiável (pode ter tipo desconhecido ou lixo), e `deRascunho` nunca lança. Cada entrada de `campos` vira um campo, mesmo malformada, para o índice dos erros (`campos[3].id`) continuar certo. O construtor em modo rascunho **não valida enquanto edita**: o conjunto só pode ser validado junto, na publicação em lote, porque os rascunhos podem depender uns dos outros. Os erros do lote voltam com o nome do formulário como prefixo e são devolvidos ao rascunho certo.
- **Editar registro antigo usa a definição da versão dele**, não a atual.
- **Foto:** `<img src>` não manda o cabeçalho do token, então a miniatura vem por `fetch` e vira uma URL local.
- **Busca e ordem são do cliente:** a lista de formulários e pastas é pequena e já está na tela, então `filtros.ts` (funções puras e testadas) filtra e ordena sem ir ao servidor. A busca ignora acento e maiúsculas, exige todas as palavras e procura em todas as pastas (ou só na aberta e nas descendentes); o resultado mostra o caminho de cada item. O filtro da árvore lateral mantém o caminho até a pasta achada e expande os ramos. O layout da linha de formulário muda pela largura da lista (container query), não da janela.
- **O mapa não calcula nem consulta nada novo:** os valores vêm das listagens (já calculados pelo servidor) e o grafo é montado no cliente. A listagem da API traz uma versão por vez, então `registrosDoFormulario.ts` lê todas as versões; há um limite de 200 registros por versão, e o mapa avisa quando corta. O layout é por camadas (o caminho mais longo até cada nó, a mesma ordem da cascata de recálculo) e as dimensões dos cartões são fixas, para as ligações caírem no lugar certo.
- **Gavetas empilhadas:** o campo de referência abre o editor da origem num portal (`Gaveta`), por isso o `<form>` dela não fica dentro do formulário de baixo e o envio não sobe pela árvore do React (`stopPropagation`). Sem o `ProvedorDeGavetas` (por exemplo, num `FormRenderer` isolado), o campo só oferece escolher.
- **Pastas só organizam:** a API devolve a lista plana e o front monta a árvore (`pastas.ts`, funções puras e testadas). Ciclo e nome repetido são regras do servidor; o front só esconde o que o servidor recusaria (mover uma pasta para dentro dela mesma) e mostra o erro dele no campo. Mover um formulário funciona por menu ("Mover para…") e arrastando para a árvore ou para um cartão de pasta; os anúncios do arraste são em português. Ao recarregar depois de mover, duplicar ou excluir, a tela mantém os dados anteriores em vez de voltar ao esqueleto.
- **Arrastar no construtor** (`construtor/arraste.ts`, funções puras e testadas): o item no ar é um `DragOverlay` (elevação e borda na cor de sinal), a origem fica como "fantasma" tracejado, e um indicador mostra a posição em que um tipo da paleta vai entrar; reordenar anima os vizinhos. O campo recém-criado entra com animação e já fica selecionado. Os anúncios para leitor de tela e as instruções são em português, e `useMovimentoReduzido` tira a animação de soltar (feita em JavaScript, fora do alcance do CSS) quando a pessoa pede menos movimento.
- **Editor de fórmulas** (`EditorDeFormula.tsx`, `formulaTexto.ts`): combobox acessível (setas, Enter/Tab aceitam, Esc fecha), dica da função com o argumento atual em destaque (assinatura, descrição e exemplo vêm do `/catalogo`), par automático de parênteses e destaque do par ao lado do cursor. O front **não parseia** a fórmula: `formulaTexto.ts` só olha parênteses e vírgulas, para ajudar a digitar e sinalizar parêntese sem par antes de validar; o erro "oficial", com a posição, continua vindo do servidor. Os campos compartilhados pelas origens (`<referência>__<campo>`, §2.7) vêm da versão atual de cada origem (`useCamposDeOrigem`), só os tipos que uma fórmula pode usar.
- **Fórmula por blocos** (`blocos.ts`, `EditorDeBlocos.tsx`): os blocos são **fichas léxicas** do texto (campo, número, operador, função, parênteses, vírgula), sempre derivadas dele a cada render; o texto só é reescrito (com espaçamento normal) quando se edita um bloco, então alternar entre Texto e Blocos sem editar não muda nada, nem os espaços. O que não tem bloco (`outro`) é preservado e avisado. Não há gramática nem tipos no front: o servidor valida e calcula, e o erro dele é destacado nos blocos pela `posicao`. Inserir pela paleta (clique, no cursor) ou arrastando, reordenar arrastando ou com Alt+setas, remover com × ou Delete.
- **Dependência `@dnd-kit`:** arrastar e soltar com sensores de teclado e leitor de tela prontos; escrever isso à mão seria bem mais código e pior em acessibilidade. Todo campo também tem botões de mover, que servem ao teclado e aos testes.

## Cuidados

- Sem `any` nem `@ts-ignore` sem motivo comentado (AGENTS.md §9, item 12).
- Estado do servidor vem da API; não duplicar regra de negócio aqui.
- Biblioteca nova só com justificativa.
