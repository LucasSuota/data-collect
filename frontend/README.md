# frontend

> A interface web do construtor de formulários: React, TypeScript (`strict`), Vite e Tailwind.

## Responsabilidade

Só apresentação. O front **não reimplementa** o avaliador de fórmulas nem a validação: usa `/definicoes/validar`, `/definicoes/previa` e os erros por campo que a API devolve (AGENTS.md §2.4). Textos em português.

## O que tem aqui

| Caminho                        | Papel                                                                                                                                                                                                |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/main.tsx`, `src/App.tsx`  | Entrada, layout e a troca de tela pela rota                                                                                                                                                          |
| `src/rotas.ts`                 | Navegação por `#hash` (sem biblioteca de rotas: são poucas telas e o backend serve só o `index.html`)                                                                                                |
| `src/api/cliente.ts`           | Cliente `fetch` da API: URL base e token configuráveis, erro uniforme tipado (`ErroDaApi`)                                                                                                           |
| `src/api/contexto.tsx`         | `ApiProvider`/`useApi`: injeta o cliente (os testes o trocam por um falso)                                                                                                                           |
| `src/api/esquema.d.ts`         | Tipos **gerados** do OpenAPI (`npm run api:tipos`); não editar                                                                                                                                       |
| `openapi.json`                 | O OpenAPI do backend (`uv run forms-openapi --saida frontend/openapi.json`)                                                                                                                          |
| `src/components/FormRenderer/` | Renderiza qualquer versão de formulário **por `id`**: texto, número, data, seleção, sim/não, calculado, seção, referência, localização e foto. A prévia dos calculados vem do servidor, com debounce |
| `src/construtor/`              | O construtor: paleta vinda do `/catalogo`, arrastar e soltar (`dnd-kit`), painel de propriedades guiado pelo catálogo, editor de fórmulas com erro sublinhado por `posicao` e publicação             |
| `src/ia/`                      | "Criar com IA": pedido, rascunhos propostos com os erros de cada um, edição de cada rascunho no construtor e "Publicar todos" (`POST /formularios/lote`)                                             |
| `src/paginas/`                 | Telas: lista de formulários, preencher/editar registro, listagem com filtros, paginação e CSV                                                                                                        |
| `src/ui/`                      | Componentes base (`Botao`, `CampoDeTexto`, `Aviso`, `Cartao`, `Selo`, `EstadoVazio`, `Icone`) sobre os tokens de `src/index.css`; as telas usam estes, nunca valores soltos                          |
| `src/lib/`                     | `formatarNumero` (arredondamento decimal exato, meio para cima, só para exibição) e formatação de células                                                                                            |
| `src/test/`                    | Configuração do Vitest e o cliente falso dos testes                                                                                                                                                  |

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
- **Dependência `@dnd-kit`:** arrastar e soltar com sensores de teclado e leitor de tela prontos; escrever isso à mão seria bem mais código e pior em acessibilidade. Todo campo também tem botões de mover, que servem ao teclado e aos testes.

## Cuidados

- Sem `any` nem `@ts-ignore` sem motivo comentado (AGENTS.md §9, item 12).
- Estado do servidor vem da API; não duplicar regra de negócio aqui.
- Biblioteca nova só com justificativa.
