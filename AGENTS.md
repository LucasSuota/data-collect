# Construtor de Formulários Modulares — Contexto para Agentes de IA

> Este arquivo é o **contexto canônico** do projeto para qualquer agente de IA (Claude, Cursor, Codex, Copilot, etc.). Toda IA que trabalhar neste repositório **deve** ler e seguir o que está aqui antes de propor mudanças. Este arquivo é a **única fonte de verdade** do projeto: se código, README ou outro documento divergirem dele, o AGENTS.md vence (ou é atualizado de propósito, junto com a mudança).

---

## 1. Visão geral

Sistema local para **montar formulários por definição (JSON)**, preencher esses formulários e guardar os registros em **SQLite**. Sem foco em setor: o mesmo sistema serve para inspeção de obra, ensaios de laboratório, checklists ou qualquer cadastro. Inspiração: Fulcrum, mas local, simples e **sem usuários nem cargos**.

> **Este repositório é somente o BACKEND.** A interface web (construtor com arrastar e soltar, `FormRenderer`, telas de preenchimento e consulta) vive em **outro repositório**, que consome a API daqui. Não há código de frontend, `package.json` nem `frontend/` neste repo. O que o front precisa deste backend está em §5.3.

O controle de corpos de prova de concreto (projeto original) é apenas um **template de demonstração** (`templates/corpo_de_prova.json`), que prova que o sistema genérico dá conta de um caso real com cálculo de resistência e conformidade.

O projeto é também **material de portfólio/entrevista**: o autor precisa conseguir explicar o núcleo linha por linha (fórmulas, validação, versionamento, RAG). Isso orienta várias regras abaixo.

### Estado atual

O projeto acabou de ser iniciado: existe o esqueleto (`pyproject.toml`, `src/forms/`, `tests/`, `README.md`, `AI_NOTES.md`), mas ainda nenhum módulo do núcleo. As pastas e módulos descritos aqui são o **alvo**; ao criá-los, siga exatamente esta estrutura e atualize este arquivo se algo mudar.

### Princípio central

> **A IA nunca calcula, só busca e redige.** Quem calcula e valida é código determinístico (campos calculados com fórmulas). Nenhum número de negócio sai de um LLM.

---

## 2. Escopo — o que será feito

### 2.1. Núcleo (obrigatório, sem IA)

- **Formulário = definição em JSON, versionada.** Registro = dados em JSON + a versão com que foi criado. Editar um formulário **nunca** quebra registros antigos.
- **Tipos de campo do MVP:** texto, número (com unidade), data, seleção, sim/não, calculado, seção (só visual).
- **Validação no servidor** contra a definição: tipo, obrigatório, opções válidas.
- **Campos calculados:** fórmulas avaliadas por avaliador próprio sobre o módulo `ast` do Python, com lista de permissão (operadores, comparações, `se`, `min`, `max`, `media`, `soma`, `pi`, `dias`).
- O servidor **recalcula sempre** ao salvar. O frontend pode mostrar prévia, mas não é fonte da verdade.
- Ordem de cálculo pelas **dependências** entre campos; **ciclo é rejeitado ao publicar** a versão.
- Campo de entrada vazio gera resultado vazio; erro de fórmula (ex.: divisão por zero) aparece **no campo**, sem derrubar o registro.

### 2.2. Suporte ao construtor de formulários (o construtor em si é do outro repo)

- Criar formulário e **publicar uma nova versão** a partir de uma definição JSON, rejeitando definição inválida (fórmula proibida, campo inexistente, ciclo, tipo desconhecido) com erro claro e localizado.
- Endpoint para **validar/pré-visualizar** uma definição e para **calcular uma prévia** de fórmulas sem salvar (o servidor continua sendo a fonte da verdade; o front não reimplementa o avaliador).
- Expor o catálogo de tipos de campo e de funções de fórmula permitidas, para a paleta e o editor do front não ficarem dessincronizados.

### 2.3. Registros: preencher e consultar

- Criar e atualizar registro contra uma versão publicada; validar e recalcular sempre no servidor.
- Listar registros com colunas derivadas da definição, filtro simples e **exportação CSV**.

### 2.4. Interfaces

- **API** (FastAPI) e **CLI enxuta** (importar template, criar registro a partir de JSON, listar e exportar) chamam as **mesmas funções** de `servico.py`, que não sabe quem as chama.
- A API é consumida pelo repositório de frontend; o contrato é o **OpenAPI** gerado pelo FastAPI (§5.3).

### 2.5. Módulos de IA (opcionais — só depois do núcleo estar pronto e testado)

- **Assistente de procedimentos (RAG):** procedimentos em `.md` (escritos pelo autor, genéricos ou sintéticos), busca com **BM25 escrito à mão**, resposta do LLM **somente com os trechos recuperados**, exibindo trecho e arquivo de origem. Sem base nos documentos → responde "não encontrei". Sem internet ou chave de API → mostra só os trechos (fallback).
- **Resumo de registros por IA:** o LLM redige a partir dos dados e de agregados **calculados pelo código** (contagem, média etc.), em saída estruturada (JSON). O código confere se **todos os números do texto batem com o banco**; se não baterem, o resumo é rejeitado.

### 2.6. Entregáveis de documentação

- `README.md` (inclui "próximos passos").
- `AI_NOTES.md`: registro de **erros reais da IA** durante a construção (ver §10).

---

## 3. Escopo — o que NÃO será feito

Estas exclusões são **deliberadas**. Não implemente, não "adiante" e não sugira como parte de uma tarefa comum. Se uma tarefa parecer exigir algo daqui, pare e pergunte.

### 3.1. Funcionalidades fora do escopo (vão para "próximos passos" no README)

- Grupo repetível (tabela de linhas), visibilidade condicional, foto e localização.
- Relação entre formulários (ex.: lote com vários corpos de prova).
- Usuários, login, cargos e permissões. O uso é local; a API ouve **só em `127.0.0.1`**.
- Modo offline e sincronização; mapas.
- IA que sugere um formulário a partir de texto.
- Qualquer código de interface web (React, HTML, CSS, `dist/`). Mesmo para "testar rápido": use Swagger (`/docs`), `curl` ou `TestClient`.
- Deploy, hospedagem e infraestrutura (CI além de lint e testes).
- `Dockerfile` e `docker-compose`: avaliado e **adiado**. SQLite local + `uv` já dão ambiente reproduzível. Só reconsiderar se alguém sem Python precisar subir a API ou se houver deploy; nesse caso é um `Dockerfile` mínimo, discutido antes.

### 3.2. Tecnologias proibidas

LangChain, LlamaIndex, bancos vetoriais, **ORM** (use `sqlite3` direto), Docker, Postgres, bibliotecas de autenticação. **Nova dependência exige justificativa** — o autor precisa conseguir defender cada uma.

### 3.3. Proibições de comportamento

- ❌ **Nunca `eval`, `exec`, `compile` ou `__import__`** para fórmulas. Só o avaliador sobre `ast` com lista de permissão. Nó de AST fora da lista → erro explícito, nunca ignorado.
- ❌ **Nunca pedir ao LLM para calcular, converter unidade, somar ou conferir número.** O LLM só redige texto sobre dados já calculados.
- ❌ Não confiar no frontend: validação e recálculo são do servidor, sempre.
- ❌ Não colocar regra de negócio em `api.py` nem em `cli.py`; ela fica em `servico.py` e abaixo.
- ❌ Não fazer mudança incompatível no contrato (OpenAPI ou formato do JSON de definição) sem sinalizar explicitamente, porque o frontend em outro repo quebra (§5.3).
- ❌ Não importar o SDK do LLM fora de `ia/cliente.py`.
- ❌ Não alterar a definição de uma versão já publicada (versões são imutáveis); mudança = nova versão.
- ❌ Não commitar `.env`, chaves de API, nem dados reais de cliente. `.env` entra no `.gitignore` **antes do primeiro commit**.

---

## 4. Stack técnico

| Camada | Tecnologia |
|---|---|
| Linguagem e ambiente | Python 3.12+, `uv`, `pyproject.toml` |
| Domínio | `dataclasses`, type hints |
| Persistência | `sqlite3` (stdlib); dados dinâmicos em colunas JSON |
| Fórmulas | módulo `ast` com lista de permissão |
| CLI | `argparse` |
| API | FastAPI, Uvicorn, Pydantic v2 **só na borda** (nunca no domínio) |
| Recuperação (opcional) | BM25 escrito à mão, sem framework |
| IA (opcional) | SDK de um LLM (ex.: Anthropic), isolado em `ia/cliente.py` |
| Configuração | `python-dotenv`, `.env` fora do git |
| Qualidade | `pytest`, `httpx` (TestClient), `ruff`, GitHub Actions |

**Execução local:** `uv run uvicorn forms.api:app --host 127.0.0.1 --port 8000` (a CLI roda por `uv run`). Sem Docker (§3.1).
**Frontend em dev:** o outro repo roda na porta 5173 (Vite) e chama esta API em `http://127.0.0.1:8000`. Como são origens diferentes, a API habilita **CORS apenas para `http://localhost:5173` e `http://127.0.0.1:5173`** (configurável por variável de ambiente); nunca `*`.

---

## 5. Arquitetura

```
src/forms/   models.py  tipos_campo.py  formulas.py  validacao.py
             repositorio.py  servico.py  cli.py  api.py
             rag/  chunker.py  indice.py  responder.py        (opcional)
             ia/   cliente.py  resumo.py  validacao.py        (opcional)
templates/   corpo_de_prova.json  inspecao_obra.json  (exemplos)
docs/        procedimentos em .md (base do assistente)
tests/       test_formulas.py  test_validacao.py  test_servico.py  test_api.py ...
```

### 5.1. Camadas e direção de dependência

```
api.py / cli.py  →  servico.py  →  validacao.py, formulas.py, tipos_campo.py
                                →  repositorio.py  →  sqlite3
```

- **`models.py`**: `dataclasses` do domínio. Sem Pydantic, sem I/O.
- **`tipos_campo.py`**: o que cada tipo aceita, valida e normaliza.
- **`formulas.py`**: parse, grafo de dependências, detecção de ciclo e avaliação. Funções puras, sem I/O.
- **`validacao.py`**: valida um registro contra uma definição.
- **`repositorio.py`**: único módulo que fala SQL. Sempre com parâmetros (`?`), nunca f-string em SQL.
- **`servico.py`**: casos de uso (importar template, publicar versão, criar/atualizar registro, listar, exportar). Ponto de entrada comum de API e CLI.
- **`api.py`**: Pydantic e HTTP só aqui; traduz erros de domínio em respostas HTTP.
- **`cli.py`**: `argparse` fino; só chama `servico.py`.
- Dependências apontam **para baixo**: o núcleo nunca importa `api`, `cli`, `rag` ou `ia`.
- **Módulos opcionais** (`rag/`, `ia/`) dependem do núcleo, nunca o contrário; o app inteiro funciona com eles removidos.

### 5.2. Modelo de dados (SQLite)

```
formularios          id, nome, criado_em
versoes_formulario   id, formulario_id, numero, definicao (JSON), publicada_em
registros            id, formulario_id, versao_id, dados (JSON), criado_em, atualizado_em
```

- Todo registro aponta para a `versao_id` com que nasceu.
- Esquema criado/migrado por código simples em `repositorio.py` (sem ferramenta de migração).

Exemplo de definição (trecho do template de corpo de prova; este é o formato do contrato):

```json
{
  "campos": [
    {"id": "fck_mpa", "tipo": "numero", "rotulo": "fck especificado", "unidade": "MPa", "obrigatorio": true},
    {"id": "diametro_mm", "tipo": "numero", "rotulo": "Diâmetro", "unidade": "mm", "obrigatorio": true},
    {"id": "data_moldagem", "tipo": "data", "rotulo": "Data de moldagem", "obrigatorio": true},
    {"id": "carga_kn", "tipo": "numero", "rotulo": "Carga de ruptura", "unidade": "kN"},
    {"id": "ruptura_28d", "tipo": "calculado", "rotulo": "Ruptura aos 28 dias",
     "formula": "data_moldagem + dias(28)"},
    {"id": "resistencia_mpa", "tipo": "calculado", "rotulo": "Resistência", "unidade": "MPa",
     "formula": "carga_kn * 1000 / (pi * (diametro_mm / 2) ** 2)"},
    {"id": "conforme", "tipo": "calculado", "rotulo": "Conforme?",
     "formula": "resistencia_mpa >= fck_mpa"}
  ]
}
```

### 5.3. Contrato com o frontend (repositório separado)

- O frontend é outro repo; **este backend é a fonte da verdade** de dados, validação, cálculo e do esquema da definição de formulário.
- O contrato tem duas partes: o **OpenAPI** do FastAPI (`/openapi.json`, `/docs`) e o **formato do JSON de definição** (§6). Modelos Pydantic da API têm nomes e campos estáveis e `response_model` explícito em todo endpoint.
- Mudança **compatível** (campo opcional novo, endpoint novo): livre. Mudança **incompatível** (renomear/remover campo, mudar tipo, mudar semântica): só com aviso explícito na tarefa/PR, descrevendo o impacto no front.
- Erros da API têm formato uniforme (`{"detalhe": "...", "erros": [{"campo": "...", "mensagem": "..."}]}`) com mensagens em PT-BR, para o front exibir no campo certo. Erro de validação de registro → 422; recurso inexistente → 404; definição inválida ao publicar → 422.
- Endpoints não dependem de estado de sessão nem de cookie. Sem autenticação nesta fase.
- Texto livre ou número vindo do front nunca é confiável (§3.3).

---

## 6. Idiomas

| Onde | Idioma |
|---|---|
| **Vocabulário de domínio** (`formulario`, `registro`, `versao`, `rotulo`, `obrigatorio`, módulos `servico.py`, `tipos_campo.py`…, tabelas, chaves do JSON de definição e campos da API) | **Português** (sem acentos em identificadores) |
| **Termos técnicos/infra** (`handler`, `middleware`, `router`, `fixture`) | **Inglês** quando já são o nome padrão da técnica |
| **Textos visíveis ao usuário**, mensagens de erro e de validação | **Português brasileiro** |
| **Comentários, README, `AI_NOTES.md`, este arquivo, PRs** | **Português brasileiro** |
| **Mensagens de commit** | **Inglês** (Conventional Commits) |

Regra de ouro: **o JSON de definição e o OpenAPI são contratos** com o repo de frontend (`campos`, `id`, `tipo`, `rotulo`, `unidade`, `obrigatorio`, `formula`). Não traduza nem renomeie por conveniência de um lado só (ver §5.3).

---

## 7. Fórmulas — regras de segurança e comportamento

O avaliador é a peça mais importante e mais testada do projeto.

- Parse com `ast.parse(..., mode="eval")`; percorrer a árvore com **allowlist explícita** de nós (constantes numéricas/booleanas, nomes de campo, operadores aritméticos e de comparação, `and`/`or`/`not`, chamadas às funções permitidas).
- Funções permitidas: `se`, `min`, `max`, `media`, `soma`, `pi`, `dias`. Qualquer outra → erro claro.
- Proibido: atributos (`a.b`), subscripts, lambdas, comprehensions, f-strings, imports, chamadas a nomes não listados.
- Nome desconhecido na fórmula (campo inexistente) → rejeitado **ao publicar**, não ao preencher.
- Grafo de dependências → ordem topológica; **ciclo rejeitado ao publicar** com mensagem que cita os campos do ciclo.
- Entrada vazia → resultado vazio. Erro de execução (divisão por zero, tipo incompatível) → o campo guarda o erro; o registro continua válido e salvo.
- Aritmética sobre números: decidir e documentar uma vez (ex.: `float` vs `Decimal`) e testar arredondamento do template de corpo de prova.
- Cobrir com testes: caminho feliz, cada operador, cada função, entradas vazias, divisão por zero, nó proibido, tentativa de injeção (`__import__('os')`, `().__class__`…), ciclo, dependência inexistente.

---

## 8. TDD

TDD é a regra para o **núcleo**: `formulas.py`, `validacao.py`, `tipos_campo.py`, `servico.py` e `repositorio.py`.

1. **Red** — escreva o teste que falha primeiro.
2. **Green** — o mínimo de código para passar.
3. **Refactor** — melhore com a rede de segurança dos testes.

- Estilo: `pytest`, **Arrange / Act / Assert** explícito, um comportamento por teste, nome descritivo (`test_ciclo_entre_campos_e_rejeitado_ao_publicar`).
- Banco de teste: SQLite **em memória** ou arquivo temporário (`tmp_path`); nunca o banco real.
- API: `fastapi.testclient.TestClient` (via `httpx`).
- LLM: **sempre** substituído por um cliente falso nos testes. Nenhum teste faz chamada de rede nem exige chave.
- **Prioridade de cobertura:** `formulas.py` e `validacao.py` primeiro e mais fundo. É o que o autor vai defender em voz alta.
- Contrato: teste de API confere o formato de erro uniforme e que os campos dos modelos de resposta não mudaram sem querer (compare com o JSON esperado).
- Verificação manual: suba a API e exercite o fluxo em `/docs` (Swagger) ou `curl`, além dos testes.

---

## 9. Código limpo — princípios fixos

1. **Nomes claros e completos.**
2. **Funções e módulos pequenos**, com uma responsabilidade.
3. Comente o **porquê** (decisão, restrição, bug), nunca o **quê**. Comentários em PT-BR.
4. **Type hints em todo código Python**; `dataclass(frozen=True)` onde fizer sentido. Imutabilidade preferida.
5. **Sem `Any`** nem `# type: ignore` sem motivo comentado; use `object`/`TypedDict`/narrowing quando o tipo é dinâmico (ex.: JSON).
6. **Sem código morto** nem código comentado.
7. **Sem abstração prematura** — regra do 3: só extraia quando o terceiro caso aparecer.
8. **Erros explícitos:** exceções de domínio próprias (ex.: `FormulaInvalida`, `CicloDeDependencia`, `RegistroInvalido`), traduzidas para HTTP só em `api.py`. Nunca `except: pass`; se ignorar de propósito, comente o porquê.
9. **Dependências explícitas** — nada de singletons globais escondidos; conexão e cliente entram por parâmetro.
10. **Não desabilitar regra de lint sem motivo** comentado em PT-BR.
11. **Código explicável:** no núcleo, prefira o código simples que o autor consegue justificar linha por linha a um truque esperto.

---

## 10. Trabalhando com IA neste repositório

- Ao cometer ou corrigir um **erro real de IA** (lógica errada, API inventada, teste que passa por motivo errado, número alucinado), acrescente uma entrada em `AI_NOTES.md`: o que foi pedido, o que a IA fez de errado, como foi detectado e a correção. Seja honesto: o arquivo é parte da defesa do projeto.
- Não "melhore" o núcleo além da tarefa pedida. Mudanças em `formulas.py` e `validacao.py` precisam de teste novo que as justifique.
- Quando houver dúvida sobre escopo, consulte §2 e §3 e **pergunte** em vez de adivinhar.

---

## 11. Linha de corte

Se o tempo apertar, corte **nesta ordem**:

1. Resumo por IA
2. Assistente RAG
3. CLI além de importar e listar
4. Exportação CSV
5. Endpoint de prévia de fórmulas (o front ainda calcula só ao salvar)

**Nunca cortar:** README, `AI_NOTES.md`, ensaio em voz alta e **testes de fórmulas e validação**.

---

### Pontos que o autor precisa saber defender

- **IA não calcula:** é onde ela erra (aritmética, valores inventados). O cálculo é de um avaliador determinístico e o resumo por IA é validado contra o banco.
- **Formulário é dado, não código:** definição em JSON versionado; registros apontam para a versão com que nasceram, então evoluir um formulário não quebra o histórico.
- **Fórmulas sem `eval`:** avaliador sobre `ast` com allowlist, porque executar texto digitado pelo usuário é falha de segurança. Ordem por dependência, ciclos rejeitados.
- **Servidor é a fonte da verdade:** valida e recalcula sempre; o cliente nunca é confiável.
- **Núcleo independente das interfaces:** API e CLI são camadas finas sobre `servico.py`.
- **Framework só no encanamento** (FastAPI): o que se explica linha por linha (fórmulas, validação, versionamento, RAG) é código próprio.

---

## 12. Segurança

- API ouvindo **somente `127.0.0.1`**.
- SQL sempre parametrizado.
- Chave de API só em `.env` / variável de ambiente; nunca no frontend nem em log.
- Saída do LLM é **dado não confiável**: valide contra o esquema esperado e contra o banco antes de exibir.
- CORS restrito às origens do frontend em dev (§4); nunca `allow_origins=["*"]`.
- Texto vindo do usuário (rótulos, opções, valores) é tratado como dado, nunca executado; a API não devolve HTML.
- Exportação CSV: neutralizar células iniciadas por `=`, `+`, `-`, `@` (injeção de fórmula em planilha).

---

## 13. Commits e branches

- Mensagens de commit em **inglês**, **Conventional Commits**:
  ```
  feat(formulas): add dependency ordering and cycle detection
  fix(validacao): reject option values outside the field definition
  test(servico): cover record update against an older form version
  refactor(repositorio): extract JSON column helpers
  chore(deps): add dnd-kit
  docs: update AGENTS.md scope
  ```
- Branches: `feat/<descricao-curta>`, `fix/<...>`, `refactor/<...>`, `chore/<...>`.
- PRs descrevem **o que** e **por que** em PT-BR.
- Commits pequenos, um por unidade lógica; testes no mesmo commit do código que cobrem.
- Nunca `git push --force` em `main`.

---

## 14. Antes de marcar uma tarefa como pronta

- [ ] Testes novos/alterados cobrindo a lógica (`uv run pytest`)
- [ ] Lint e formatação (`uv run ruff check .` e `uv run ruff format .`)
- [ ] **Testado manualmente** quando mexer em API/CLI: golden path + 1 caso de borda via `/docs` ou `curl` (testes não substituem ver funcionando)
- [ ] Contrato (OpenAPI / JSON de definição) inalterado ou mudança incompatível sinalizada (§5.3)
- [ ] Nenhum `eval`/`exec`, nenhum SQL por concatenação, nenhum segredo no diff
- [ ] Sem `print` de depuração, `Any` injustificado ou TODO sem explicação
- [ ] Nada fora do escopo da §2 foi adicionado; nada da §3 foi violado
- [ ] `AI_NOTES.md` atualizado se houve erro real de IA
- [ ] Este arquivo e o README atualizados se estrutura, comandos ou escopo mudaram

---

## 15. Referências rápidas

- Python `ast`: https://docs.python.org/3/library/ast.html
- FastAPI: https://fastapi.tiangolo.com
- `uv`: https://docs.astral.sh/uv
- Frontend: repositório separado (adicionar o link aqui quando existir)
