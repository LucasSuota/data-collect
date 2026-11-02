# frontend

> A interface web do construtor de formulários: React, TypeScript (`strict`), Vite e Tailwind.

## Responsabilidade

Só apresentação. O front **não reimplementa** o avaliador de fórmulas nem a validação: usa `/definicoes/validar`, `/definicoes/previa` e os erros por campo que a API devolve (AGENTS.md §2.4). Textos em português.

## O que tem aqui

| Caminho                                | Papel                                                     |
| -------------------------------------- | --------------------------------------------------------- |
| `src/main.tsx`, `src/App.tsx`          | Entrada e componente raiz                                 |
| `src/test/setup.ts`                    | Configuração do Vitest + Testing Library                  |
| `vite.config.ts`                       | Vite, Tailwind e Vitest (porta fixa 5173)                 |
| `eslint.config.js`, `.prettierrc.json` | Lint (sem `any` nem `@ts-ignore` sem motivo) e formatação |

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

## Cuidados

- Sem `any` nem `@ts-ignore` sem motivo comentado (AGENTS.md §9, item 12).
- Estado do servidor vem da API; não duplicar regra de negócio aqui.
- Biblioteca nova só com justificativa.
