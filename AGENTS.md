# Construtor de Formulários Modulares — Contexto para Agentes de IA

> Este arquivo é o **contexto canônico** do projeto para qualquer agente de IA (Claude, Cursor, Codex, Copilot, etc.). Toda IA que trabalhar neste repositório **deve** ler e seguir o que está aqui antes de propor mudanças. Este arquivo é a **única fonte de verdade** do projeto: se código, README ou outro documento divergirem dele, o AGENTS.md vence (ou é atualizado de propósito, junto com a mudança).

---

## 1. Visão geral

Sistema local para **montar formulários por definição (JSON)**, preencher esses formulários e guardar os registros em **SQLite**. Sem foco em setor: o mesmo sistema serve para inspeção de obra, ensaios de laboratório, checklists ou qualquer cadastro. Inspiração: Fulcrum, mas local, simples e **sem usuários nem cargos**.

> **Este repositório contém o app inteiro** (monorepo): o **backend** Python (`src/forms/`), a **interface web** (`frontend/`: construtor com arrastar e soltar, `FormRenderer`, telas de preenchimento e consulta; React, TypeScript, Vite e Tailwind), o **shell desktop** (`desktop/`, Electron) e o empacotamento do instalável (§4.1). O contrato entre front e backend está em §5.3.

O controle de corpos de prova de concreto (projeto original) é apenas um **template de demonstração** (`templates/corpo_de_prova.json`), que prova que o sistema genérico dá conta de um caso real com cálculo de resistência e conformidade.

O projeto é também **material de portfólio/entrevista**: o autor precisa conseguir explicar o núcleo linha por linha (fórmulas, validação, versionamento, RAG). Isso orienta várias regras abaixo.

### Estado atual

O núcleo, a API, a CLI, o `frontend/`, o `desktop/`, o empacotamento e os módulos de IA (`ia/`, `rag/`) existem e estão testados. As pastas e módulos descritos aqui continuam sendo a estrutura a seguir; atualize este arquivo se algo mudar. Ainda não verificados à mão: a janela do Electron, o fluxo no navegador real e qualquer chamada real a um LLM (os testes usam sempre o cliente falso).

**Ordem de construção (de baixo para cima, sempre com TDD):** `tipos_campo.py` e `formulas.py` (tipos, vazio, datas, funções) → `validacao.py` → `repositorio.py` → `servico.py` (publicar versão, registros, relação entre formulários, cascata, exclusão) → `api.py` e `cli.py` → `frontend/` e `desktop/` (só depois que núcleo e API estiverem testados) → módulos opcionais (`rag/`, `ia/`). A relação entre formulários (§2.7) faz parte do núcleo, mas só entra depois que fórmulas, validação e registros simples estiverem testados.

### Princípio central

> **A IA nunca calcula, só busca e redige.** Quem calcula e valida é código determinístico (campos calculados com fórmulas). Nenhum número de negócio sai de um LLM.

---

## 2. Escopo — o que será feito

### 2.1. Núcleo (obrigatório, sem IA)

- **Formulário = definição em JSON, versionada.** Registro = dados em JSON + a versão com que foi criado. Editar um formulário **nunca** quebra registros antigos.
- **Tipos de campo do MVP:** texto, número (com unidade), data, seleção, sim/não, calculado, seção (só visual), referência a registro de outro formulário (§2.7), localização (coordenadas) e foto (§2.8).
- **Validação no servidor** contra a definição: tipo, obrigatório, opções válidas.
- **Campos calculados:** fórmulas avaliadas por avaliador próprio sobre o módulo `ast` do Python, com lista de permissão (operadores, comparações, as funções `se`, `min`, `max`, `media`, `soma`, `dias` e a constante `pi`).
- O servidor **recalcula sempre** ao salvar. O frontend pode mostrar prévia, mas não é fonte da verdade.
- Ordem de cálculo pelas **dependências** entre campos; **ciclo é rejeitado ao publicar** a versão.
- Campo de entrada vazio gera resultado vazio; erro de fórmula (ex.: divisão por zero) aparece **no campo**, sem derrubar o registro.

### 2.2. Suporte ao construtor de formulários (o construtor em si é o `frontend/`)

- Criar formulário e **publicar uma nova versão** a partir de uma definição JSON, rejeitando definição inválida (fórmula proibida, campo inexistente, ciclo, tipo desconhecido, tipos incompatíveis na fórmula, `id` ausente/duplicado/reservado, `casas_decimais` inválido) com erro claro e localizado.
  - `POST /formularios`: recebe `{nome, definicao}`, cria o formulário e já publica a **versão 1** (um formulário sem versão não pode ser preenchido, então não existe esse estado). Definição inválida → 422 e nada é criado. O nome fica no formulário, fora da definição, e é **único** (sem diferenciar maiúsculas/minúsculas nem espaços nas pontas); nome repetido → 422 no campo `nome`. Como as referências entre formulários usam o nome (§2.7), renomear fica para "próximos passos". Importar templates que dependem uns dos outros exige a ordem das dependências (a origem primeiro).
  - `GET /formularios`: lista `{id, nome, criado_em, versao_atual_id, versao_atual_numero}`, sem definições.
  - `GET /formularios/{id}`: formulário com a **versão atual completa** (`id`, `numero`, `definicao`); é de onde o front tira o `versao_id` para preencher.
  - `POST /formularios/lote`: recebe `{formularios: [{nome, definicao}]}` e cria todos **numa só transação**, na ordem das dependências (origem primeiro), com a v1 de cada um. Os formulários do lote podem se referenciar entre si e a formulários já existentes. Qualquer erro (definição inválida, nome repetido dentro do lote ou já existente, ciclo) → 422 com os erros localizados por formulário e **nada é criado**. Serve a importação de templates dependentes e o gerador por IA (§2.5).
  - `POST /formularios/{id}/versoes`: recebe `{definicao}` e publica a próxima versão (`numero` anterior + 1); 422 se inválida. `GET /formularios/{id}/versoes` lista `{id, numero, publicada_em}`; `GET /formularios/{id}/versoes/{versao_id}` devolve a versão com definição (para renderizar um registro antigo).
  - Versões são imutáveis: não existe `PUT`, `PATCH` nem `DELETE` de versão (§3.3).
  - `DELETE /formularios/{id}`: regras de bloqueio em §2.7.
- Endpoint para **validar/pré-visualizar** uma definição e para **calcular uma prévia** de fórmulas sem salvar (o servidor continua sendo a fonte da verdade; o front não reimplementa o avaliador).
  - `POST /definicoes/validar`: sem estado (não exige formulário criado). Responde **200** com `{"valida": false, "erros": [...]}`, porque definição incompleta é o caso normal enquanto o usuário edita; o 422 vale só ao **publicar**. Devolve **todos** os erros de uma vez, não só o primeiro.
  - `POST /definicoes/previa`: recebe `{definicao, valores}` e devolve os campos calculados no formato `{"valor", "erro"}` (§7), sem salvar. Usa a **mesma função de cálculo** do salvar. Definição inválida devolve a mesma lista de erros do `validar`.
- Expor o catálogo de tipos de campo e de funções de fórmula permitidas, para a paleta e o editor do front não ficarem dessincronizados.
  - `GET /catalogo`: tipos de campo (id, rótulo, propriedades aceitas), funções (nome, assinatura, descrição, exemplo), a constante `pi` e os nomes reservados. É gerado da **mesma tabela de funções que o avaliador usa**, nunca de uma lista paralela.

### 2.3. Registros: preencher e consultar

- Criar e atualizar registro contra uma versão publicada; validar e recalcular sempre no servidor.
  - `POST /formularios/{id}/registros` exige `versao_id` no corpo: o front renderizou uma versão específica, e o servidor não valida contra outra em silêncio.
  - `PUT /registros/{id}` **substitui** todos os valores (sem `PATCH` parcial), valida e recalcula tudo; o registro continua na versão de origem.
  - `GET /registros/{id}` devolve `{id, formulario_id, versao_id, dados, criado_em, atualizado_em}`; com o `versao_id` o front busca a definição certa.
  - `DELETE /registros/{id}` apaga de verdade (uso local, sem auditoria), exceto se outro registro o referencia (§2.7).
  - O cliente manda **só campos de entrada**. Chave de campo calculado ou inexistente → 422 indicando o campo (aceitar e ignorar esconderia bug no front). Erro de validação (obrigatório vazio, opção inválida, tipo errado) → 422 com a lista por `id`; erro de **cálculo** nunca bloqueia (§7).
- Listar registros com colunas derivadas da definição, filtro simples e **exportação CSV**.
  - `GET /formularios/{id}/registros` lista os registros de **uma versão** (parâmetro `versao_id`, padrão a última publicada); as colunas vêm dessa definição, sem campos `secao`. Paginação com `limite` (padrão 50, máximo 200) e `deslocamento`; resposta `{"itens": [...], "total": N}`.
  - Filtro: só **igualdade** em campos `selecao`, `sim_nao`, `texto` e `calculado` booleano, mais `criado_de` e `criado_ate`. Número e data ficam para "próximos passos" (número é guardado como string, então `"25.5"` e `"25.50"` exigiriam comparação numérica). O nome do campo é validado contra a definição (allowlist) antes de entrar na consulta, e o valor vai sempre parametrizado.
  - `GET /formularios/{id}/registros/exportar`: mesma versão e mesmos filtros da listagem. Cabeçalho `rotulo (unidade)`; números arredondados por `casas_decimais` (§7). Formato para abrir no Excel em português: UTF-8 com BOM, separador `;`, vírgula decimal. Campo calculado com erro sai como `ERRO: <mensagem>`; vazio sai vazio.

### 2.4. Interfaces

- **API** (FastAPI) e **CLI enxuta** (importar template, criar registro a partir de JSON, listar e exportar) chamam as **mesmas funções** de `servico.py`, que não sabe quem as chama.
- A API é consumida pelo **frontend deste mesmo repositório** (`frontend/`); o contrato é o **OpenAPI** gerado pelo FastAPI (§5.3).
- **Frontend** (`frontend/`): construtor de formulários com arrastar e soltar, renderizador de formulário (`FormRenderer`), telas de preenchimento, listagem e consulta, exportação. É só apresentação: **não reimplementa** o avaliador de fórmulas nem a validação (usa `/definicoes/validar`, `/definicoes/previa` e os erros da API). Textos em PT-BR.

### 2.5. Módulos de IA (opcionais — só depois do núcleo estar pronto e testado)

- **Assistente de procedimentos (RAG):** procedimentos em `.md` (escritos pelo autor, genéricos ou sintéticos), busca com **BM25 escrito à mão**, resposta do LLM **somente com os trechos recuperados**, exibindo trecho e arquivo de origem. Sem base nos documentos → responde "não encontrei". Sem internet ou chave de API → mostra só os trechos (fallback).
- **Busca semântica (opcional dentro do RAG):** o BM25 à mão continua como base e como fallback. Se houver provedor de embeddings (chamado só via `ia/cliente.py`), os vetores ficam numa tabela do SQLite (BLOB) e são comparados por similaridade de cosseno em Python, sem extensão de banco: com algumas centenas de trechos isso é instantâneo. Sem internet ou chave, vale só o BM25.
- **Resumo de registros por IA:** o LLM redige a partir dos dados e de agregados **calculados pelo código** (contagem, média etc.), em saída estruturada (JSON). O código confere se **todos os números do texto batem com o banco**; se não baterem, o resumo é rejeitado.
- **Gerador de formulário por IA:** a pessoa descreve em texto o que quer e o LLM propõe **um ou mais formulários** (cada um uma **definição JSON**, ligados entre si quando o pedido pedir); a pessoa revisa, ajusta e **aprova** no construtor. O LLM só redige a definição (inclusive o texto das fórmulas): quem valida é o código (`validar_definicao`, §2.2), e nenhum valor de negócio sai do LLM.
  - Saída do LLM é **dado não confiável**: vira JSON no esquema da definição e passa pela mesma validação da publicação. Se houver erros, eles voltam ao LLM para correção, no máximo 2 vezes; persistindo, a proposta segue para o construtor **com a lista de erros**, para a pessoa corrigir.
  - O prompt é montado com o catálogo (tipos de campo, funções, `pi`, nomes reservados), gerado das mesmas tabelas do `GET /catalogo`, e com os **formulários existentes**: para cada um, o `nome` e os campos que ele **compartilha** (`id`, rótulo, tipo), vindos da versão atual. Com isso a IA cria **correlações** (§2.7): campos `referencia` apontando para um formulário existente **ou para outro formulário proposto no mesmo pedido** (`formulario` = nome), e fórmulas que usam `<referência>__<campo compartilhado>`. Ex.: "crie ensaio, proctor e insitu, cada um dependendo do anterior" gera os três, com os campos `compartilhado` onde a origem libera. A validação (§2.7) barra origem inexistente, campo não compartilhado e ciclo, **tratando o conjunto proposto como se já estivesse publicado**. A IA **nunca altera um formulário já publicado**; se precisar de um campo que uma origem existente não compartilha, o erro de validação aparece e a pessoa decide ajustar essa origem no construtor. Nenhum registro nem dado do banco é enviado ao LLM, só o texto do pedido, os metadados acima e, ao refinar, os rascunhos em edição.
  - **Nunca salva.** `POST /definicoes/gerar` recebe `{pedido, rascunhos?}` (`rascunhos` = `[{nome, definicao}]` em edição, para refinar: "adicione um campo X") e devolve `{formularios: [{nome, definicao, erros}]}` sem criar nada. A pessoa pode editar, remover ou renomear cada rascunho e então aprova o conjunto, que é publicado **de uma vez** por `POST /formularios/lote` (§2.2).
  - Sem chave ou sem internet: o recurso fica indisponível, com mensagem clara em PT-BR; o construtor manual continua funcionando. O endpoint só é montado quando o módulo `ia/` existe.
  - Resumo e assistente na API: `POST /formularios/{id}/resumo` (mesma versão e filtros da listagem; o código calcula os agregados e o resumo é descartado, com 502, se algum número não bater) e `POST /assistente/perguntar` (`{pergunta}`; devolve `{encontrou, texto, usou_ia, trechos}`; sem IA devolve só os trechos). `IaIndisponivel` vira 503 e resposta da IA fora do formato, 502, ambos no erro uniforme em PT-BR.
  - No front: ação "Criar com IA" no construtor (campo de pedido, lista de formulários propostos com os erros de cada um, edição livre de cada rascunho no editor, "Publicar todos").

### 2.6. Entregáveis de documentação

- `README.md` (inclui "próximos passos").
- `AI_NOTES.md`: registro de **erros reais da IA** durante a construção (ver §10).

### 2.7. Relação entre formulários (parte do núcleo)

Um formulário pode depender de outro. Exemplo: `proctor` depende de `ensaio`, e `insitu` depende de `proctor`; cada formulário de origem decide quais campos libera.

- **Muitos para um, por registro:** um registro de `proctor` aponta para **um** registro de `ensaio`; vários proctors podem apontar para o mesmo ensaio.
- **Definição:** a origem marca `"compartilhado": true` nos campos que libera (qualquer tipo, exceto `secao` e `referencia`). O dependente declara um campo `{"id": "ensaio", "tipo": "referencia", "formulario": "ensaio", "rotulo": "Ensaio", "obrigatorio": true}`. `formulario` é o **nome** do formulário de origem (não o `id`, que só existe depois de criado e quebraria templates importáveis). O valor desse campo no registro é o `id` do registro de origem.
- **Fórmulas:** os campos compartilhados aparecem como `<id da referência>__<id compartilhado>` (ex.: `ensaio__umidade`), somente leitura, com o mesmo tipo do campo de origem (`calculado` usa o tipo inferido). É um nome simples, então a allowlist continua sem atributos nem subscripts (§7). Só `numero`, `data`, `sim_nao` e `calculado` desses tipos são usáveis em fórmulas.
- **Referência vazia** (campo não obrigatório sem valor) deixa seus campos compartilhados vazios, e vazio propaga (§7). Campo compartilhado com erro na origem propaga o erro, citando o campo de origem.
- **Ao publicar, rejeitar** (422, erro localizado): `formulario` inexistente (nenhum formulário com esse nome); fórmula que usa campo que a origem não compartilha; **ciclo entre formulários** (inclui auto-referência), citando os formulários envolvidos.
- **Ao salvar registro:** a referência exige o `id` de um registro existente do formulário apontado (de qualquer versão dele), senão 422 no campo. Campo compartilhado que o registro de origem não tem (versão antiga dele) conta como vazio.
- **Contrato dos campos compartilhados:** enquanto houver dependentes, uma nova versão da origem que remova um campo compartilhado, deixe de compartilhá-lo ou mude seu tipo (inclusive o tipo inferido de um `calculado`) é rejeitada com 422. Campo novo ou não compartilhado: livre.
- **Cascata:** ao atualizar um registro de origem (criar não tem dependentes, e excluir é bloqueado se houver), os registros dependentes (transitivamente) são recalculados **na mesma transação**, cada um contra a sua própria versão. Falha de cálculo no dependente vira erro no campo e nunca bloqueia nem reverte a edição da origem.
- **Exclusão:** `DELETE /formularios/{id}` só se nenhum outro formulário depende dele (em qualquer versão) **e** ele não tem registros; senão 409. `DELETE /registros/{id}` só se nenhum outro registro o referencia; senão 409. Excluir um formulário apaga também suas versões (só é possível sem registros).
- Na listagem e no CSV, o campo `referencia` aparece como o `id` do registro apontado.

### 2.8. Campos de localização e foto

- **`localizacao`:** guarda um ponto como `{"latitude": "-23.550520", "longitude": "-46.633308"}` (strings, no mesmo espírito do `Decimal`, §7). Valida a faixa (latitude de −90 a 90, longitude de −180 a 180); um dos dois sem o outro é erro, e `obrigatorio` vale para o par. Fica no JSON do registro, sem extensão espacial. Não pode ser usado em fórmulas. No CSV sai como `lat / lon` (ex.: `-23,550520 / -46,633308`).
- **`foto`:** um campo guarda uma ou mais fotos; `maximo` opcional (inteiro `>= 1`). O envio é em duas etapas, porque o registro pode ainda não existir:
  - `POST /anexos` (multipart, campo `arquivo`) processa a imagem e devolve `{id, largura, altura, tamanho_bytes}`; o registro guarda a lista de `id`s no campo.
  - `GET /anexos/{id}` devolve o WebP (`image/webp`).
  - Ao salvar o registro, cada `id` precisa existir e não estar vinculado a outro registro ou campo, senão 422 no campo. Anexos retirados do campo, ou de um registro excluído, são apagados (o arquivo só depois do commit). Anexos nunca vinculados há mais de 24 h são removidos na inicialização do app.
  - Na listagem o campo vem como lista de `id`s; no CSV, como a quantidade de fotos.
- **Processamento (`fotos.py`, função pura de bytes para bytes):**
  - Só entram JPEG, PNG e WebP (HEIC não é suportado, com mensagem clara em PT-BR), até 20 MB e com limite de pixels (proteção contra bomba de descompressão).
  - Aplica a orientação EXIF, **remove todos os metadados** (o EXIF traz a localização exata) e converte para **WebP** em RGB.
  - Meta de **50 a 80 KB por foto** (1 KB = 1024 bytes): lado maior inicial de 1280 px (nunca amplia), qualidade começando em 80 e descendo de 5 em 5 até 40; se ainda passar de 80 KB, reduz as dimensões em 15% e repete, com piso de 480 px no lado maior. Se mesmo no piso passar, guarda o menor resultado obtido. Foto que já fica abaixo de 50 KB com qualidade 80 não é piorada nem ampliada: o teto de 80 KB é o que o algoritmo persegue, e 50 KB é só o alvo típico.
  - Só o WebP processado é guardado; **o original é descartado** e não dá para recuperá-lo. Os parâmetros são constantes nomeadas no módulo.
- **Testes de `fotos.py`** com imagens geradas no próprio teste (ruído, gradiente, retrato com EXIF de rotação, PNG com transparência, arquivo corrompido): conferem a faixa de tamanho, as dimensões, a ausência de EXIF e a rejeição de formato inválido.

### 2.9. App instalável

O produto final é um **aplicativo instalável** de uso local: janela Electron com o frontend, backend Python embutido como processo filho e SQLite. Detalhes técnicos em §4.1.

- Alvos: **Windows, macOS e Linux**.
- Fora do escopo: assinatura de código e notarização (por isso o macOS e o Windows mostram um aviso na primeira abertura), loja de apps e atualização automática (próximos passos).

---

## 3. Escopo — o que NÃO será feito

Estas exclusões são **deliberadas**. Não implemente, não "adiante" e não sugira como parte de uma tarefa comum. Se uma tarefa parecer exigir algo daqui, pare e pergunte.

### 3.1. Funcionalidades fora do escopo (vão para "próximos passos" no README)

- Grupo repetível (tabela de linhas) e visibilidade condicional. Consulta espacial (distância, raio) e mapas sobre `localizacao`.
- Relação um-para-muitos **dentro de um mesmo registro** (ex.: lote com vários corpos de prova como linhas). A relação *entre formulários*, por referência a um registro, está no escopo (§2.7).
- Usuários, login, cargos e permissões. O uso é local; a API ouve **só em `127.0.0.1`**.
- Modo offline e sincronização; mapas.
- Código de interface fora de `frontend/` e `desktop/`. O `dist/` gerado e os binários do instalável não são versionados. Para testar a API sem subir o front, use Swagger (`/docs`), `curl` ou `TestClient`.
- Deploy, hospedagem e infraestrutura (CI além de lint e testes), assinatura/notarização do instalável, loja de apps e atualização automática. Gerar o instalável (§4.1) está no escopo.
- `Dockerfile` e `docker-compose`: avaliado e **adiado**. SQLite local + `uv` já dão ambiente reproduzível. Só reconsiderar se alguém sem Python precisar subir a API ou se houver deploy; nesse caso é um `Dockerfile` mínimo, discutido antes.

### 3.2. Tecnologias proibidas

LangChain, LlamaIndex, bancos vetoriais (inclui pgvector e extensões como `sqlite-vec`), **ORM** (use `sqlite3` direto), Docker, Postgres/PostGIS (o app instalável usa SQLite, §4.1), bibliotecas de autenticação. **Nova dependência exige justificativa** — o autor precisa conseguir defender cada uma.

### 3.3. Proibições de comportamento

- ❌ **Nunca `eval`, `exec`, `compile` ou `__import__`** para fórmulas. Só o avaliador sobre `ast` com lista de permissão. Nó de AST fora da lista → erro explícito, nunca ignorado.
- ❌ **Nunca pedir ao LLM para calcular, converter unidade, somar ou conferir número.** O LLM só redige texto sobre dados já calculados.
- ❌ Não confiar no frontend: validação e recálculo são do servidor, sempre.
- ❌ Não colocar regra de negócio em `api.py` nem em `cli.py`; ela fica em `servico.py` e abaixo.
- ❌ Não fazer mudança incompatível no contrato (OpenAPI ou formato do JSON de definição) sem sinalizar explicitamente, porque o `frontend/` quebra (§5.3).
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
| Fotos | `Pillow` (decodificar, converter para WebP, remover EXIF) e `python-multipart` (upload no FastAPI) |
| Frontend (`frontend/`) | React, TypeScript (`strict`), Vite, Tailwind CSS; gerenciador de pacotes `npm` |
| Desktop (`desktop/`) | Electron (janela e processo filho do backend), `electron-builder` (instalador) |
| Backend no instalável | `PyInstaller` (executável), `platformdirs` (pasta de dados) |
| Qualidade do front | Vitest + Testing Library, ESLint, Prettier |
| Qualidade | `pytest`, `httpx` (TestClient), `ruff`, GitHub Actions |

**Execução local:** `uv run uvicorn forms.api:app --host 127.0.0.1 --port 8000` (a CLI roda por `uv run`). Sem Docker (§3.1).
**Frontend em dev:** `frontend/` roda na porta 5173 (`npm run dev`, Vite) e chama esta API em `http://127.0.0.1:8000`. Como são origens diferentes, a API habilita **CORS apenas para `http://localhost:5173` e `http://127.0.0.1:5173`** (configurável por variável de ambiente); nunca `*`.

### 4.1. App instalável (empacotamento)

- O instalado tem dois processos: o **Electron** (`desktop/`), que abre a janela e gerencia o processo filho, e o **backend Python** (`app.py`, empacotado com PyInstaller), que sobe o FastAPI em `127.0.0.1` numa **porta livre** e **serve o build estático do front** (`frontend/dist`, copiado ao empacotar) na mesma origem, então no instalado não há CORS. O backend escolhe a porta e a imprime como primeira linha da saída (JSON `{"porta": N}`); o Electron a lê, abre a janela em `http://127.0.0.1:<porta>` e encerra o backend ao fechar. Se o backend cair, o Electron mostra um erro claro em PT-BR em vez de uma janela em branco.
- Os dados do usuário (banco SQLite e pasta de fotos) ficam na pasta de dados do sistema, via `platformdirs`, nunca dentro do pacote do app. Backup = copiar essa pasta.
- **Token por execução:** um token é gerado a cada início do app e a API o exige no cabeçalho `X-Forms-Token`; outro programa ou página da máquina não chama a API sem ele. O Electron gera o token, passa ao backend por variável de ambiente e o expõe ao front pelo *preload* (`contextBridge`). Em dev (navegador + Vite) ele é dispensado por variável de ambiente.
- Empacotamento em três passos, com scripts em `empacotamento/`: (1) `npm run build` do front; (2) **PyInstaller** gera o executável do backend; (3) **electron-builder** monta o instalador com o executável do backend (que já leva o `dist` do front dentro, porque é o backend que o serve) (macOS: `.dmg`; Windows: instalador NSIS; Linux: AppImage). O PyInstaller **não faz compilação cruzada**: cada instalador é gerado no próprio sistema, então o build do instalável roda numa matriz de CI com os três. O `dist/` e os binários gerados **não são versionados**.
- **Portabilidade:** caminhos sempre com `pathlib`, nunca texto concatenado; `anexos.caminho` é guardado com `/` (relativo à pasta de dados) em qualquer sistema; a pasta de dados vem de `platformdirs`. Nenhum código assume `\n` ou `/` do sistema.
- **Exportar CSV** usa o download padrão do Electron, que abre o diálogo nativo de salvar. Captura direta pela câmera fica fora por ora; o envio de foto usa o seletor de arquivo.
- **Segurança do Electron:** `contextIsolation` ligado, `nodeIntegration` desligado, sem `remote`; a janela só navega para `http://127.0.0.1:<porta>` e bloqueia qualquer outra URL; o *preload* expõe só o mínimo (o token).
- O banco do usuário persiste entre versões do app, então migração de esquema é crítica (§5.2).
- Dependências do instalável e por quê: `PyInstaller` (gerar o executável do backend), `platformdirs` (pasta de dados correta por sistema), `Electron` e `electron-builder` (janela e instalador), `Pillow` e `python-multipart` (§2.8). Alvos: Windows, macOS e Linux (§2.9).

---

## 5. Arquitetura

```
src/forms/   models.py  tipos_campo.py  formulas.py  validacao.py
             fotos.py  exportacao.py  repositorio.py  cli.py  app.py
             api.py  api_esquemas.py  api_rotas.py  api_extensoes.py  exportar_openapi.py
             servico.py (fachada)  servico_base.py  servico_registros.py
             servico_anexos.py  servico_consulta.py  servico_pastas.py
             rag/  chunker.py  indice.py  semantico.py  responder.py  extensao.py  (opcional)
             ia/   cliente.py  resumo.py  validacao.py  gerador.py  extensao.py     (opcional)
templates/   corpo_de_prova.json  inspecao_obra.json  (exemplos)
docs/        procedimentos em .md (base do assistente)
frontend/    React + TypeScript + Vite + Tailwind (§4)
desktop/     Electron: processo principal, preload, configuração do instalador
empacotamento/  scripts do instalável (build do front, PyInstaller, electron-builder)
tests/       test_formulas.py  test_validacao.py  test_servico.py  test_api.py ...
```

**Resumos de pasta:** cada pasta com código tem um `README.md` curto (o que é, o que tem, como se conecta, como testar), mantido pelo `doc-writer`. `src/forms/` tem um só, com uma seção por módulo. O resumo descreve o que **existe** no código; as regras e o alvo continuam aqui. A pasta `docs/` é reservada à base do RAG e não recebe esses resumos.

### 5.1. Camadas e direção de dependência

```
api.py / cli.py  →  servico.py  →  validacao.py, formulas.py, tipos_campo.py, fotos.py
                                →  repositorio.py  →  sqlite3
```

- **`models.py`**: `dataclasses` do domínio. Sem Pydantic, sem I/O.
- **`tipos_campo.py`**: o que cada tipo aceita, valida e normaliza.
- **`formulas.py`**: parse, grafo de dependências, detecção de ciclo e avaliação. Funções puras, sem I/O.
- **`validacao.py`**: valida um registro contra uma definição.
- **`fotos.py`**: processa uma imagem (valida, orienta, remove metadados, converte para WebP na faixa de tamanho, §2.8). Função pura de bytes para bytes. O I/O de arquivo (gravar e apagar o `.webp`) fica em `servico_anexos.py` (reexportado por `servico.py`), com a pasta de dados recebida por parâmetro.
- **`repositorio.py`**: único módulo que fala SQL. Sempre com parâmetros (`?`), nunca f-string em SQL.
- **`servico.py`**: casos de uso (importar template, publicar versão, validar definição, prévia de fórmulas, catálogo, criar/atualizar registro, listar, exportar). Ponto de entrada comum de API e CLI. Para não virar um arquivo gigante, os casos de uso de registros (`servico_registros.py`), anexos (`servico_anexos.py`) e consulta/exportação (`servico_consulta.py`) e pastas (`servico_pastas.py`) moram em módulos próprios, e as peças comuns (transação, campos compartilhados) em `servico_base.py`; `servico.py` os reexporta, então API e CLI chamam tudo por `servico.<função>`.
- **`exportacao.py`**: formatação das células e geração do CSV (§2.3, §12). Funções puras, sem I/O; usada por `servico_consulta.py`.
- **`api.py`**: Pydantic e HTTP só aqui; traduz erros de domínio em respostas HTTP. Fica dividida em `api.py` (app, token por execução, CORS, tratadores de erro), `api_esquemas.py` (modelos Pydantic de entrada e saída) e `api_rotas.py` (endpoints); `api_extensoes.py` descobre e monta as rotas dos módulos opcionais; `exportar_openapi.py` gera o `openapi.json` do front.
- **`cli.py`**: `argparse` fino; só chama `servico.py`.
- **`app.py`**: entrada do backend no app instalável (§4.1): sobe a API, serve o build do front e imprime a porta. Não abre janela (isso é do Electron). Só monta as peças, sem regra de negócio.
- Dependências apontam **para baixo**: o núcleo nunca importa `api`, `cli`, `rag` ou `ia`.
- **Módulos opcionais** (`rag/`, `ia/`) dependem do núcleo, nunca o contrário; o app inteiro funciona com eles removidos. Cada um publica um `EXTENSAO` em `extensao.py` (rotas e tratadores de erro), e o núcleo o procura **pelo nome** em execução (`descobrir_extensoes()`), sem importá-lo; só a ausência do próprio módulo é tolerada. Como o PyInstaller não vê imports por nome, `empacotamento/` os declara com `--hidden-import`.

### 5.2. Modelo de dados (SQLite)

```
formularios          id, nome (único), criado_em
versoes_formulario   id, formulario_id, numero, definicao (JSON), publicada_em
registros            id, formulario_id, versao_id, dados (JSON), criado_em, atualizado_em
dependencias_formulario  formulario_id, depende_de_id
referencias_registro     registro_id, campo_id, destino_id
anexos               id, registro_id (nulo até vincular), campo_id, caminho, largura, altura, tamanho_bytes, criado_em
```

- `anexos` guarda os metadados das fotos; o arquivo `.webp` fica na pasta de dados e `caminho` é relativo a ela (§2.8).

- `dependencias_formulario` é preenchida ao publicar e o vínculo permanece enquanto o formulário existir (versões antigas e seus registros ainda apontam). `referencias_registro` é mantida ao salvar o registro. As duas existem para bloquear exclusões e achar dependentes na cascata sem varrer colunas JSON (§2.7).

- Todo registro aponta para a `versao_id` com que nasceu. Editar o registro **não muda a versão**: ele é validado e recalculado contra a versão de origem. Migrar registro para versão nova está fora do escopo (próximos passos).
- Esquema criado/migrado por código simples em `repositorio.py` (sem ferramenta de migração), versionado com `PRAGMA user_version`. Como o banco do usuário persiste entre versões do app, toda mudança de esquema exige teste de atualização a partir do esquema anterior.

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
    {"id": "resistencia_mpa", "tipo": "calculado", "rotulo": "Resistência", "unidade": "MPa", "casas_decimais": 1,
     "formula": "carga_kn * 1000 / (pi * (diametro_mm / 2) ** 2)"},
    {"id": "conforme", "tipo": "calculado", "rotulo": "Conforme?",
     "formula": "resistencia_mpa >= fck_mpa"}
  ]
}
```

Valores de `tipo`: `texto`, `numero`, `data`, `selecao`, `sim_nao`, `calculado`, `secao`, `referencia`, `localizacao`, `foto`. Campo `foto` aceita `"maximo"` opcional (§2.8). Campo `referencia` exige `"formulario"` (nome do formulário de origem); qualquer campo (exceto `secao` e `referencia`) aceita `"compartilhado": true` (§2.7). Campo `selecao` exige `"opcoes"`: lista não vazia de strings, sem duplicatas (ex.: `"opcoes": ["Aprovado", "Reprovado"]`).

### 5.3. Contrato com o frontend (`frontend/`, mesmo repositório)

- O frontend está no mesmo repositório, mas o **backend é a fonte da verdade** de dados, validação, cálculo e do esquema da definição de formulário.
- O contrato tem duas partes: o **OpenAPI** do FastAPI (`/openapi.json`, `/docs`) e o **formato do JSON de definição** (§6). Modelos Pydantic da API têm nomes e campos estáveis e `response_model` explícito em todo endpoint.
- Mudança **compatível** (campo opcional novo, endpoint novo): livre. Mudança **incompatível** (renomear/remover campo, mudar tipo, mudar semântica): só com aviso explícito na tarefa/PR, descrevendo o impacto no front; o ajuste do `frontend/` entra no mesmo PR. Os tipos TypeScript da API são **gerados do OpenAPI** (`openapi-typescript`), nunca escritos à mão, e o CI falha se o arquivo gerado estiver desatualizado.
- Erros da API têm formato uniforme (`{"detalhe": "...", "erros": [{"campo": "...", "mensagem": "..."}]}`) com mensagens em PT-BR, para o front exibir no campo certo. Erro de validação de registro → 422; recurso inexistente → 404; definição inválida ao publicar → 422; exclusão bloqueada por vínculo (§2.7) → 409.
- **Localização de erro de definição:** `campo` usa o **id do campo** (`resistencia_mpa.formula`), nunca o índice, porque o índice muda quando o usuário reordena campos no editor e o id não. Exceção: quando o problema é o próprio id (ausente, duplicado ou reservado), usa o índice (`campos[3].id`), já que não há id confiável; erro global (ex.: definição sem a chave `campos`) usa `campos`. Erro de fórmula pode trazer `posicao` opcional (`{"inicio": 12, "fim": 20}`, offsets do `ast` no texto da fórmula) para o front sublinhar o trecho. Ciclo cita os campos envolvidos.
- Endpoints não dependem de estado de sessão nem de cookie. Sem login de usuário nesta fase; no app instalado a API exige o token por execução no cabeçalho `X-Forms-Token` (§4.1), e o front precisa enviá-lo.
- Texto livre ou número vindo do front nunca é confiável (§3.3).
- **Valores numéricos trafegam como string** nas respostas, para não perder precisão no front; a entrada aceita número ou string (§7). Campos calculados vêm como `{"valor", "erro"}` (§7).
- `POST /definicoes/validar` não é uma resposta de erro: devolve 200 com `{"valida", "erros"}` (§2.2), então não segue o formato `{"detalhe", "erros"}` acima, mas cada item de `erros` usa o mesmo `{"campo", "mensagem"}`.

---

## 6. Idiomas

| Onde | Idioma |
|---|---|
| **Vocabulário de domínio** (`formulario`, `registro`, `versao`, `rotulo`, `obrigatorio`, módulos `servico.py`, `tipos_campo.py`…, tabelas, chaves do JSON de definição e campos da API) | **Português** (sem acentos em identificadores) |
| **Termos técnicos/infra** (`handler`, `middleware`, `router`, `fixture`) | **Inglês** quando já são o nome padrão da técnica |
| **Código do front** (`frontend/`, `desktop/`) | Identificadores de domínio em português (`Formulario`, `registro`, `rotulo`); termos técnicos em inglês (`component`, `hook`, `props`) |
| **Textos visíveis ao usuário**, mensagens de erro e de validação | **Português brasileiro** |
| **Comentários, README, `AI_NOTES.md`, este arquivo, PRs** | **Português brasileiro** |
| **Mensagens de commit** | **Inglês** (Conventional Commits) |

Regra de ouro: **o JSON de definição e o OpenAPI são contratos** com o `frontend/` (`campos`, `id`, `tipo`, `rotulo`, `unidade`, `casas_decimais`, `opcoes`, `compartilhado`, `formulario`, `maximo`, `obrigatorio`, `formula`). Não traduza nem renomeie por conveniência de um lado só (ver §5.3).

---

## 7. Fórmulas — regras de segurança e comportamento

O avaliador é a peça mais importante e mais testada do projeto.

- Parse com `ast.parse(..., mode="eval")`; percorrer a árvore com **allowlist explícita** de nós (constantes numéricas/booleanas, nomes de campo, operadores aritméticos e de comparação, `and`/`or`/`not`, chamadas às funções permitidas).
- Funções permitidas: `se`, `min`, `max`, `media`, `soma`, `dias`, mais a **constante** `pi` (sem parênteses, como no exemplo da §5.2). Qualquer outra → erro claro.
- **Nomes reservados:** o `id` de um campo não pode ser `pi`, `se`, `min`, `max`, `media`, `soma` nem `dias`, e não pode conter `__` (reservado aos campos compartilhados via referência, §2.7); a publicação rejeita com mensagem clara.
- **Vazio propaga:** se qualquer operando é vazio (operadores, comparações, `and`/`or`/`not` e argumentos de função), o resultado é vazio. Vale também para `soma`, `media`, `min` e `max`: nada é ignorado em silêncio (média parcial poderia gerar um "conforme" falso). Ignorar vazios, se um dia for preciso, seria função nova, sem mudar as existentes.
- **Contrato das funções:** `soma`, `media`, `min` e `max` aceitam 1 ou mais números. `se(cond, a, b)` exige `cond` booleano (número é erro), devolve vazio se `cond` é vazia e **avalia só o ramo escolhido**, para que `se(d == 0, 0, x / d)` não erre por divisão por zero. `dias(n)` exige `n` inteiro e só faz sentido em `data ± dias(n)`: constante não inteira é rejeitada ao publicar; valor vindo de campo é checado na execução.
- Proibido: atributos (`a.b`), subscripts, lambdas, comprehensions, f-strings, imports, chamadas a nomes não listados.
- Nome desconhecido na fórmula (campo inexistente) → rejeitado **ao publicar**, não ao preencher.
- Grafo de dependências → ordem topológica; **ciclo rejeitado ao publicar** com mensagem que cita os campos do ciclo.
- Erro de execução (divisão por zero, `dias` com valor não inteiro vindo de um campo) → o campo guarda o erro; o registro continua válido e salvo (formato abaixo).
- Aritmética sobre números: **`Decimal`** (decidido), nunca `float`. Todo campo `numero` é normalizado para `Decimal` em `tipos_campo.py`, para que as fórmulas nunca misturem tipos. Testar arredondamento do template de corpo de prova.
- **Número no JSON (fronteira):** na entrada a API aceita número JSON ou string e converte direto para `Decimal` (`Decimal(str(valor))`, nunca via `float`). Na saída da API e na coluna `dados` do SQLite, número vai **sempre como string** (`"25.50"`), porque número JSON vira `float` no JavaScript e perderia a precisão. Datas em ISO (`"2026-11-01"`). Contrato com o front (§5.3).
- **Casas decimais:** `casas_decimais` é opcional na definição do campo e orienta **só a exibição** (o front arredonda) e a **exportação CSV**, que sai arredondada com ele (campo sem `casas_decimais` sai com o valor completo). O `valor` guardado e devolvido mantém a precisão total, e as fórmulas sempre calculam sobre ela, nunca sobre o valor arredondado. Aceito em campos `numero` e em `calculado` cujo tipo inferido é numero; deve ser inteiro `>= 0`. Em outro tipo, ou com valor inválido, a publicação rejeita com mensagem clara.
- **Tipos na fórmula (checados ao publicar):** o avaliador infere o tipo de cada expressão sem executá-la. Tipos: `numero`, `data`, `booleano` e `duracao` (resultado de `dias(n)`). Campo `numero` → numero; `data` → data; `sim_nao` → booleano; `calculado` → tipo inferido da própria fórmula. Combinações aceitas:
  - `numero` com `+ - * / **` → numero; `soma`, `media`, `min` e `max` só sobre numero → numero.
  - `data + duracao` e `data - duracao` → data; `data - data` → numero (dias, `Decimal`).
  - `== != < <= > >=` entre dois numero ou duas data → booleano; entre dois booleano só `==` e `!=`.
  - `and`, `or` e `not` só sobre booleano.
  - `se(cond, a, b)`: `cond` booleano, `a` e `b` do mesmo tipo, resultado nesse tipo.
  - `dias(n)`: `n` numero → duracao.
  Qualquer outra combinação (`data * 2`, `data + data`, `data >= 3`, `duracao` como resultado final do campo) é **rejeitada ao publicar**, com mensagem e `posicao` na fórmula. Campos `texto`, `selecao`, `secao`, `localizacao` e `foto` não podem ser referenciados em fórmulas (a allowlist não tem constante de texto); reavaliar se surgir a necessidade.
- **Formato do campo calculado no registro:** todo campo `calculado` é sempre `{"valor": ..., "erro": ...}`; campos de entrada continuam valor simples. Entrada vazia → `{"valor": null, "erro": null}` (ainda não dá para calcular); falha de execução → `{"valor": null, "erro": "mensagem em PT-BR"}`. Fórmula que depende de campo calculado com erro também fica com erro, citando o campo de origem. Este formato é contrato com o front (§5.3).
- Cobrir com testes: caminho feliz, cada operador, cada função, entradas vazias, divisão por zero, nó proibido, tentativa de injeção (`__import__('os')`, `().__class__`…), ciclo, dependência inexistente, cada combinação de tipos aceita e rejeitada (incluindo comparação entre datas), campo compartilhado vazio ou com erro na origem, ciclo entre formulários, cascata de recálculo.

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
- **Frontend:** Vitest + Testing Library para a lógica e os componentes (montagem da definição no construtor, `FormRenderer`, exibição de erros por campo). TDD vale para a lógica; tela puramente visual dispensa teste de snapshot. Como o front não tem regra de negócio, não há teste dela lá. Verificação manual: `npm run dev` com a API no ar, golden path + 1 caso de borda.
- **Desktop:** o instalável é verificado manualmente (instalar, abrir, criar um registro, fechar e reabrir) antes de dar a tarefa por pronta.

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
12. **Frontend:** TypeScript em modo `strict`, sem `any` nem `@ts-ignore` sem motivo comentado; componentes pequenos; estado do servidor vem da API, nunca duplicando regra de negócio; biblioteca nova só com justificativa (ex.: a de arrastar e soltar, quando entrar).

---

## 10. Trabalhando com IA neste repositório

- **Toda tarefa começa pelo orquestrador** (`agents/orchestrator.md`): ele faz a triagem, confere o escopo e decide quais agentes chamar e em que ordem. Os demais agentes (`issue-creator`, `issue-planner`, `issue-coder`, `issue-reviewer`, `doc-writer`, `git-manager`) são chamados por ele, e não diretamente, salvo pedido explícito do autor.
- Ao cometer ou corrigir um **erro real de IA** (lógica errada, API inventada, teste que passa por motivo errado, número alucinado), acrescente uma entrada em `AI_NOTES.md`: o que foi pedido, o que a IA fez de errado, como foi detectado e a correção. Seja honesto: o arquivo é parte da defesa do projeto.
- Não "melhore" o núcleo além da tarefa pedida. Mudanças em `formulas.py` e `validacao.py` precisam de teste novo que as justifique.
- Quando houver dúvida sobre escopo, consulte §2 e §3 e **pergunte** em vez de adivinhar.

---

## 11. Linha de corte

Se o tempo apertar, corte **nesta ordem**:

1. Resumo por IA
2. Gerador de formulário por IA
3. Assistente RAG
4. CLI além de importar e listar
5. Exportação CSV
6. Endpoint de prévia de fórmulas (o front ainda calcula só ao salvar)

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
- Exportação CSV: neutralizar células **de texto** iniciadas por `=`, `+`, `-`, `@`, tab ou `CR` (injeção de fórmula em planilha), prefixando com `'`. Não vale para números: um `Decimal` negativo (`-3,5`) começa com `-` e não pode ser corrompido, e número só entra no CSV via formatação de `Decimal`.
- Upload de foto: tamanho e número de pixels limitados antes de decodificar; só JPEG, PNG e WebP, reconhecidos pelo conteúdo e não pela extensão; metadados (EXIF) removidos; arquivo gravado com nome gerado (UUID), nunca com o nome enviado (sem path traversal).
- No app instalado a API exige o token por execução (§4.1), além de ouvir só em `127.0.0.1`. O Electron segue as regras de segurança do §4.1 (`contextIsolation`, sem `nodeIntegration`).

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
- [ ] Lint e formatação (`uv run ruff check .` e `uv run ruff format .`). Atenção: o `ruff format` também formata blocos de Python dentro de arquivos `.md`
- [ ] CI verde no PR (`.github/workflows/ci.yml` roda `uv sync --locked`, ruff check, ruff format --check e pytest, o pytest numa matriz com Windows, macOS e Linux; o job do `frontend/` roda `npm ci`, lint, typecheck, testes e build). Se mudar dependência, commite `pyproject.toml` e `uv.lock` juntos
- [ ] **Testado manualmente** quando mexer em API/CLI: golden path + 1 caso de borda via `/docs` ou `curl` (testes não substituem ver funcionando)
- [ ] Contrato (OpenAPI / JSON de definição) inalterado ou mudança incompatível sinalizada (§5.3)
- [ ] Mudou o esquema do banco? Teste de atualização a partir do esquema anterior (§5.2)
- [ ] Nenhum `eval`/`exec`, nenhum SQL por concatenação, nenhum segredo no diff
- [ ] Sem `print` de depuração, `Any` injustificado ou TODO sem explicação
- [ ] Nada fora do escopo da §2 foi adicionado; nada da §3 foi violado
- [ ] `AI_NOTES.md` atualizado se houve erro real de IA
- [ ] Este arquivo e o README atualizados se estrutura, comandos ou escopo mudaram
- [ ] `README.md` das pastas afetadas atualizado se um módulo mudou de responsabilidade, dependências, contrato ou arquivos (§5)

---

## 15. Referências rápidas

- Python `ast`: https://docs.python.org/3/library/ast.html
- FastAPI: https://fastapi.tiangolo.com
- `uv`: https://docs.astral.sh/uv
- Frontend e desktop: `frontend/` e `desktop/` neste repositório
- React: https://react.dev · Vite: https://vite.dev · Tailwind: https://tailwindcss.com · Electron: https://www.electronjs.org/docs
