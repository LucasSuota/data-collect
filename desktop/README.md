# desktop

> A janela Electron do app instalável: abre o backend Python como processo filho e mostra o front.

## Responsabilidade

Gerar o token da execução, iniciar o backend embutido, ler a porta da primeira linha da saída dele e abrir `http://127.0.0.1:<porta>`. Se o backend cair, mostra um erro em português em vez de uma janela em branco; ao fechar, encerra o backend. **Não tem regra de negócio** e não mexe em banco (AGENTS.md §4.1).

## O que tem aqui

| Arquivo            | Papel                                                                                                |
| ------------------ | ---------------------------------------------------------------------------------------------------- |
| `src/logica.ts`    | Lógica pura, testada: ler a porta, `urlPermitida`, token, comando do backend, página de erro e a CSP |
| `src/principal.ts` | Processo principal: janela, processo filho, bloqueio de navegação, permissões e encerramento         |
| `src/preload.ts`   | A única ponte com a página: expõe só `window.formsApi = { token }`                                   |
| `src/*.test.ts`    | Testes da lógica e conferências de segurança sobre o código-fonte                                    |

## Como se conecta

- **Backend:** em desenvolvimento roda `uv run python -m forms.app`; empacotado, o executável do PyInstaller em `resources/backend/forms-backend` (ver `empacotamento/`). O token vai por `FORMS_TOKEN` e a primeira linha da saída (`{"porta": N}`) traz a porta.
- **Front:** servido pelo próprio backend na mesma origem; o token chega à página pelo _preload_.
- **Dados do usuário:** na pasta de dados do sistema (`platformdirs`), nunca dentro do pacote.

## Segurança (AGENTS.md §4.1 e §12)

- `contextIsolation` ligado, `nodeIntegration` desligado, `sandbox` ligado, sem `remote`; DevTools só fora do pacote.
- A janela só navega para `http://127.0.0.1:<porta>` (a origem é comparada já interpretada, não o início do texto); nenhuma janela nova abre.
- CSP só da própria origem (sem `eval`, script em linha, objeto ou frame); todas as permissões (câmera, localização...) são negadas.
- Uma única instância: duas abririam dois backends sobre o mesmo banco.

## Como rodar e testar

```bash
cd desktop
npm ci                 # baixa o binário do Electron
npm run build          # tsc -> dist/
npm start              # abre a janela (precisa de `npm run build` no frontend/ e do uv)
npm run lint && npm run format:check && npm run typecheck && npm test
```

Os testes não precisam do binário (`ELECTRON_SKIP_BINARY_DOWNLOAD=1`).

## Verificação manual (a janela em si não é testada automaticamente)

Abrir, criar um registro, fechar e reabrir (o registro continua lá); matar o processo do backend com a janela aberta e ver a página de erro em português; exportar um CSV e ver o diálogo nativo de salvar.

## Cuidados

- O preload não pode importar módulos locais (por causa do `sandbox`), então repete o prefixo do argumento do token; um teste confere que é o mesmo de `logica.ts`.
- No Windows o backend é encerrado com `taskkill /t` (o `kill` não derruba os netos).
- Assinatura de código e notarização estão fora do escopo (AGENTS.md §2.9): o macOS e o Windows mostram um aviso na primeira abertura.
