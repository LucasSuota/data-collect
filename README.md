# Construtor de Formulários Modulares

Aplicativo instalável (Windows, macOS e Linux) para **montar formulários por definição JSON**, preenchê-los e guardar os registros em SQLite, tudo local. Serve para inspeção de obra, ensaios de laboratório, checklists ou qualquer cadastro. Não há usuários nem cargos.

Os campos calculados usam fórmulas avaliadas por um avaliador próprio sobre `ast`, sem `eval`. Princípio central: **a IA nunca calcula, só busca e redige.** Quem calcula e valida é código determinístico.

O projeto é um monorepo: backend Python, interface web e shell desktop. O contexto completo (escopo, arquitetura, regras) está em [AGENTS.md](AGENTS.md), que é a fonte da verdade.

## Estado atual

O núcleo (fórmulas, validação, repositório, serviço), a API, a CLI, o `frontend/`, o `desktop/` (Electron), o empacotamento do instalável e os módulos de IA (`ia/` e `rag/`) estão implementados e testados com TDD. **Não verificado ainda:** a janela do Electron e o fluxo no navegador real foram exercitados só por testes automatizados e `curl`, e nenhuma chamada real a um LLM foi feita (os testes usam um cliente falso). A ordem de construção foi de baixo para cima: tipos e fórmulas, validação, repositório, serviço, API e CLI, front e Electron, e por último os módulos de IA.

## O que o sistema faz

- **Formulário é dado, não código.** A definição é um JSON versionado. Cada registro aponta para a versão com que nasceu, então evoluir um formulário nunca quebra o histórico. Versões publicadas são imutáveis.
- **Tipos de campo:** texto, número (com unidade e `casas_decimais`), data, seleção, sim/não, calculado, seção (só visual), referência a outro formulário, localização e foto.
- **Servidor é a fonte da verdade.** Valida e recalcula sempre; o front mostra prévia, mas não decide nada.
- **Relação entre formulários.** Um formulário pode depender de outro por referência a um registro (ex.: `insitu` depende de `proctor`, que depende de `ensaio`). A origem escolhe quais campos compartilha; editar a origem recalcula os dependentes em cascata.
- **Localização e foto.** Coordenadas (latitude e longitude) validadas por faixa. Fotos são convertidas para WebP e reduzidas para ficar em torno de 50 a 80 KB, com o EXIF removido.
- **Registros:** criar, editar, excluir, listar com filtro simples e exportar CSV pronto para o Excel em português.
- **IA opcional:** assistente de procedimentos (RAG com BM25 escrito à mão), resumo de registros validado contra o banco e **gerador de formulário**: a pessoa descreve o que quer, a IA propõe um ou mais formulários, ligados entre si ou a formulários existentes, o código os valida e a pessoa revisa e aprova no construtor. A IA nunca salva nada sozinha.

## Exemplo de definição

Trecho do template de demonstração (controle de corpos de prova de concreto):

```json
{
  "campos": [
    {"id": "fck_mpa", "tipo": "numero", "rotulo": "fck especificado", "unidade": "MPa", "obrigatorio": true},
    {"id": "diametro_mm", "tipo": "numero", "rotulo": "Diâmetro", "unidade": "mm", "obrigatorio": true},
    {"id": "data_moldagem", "tipo": "data", "rotulo": "Data de moldagem", "obrigatorio": true},
    {"id": "carga_kn", "tipo": "numero", "rotulo": "Carga de ruptura", "unidade": "kN"},
    {"id": "ruptura_28d", "tipo": "calculado", "rotulo": "Ruptura aos 28 dias",
     "formula": "data_moldagem + dias(28)"},
    {"id": "resistencia_mpa", "tipo": "calculado", "rotulo": "Resistência", "unidade": "MPa", "casas_decimais": 1,
     "formula": "carga_kn * 1000 / (pi * (diametro_mm / 2) ** 2)"},
    {"id": "conforme", "tipo": "calculado", "rotulo": "Conforme?",
     "formula": "resistencia_mpa >= fck_mpa"}
  ]
}
```

Um campo calculado sempre chega ao front como `{"valor": ..., "erro": ...}`, para o erro de uma fórmula aparecer no campo sem derrubar o registro.

## Como as fórmulas funcionam

- **Segurança:** o texto é lido com `ast.parse` e percorrido com uma lista de permissão de nós. Nunca `eval`, `exec` nem `compile`. Atributos, subscripts, lambdas e imports são rejeitados.
- **Funções:** `se`, `min`, `max`, `media`, `soma`, `dias` e a constante `pi`.
- **Números:** sempre `Decimal`, nunca `float`. Na API e no banco, número vai como string (`"25.50"`) para não perder precisão no JavaScript.
- **Vazio propaga:** se um operando está vazio, o resultado é vazio, sem erro. Assim uma média parcial nunca vira um "conforme" falso.
- **Tipos checados ao publicar:** `data * 2`, `data + data` ou `se` com ramos de tipos diferentes são rejeitados antes de qualquer registro existir. Datas aceitam `data ± dias(n)`, `data − data` (resulta em dias) e comparações entre datas.
- **Dependências:** a ordem de cálculo vem do grafo de dependências. Ciclo entre campos, ou entre formulários, é rejeitado ao publicar, citando os envolvidos.
- **Erros de execução** (divisão por zero) ficam no campo; erros de definição impedem a publicação, com mensagem localizada pelo `id` do campo.

## Arquitetura

```
frontend/      React + TypeScript + Vite + Tailwind
desktop/       Electron: janela, processo filho do backend, instalador
src/forms/     backend Python
  models.py  tipos_campo.py  formulas.py  validacao.py  fotos.py
  repositorio.py  servico.py (+ servico_*.py)  exportacao.py  cli.py  api.py (+ api_*.py)  app.py
  rag/  ia/                                  (opcionais; achados pelo nome em api_extensoes.py)
templates/     corpo_de_prova.json  inspecao_obra.json
empacotamento/ scripts do instalável
tests/
```

Resumo de cada pasta com código: [src/forms/README.md](src/forms/README.md) e [templates/README.md](templates/README.md).

A dependência sempre aponta para baixo:

```
api.py / cli.py  →  servico.py  →  validacao.py, formulas.py, tipos_campo.py, fotos.py
                                →  repositorio.py  →  sqlite3
```

- Regra de negócio fica em `servico.py` e abaixo; `api.py` e `cli.py` são camadas finas.
- Só `repositorio.py` fala SQL, sempre parametrizado. Sem ORM.
- Pydantic só na borda da API. O domínio usa `dataclasses`.
- Os módulos opcionais (`rag/`, `ia/`) dependem do núcleo, nunca o contrário.

## API

O contrato é o OpenAPI gerado pelo FastAPI (`/docs`); os tipos TypeScript do front são gerados dele. Erros têm formato uniforme (`{"detalhe": "...", "erros": [{"campo": "...", "mensagem": "..."}]}`) com mensagens em português.

| Área | Endpoints |
|---|---|
| Formulários e versões | `POST /formularios` (cria e publica a v1), `POST /formularios/lote` (vários de uma vez, na ordem das dependências), `GET /formularios`, `GET /formularios/{id}`, `POST /formularios/{id}/duplicar` (cópia com a v1 igual à versão atual, na mesma pasta, sem registros), `DELETE /formularios/{id}`, `POST` e `GET /formularios/{id}/versoes`, `GET /formularios/{id}/versoes/{versao_id}` |
| Construtor | `POST /definicoes/validar`, `POST /definicoes/previa`, `GET /catalogo` |
| Pastas | `POST` e `GET /pastas`, `PUT` e `DELETE /pastas/{id}` (árvore que só organiza; excluir só pasta vazia), `PUT /formularios/{id}/pasta` (mover, `null` = raiz) |
| Registros | `POST /formularios/{id}/registros`, `GET`, `PUT` e `DELETE /registros/{id}` |
| Consulta | `GET /formularios/{id}/registros` (versão, filtro por igualdade, paginação), `GET /formularios/{id}/registros/exportar` (CSV) |
| Fotos | `POST /anexos` (multipart), `GET /anexos/{id}` |
| IA (opcional) | `POST /definicoes/gerar` (propõe formulários, nunca salva), `POST /formularios/{id}/resumo` (resumo conferido contra os dados), `POST /assistente/perguntar` (só com os procedimentos). Sem chave ou internet respondem 503 em português, e o assistente mostra só os trechos |

## IA (opcional)

Três recursos, todos com a mesma regra: **a IA nunca calcula, só busca e redige**.

- **Criar com IA:** a pessoa descreve o que quer, a IA propõe um ou mais formulários (ligados entre si, se o pedido pedir), o servidor valida o conjunto e devolve os erros ao LLM para corrigir (no máximo 2 vezes). A pessoa revisa e edita cada rascunho no construtor e publica todos de uma vez. Nada é salvo antes.
- **Resumo de registros:** o código calcula os agregados; o LLM só redige. Todo número do texto é conferido contra os agregados, e o resumo inteiro é descartado se algum não bater.
- **Assistente de procedimentos (RAG):** BM25 escrito à mão sobre os `.md` de `docs/`, mais busca semântica se houver provedor de embeddings. Responde só com os trechos recuperados e diz "não encontrei" quando não há base.

Para ligar: `uv sync --extra ia` e `ANTHROPIC_API_KEY` no `.env`. Sem isso, as rotas respondem 503 e o restante do app funciona normalmente. A API da Anthropic não tem embeddings, então a busca semântica só liga com outro provedor que implemente `ClienteDeLLM`.

## App instalável

O instalado tem dois processos: o Electron abre a janela e gerencia o backend Python, que escolhe uma porta livre em `127.0.0.1` e serve o build do front na mesma origem. Os dados do usuário (banco e fotos) ficam na pasta de dados do sistema. Cada execução gera um token exigido pela API, para que outro programa da máquina não a chame.

O PyInstaller não compila para outro sistema, então cada instalador é gerado no próprio sistema, numa matriz de CI.

## Como rodar

Requer [uv](https://docs.astral.sh/uv) e Python 3.12+:

```bash
uv sync
cp .env.example .env
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Para subir a API em desenvolvimento:

```bash
uv run uvicorn forms.api:app --host 127.0.0.1 --port 8000
```

O front roda separado em `http://localhost:5173` (Vite) e a API libera CORS só para essa origem, nunca `*`.

## Qualidade

- **TDD** no núcleo, com `formulas.py` e `validacao.py` primeiro e mais fundo. O LLM é sempre substituído por um cliente falso nos testes, que nunca fazem chamada de rede.
- **CI** (GitHub Actions): o job `lint` roda `ruff check` e `ruff format --check` uma vez, no Linux; o job `testes` roda `pytest` numa matriz com Linux, Windows e macOS (sem `fail-fast`, para ver os três resultados). Ambos usam `uv sync --locked`. O front terá job próprio (lint, typecheck, testes e build). O `.gitattributes` força fim de linha LF para o checkout no Windows não alterar os arquivos.
- **Segurança:** API só em `127.0.0.1`, SQL parametrizado, upload de foto validado pelo conteúdo e sem EXIF, exportação CSV com neutralização de injeção de fórmula em células de texto, chave de API só em `.env`.
- **Agentes** (`agents/`): o `orchestrator` recebe toda tarefa, confere o escopo e aciona `issue-creator`, `issue-planner`, `issue-coder`, `issue-reviewer`, `doc-writer` e `git-manager`, parando para o autor nas decisões que importam. O `doc-writer` mantém um `README.md` de resumo em cada pasta com código (o que é, como se conecta, como testar).
- **`AI_NOTES.md`** registra os erros reais da IA durante a construção.

## Próximos passos (fora do escopo atual)

- Grupo repetível (tabela de linhas) e visibilidade condicional.
- Consulta espacial (distância, raio) e mapas sobre as coordenadas.
- Renomear formulário e migrar um registro para outra versão.
- Filtro por número e por data na listagem.
- Fórmulas com campos de texto e seleção; função que ignora vazios (`media_preenchidos`).
- Fotos em HEIC e captura direta pela câmera.
- Assinatura de código, notarização e atualização automática do instalável.
- Usuários, cargos e permissões; modo offline com sincronização.
