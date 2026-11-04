# data-collect — Contexto para Agentes de IA

> Este arquivo é o **contexto canônico** do projeto para qualquer agente de IA (Claude, Cursor, Codex, Copilot, etc.). Toda IA que trabalhar neste repositório **deve** ler e seguir o que está aqui antes de propor mudanças. Este arquivo é a **única fonte de verdade** do projeto: se código, README ou outro documento divergirem dele, o AGENTS.md vence (ou é atualizado de propósito, junto com a mudança).

---

## 1. Visão geral

Aplicação **web** (mobile-first) para **montar formulários por definição (JSON)**, preencher esses formulários e guardar os registros em **PostgreSQL**, em **equipes** com **cargos e permissões**: várias pessoas veem e trabalham o mesmo fluxo. Sem foco em setor: o mesmo sistema serve para inspeção de obra, ensaios de laboratório, checklists ou qualquer cadastro. Inspiração: Fulcrum, mas simples e **auto-hospedado** (tudo roda local, no `docker-compose`, sem serviço externo na frente).

> **Este repositório contém o app inteiro** (monorepo): o **backend** Python (`src/forms/`), a **interface web** (`frontend/`: construtor com arrastar e soltar, `FormRenderer`, telas de preenchimento e consulta; React, TypeScript, Vite e Tailwind) e a **infraestrutura** (`docker-compose.yml` e `docker/`, §4.1). O contrato entre front e backend está em §5.3. O **design de referência** do front é `frontend/data-collect-design-pattern.pdf` (§2.11).

O controle de corpos de prova de concreto (projeto original) é apenas um **template de demonstração** (`templates/corpo_de_prova.json`), que prova que o sistema genérico dá conta de um caso real com cálculo de resistência e conformidade.

O projeto é também **material de portfólio/entrevista**: o autor precisa conseguir explicar o núcleo linha por linha (fórmulas, validação, versionamento, RAG). Isso orienta várias regras abaixo.

### Estado atual

**Migração para a versão web em andamento** (roadmap: issue #164 e filhas). Este arquivo descreve o **alvo**; o código ainda está parcialmente no estado anterior (SQLite, `desktop/`, `empacotamento/`, fotos, sem autenticação) e cada issue do roadmap o traz para cá. O núcleo (fórmulas, validação, serviço), a API, a CLI, o `frontend/` e os módulos de IA (`ia/`, `rag/`) existem e estão testados com cliente falso. Ainda não verificados à mão: o fluxo no navegador real e qualquer chamada real a um LLM.

**Ordem de construção (de baixo para cima, sempre com TDD):** `tipos_campo.py` e `formulas.py` (tipos, vazio, datas, funções) → `validacao.py` → `repositorio.py` (Postgres e migrações) → `servico.py` (publicar versão, registros, relação entre formulários, cascata, exclusão) → equipes, cargos e autenticação (§2.12, §2.13) → `api.py` e `cli.py` → `frontend/` (só depois que núcleo e API estiverem testados) → módulos opcionais (`rag/`, `ia/`). A relação entre formulários (§2.7) faz parte do núcleo, mas só entra depois que fórmulas, validação e registros simples estiverem testados.

### Princípio central

> **A IA nunca calcula, só busca e redige.** Quem calcula e valida é código determinístico (campos calculados com fórmulas). Nenhum número de negócio sai de um LLM.

---

## 2. Escopo — o que será feito

### 2.1. Núcleo (obrigatório, sem IA)

- **Formulário = definição em JSON, versionada.** Registro = dados em JSON + a versão com que foi criado. Editar um formulário **nunca** quebra registros antigos.
- **Tipos de campo do MVP:** texto, número (com unidade), data, seleção, sim/não, calculado, seção (só visual), referência a registro de outro formulário (§2.7), localização (coordenadas, §2.8). Não há campo de foto nem anexo de arquivo.
- **Validação no servidor** contra a definição: tipo, obrigatório, opções válidas.
- **Campos calculados:** fórmulas avaliadas por avaliador próprio sobre o módulo `ast` do Python, com lista de permissão (operadores, comparações, as funções `se`, `min`, `max`, `media`, `soma`, `dias` e a constante `pi`).
- O servidor **recalcula sempre** ao salvar. O frontend pode mostrar prévia, mas não é fonte da verdade.
- Ordem de cálculo pelas **dependências** entre campos; **ciclo é rejeitado ao publicar** a versão.
- Campo de entrada vazio gera resultado vazio; erro de fórmula (ex.: divisão por zero) aparece **no campo**, sem derrubar o registro.

### 2.2. Suporte ao construtor de formulários (o construtor em si é o `frontend/`)

- Criar formulário e **publicar uma nova versão** a partir de uma definição JSON, rejeitando definição inválida (fórmula proibida, campo inexistente, ciclo, tipo desconhecido, tipos incompatíveis na fórmula, `id` ausente/duplicado/reservado, `casas_decimais` inválido) com erro claro e localizado.
  - `POST /formularios`: recebe `{nome, definicao}`, cria o formulário e já publica a **versão 1** (um formulário sem versão não pode ser preenchido, então não existe esse estado). Definição inválida → 422 e nada é criado. O nome fica no formulário, fora da definição, e é **único dentro da equipe** (sem diferenciar maiúsculas/minúsculas nem espaços nas pontas); nome repetido → 422 no campo `nome`. Como as referências entre formulários usam o nome (§2.7), renomear fica para "próximos passos". Importar templates que dependem uns dos outros exige a ordem das dependências (a origem primeiro).
  - `GET /formularios`: lista `{id, nome, criado_em, versao_atual_id, versao_atual_numero}`, sem definições.
  - `GET /formularios/{id}`: formulário com a **versão atual completa** (`id`, `numero`, `definicao`); é de onde o front tira o `versao_id` para preencher.
  - `POST /formularios/lote`: recebe `{formularios: [{nome, definicao}]}` e cria todos **numa só transação**, na ordem das dependências (origem primeiro), com a v1 de cada um. Os formulários do lote podem se referenciar entre si e a formulários já existentes. Qualquer erro (definição inválida, nome repetido dentro do lote ou já existente, ciclo) → 422 com os erros localizados por formulário e **nada é criado**. Serve a importação de templates dependentes e o gerador por IA (§2.5).
  - `POST /formularios/{id}/versoes`: recebe `{definicao}` e publica a próxima versão (`numero` anterior + 1); 422 se inválida. `GET /formularios/{id}/versoes` lista `{id, numero, publicada_em}`; `GET /formularios/{id}/versoes/{versao_id}` devolve a versão com definição (para renderizar um registro antigo).
  - Versões são imutáveis: não existe `PUT`, `PATCH` nem `DELETE` de versão (§3.3).
  - **Rascunho de versão:** cada formulário pode ter **um rascunho** (a próxima versão em edição), compartilhado pela equipe. `GET /formularios/{id}/rascunho` (404 se não há), `PUT` (substitui; aceita definição incompleta, como o `validar`), `DELETE` (descarta) e `POST /formularios/{id}/rascunho/publicar` (valida como a publicação e cria a versão `numero` anterior + 1, apagando o rascunho). Salvar com `revisao` antiga → 409 (§2.14). É onde o construtor salva e onde o mapa de vínculos cria referências (§2.7). Versões publicadas continuam imutáveis.
  - `DELETE /formularios/{id}`: regras de bloqueio em §2.7.
- Endpoint para **validar/pré-visualizar** uma definição e para **calcular uma prévia** de fórmulas sem salvar (o servidor continua sendo a fonte da verdade; o front não reimplementa o avaliador).
  - `POST /definicoes/validar`: sem estado (não exige formulário criado). Responde **200** com `{"valida": false, "erros": [...]}`, porque definição incompleta é o caso normal enquanto o usuário edita; o 422 vale só ao **publicar**. Devolve **todos** os erros de uma vez, não só o primeiro.
  - `POST /definicoes/previa`: recebe `{definicao, valores}` e devolve os campos calculados no formato `{"valor", "erro"}` (§7), sem salvar. Usa a **mesma função de cálculo** do salvar. Definição inválida devolve a mesma lista de erros do `validar`.
- Expor o catálogo de tipos de campo e de funções de fórmula permitidas, para a paleta e o editor do front não ficarem dessincronizados.
  - `GET /catalogo`: tipos de campo (id, rótulo, propriedades aceitas), funções (nome, assinatura, descrição, exemplo), a constante `pi` e os nomes reservados. É gerado da **mesma tabela de funções que o avaliador usa**, nunca de uma lista paralela.

### 2.3. Registros: preencher e consultar

- Criar e atualizar registro contra uma versão publicada; validar e recalcular sempre no servidor.
  - `POST /formularios/{id}/registros` exige `versao_id` no corpo: o front renderizou uma versão específica, e o servidor não valida contra outra em silêncio.
  - `PUT /registros/{id}` **substitui** todos os valores (sem `PATCH` parcial), valida e recalcula tudo; o registro continua na versão de origem. Exige a `revisao` lida (§2.14).
  - `GET /registros/{id}` devolve `{id, formulario_id, versao_id, dados, revisao, criado_por, atualizado_por, criado_em, atualizado_em}` (autoria em §2.14); com o `versao_id` o front busca a definição certa.
  - `DELETE /registros/{id}` apaga de verdade (o histórico de alterações fica, §2.14), exceto se outro registro o referencia (§2.7).
  - O cliente manda **só campos de entrada**. Chave de campo calculado ou inexistente → 422 indicando o campo (aceitar e ignorar esconderia bug no front). Erro de validação (obrigatório vazio, opção inválida, tipo errado) → 422 com a lista por `id`; erro de **cálculo** nunca bloqueia (§7).
- Listar registros com colunas derivadas da definição, filtro simples e **exportação CSV**.
  - `GET /formularios/{id}/registros` lista os registros de **uma versão** (parâmetro `versao_id`, padrão a última publicada); as colunas vêm dessa definição, sem campos `secao`. Paginação com `limite` (padrão 50, máximo 200) e `deslocamento`; resposta `{"itens": [...], "total": N}`.
  - Filtro: só **igualdade** em campos `selecao`, `sim_nao`, `texto` e `calculado` booleano, mais `criado_de` e `criado_ate`. Número e data ficam para "próximos passos" (número é guardado como string, então `"25.5"` e `"25.50"` exigiriam comparação numérica). O nome do campo é validado contra a definição (allowlist) antes de entrar na consulta, e o valor vai sempre parametrizado.
  - **Cartões e filtros por status:** a definição aceita a propriedade opcional `exibicao` (§5.2) com o campo em destaque, o campo de status e um resumo. `GET /formularios/{id}/registros/contagens` devolve a contagem por estado (Conforme, Não conforme, Erro no cálculo, Aguardando dados), com os mesmos filtros da listagem. O estado é sempre decidido pelo servidor (§7).
  - `GET /formularios/{id}/registros/exportar`: mesma versão e mesmos filtros da listagem. Cabeçalho `rotulo (unidade)`; números arredondados por `casas_decimais` (§7). Formato para abrir no Excel em português: UTF-8 com BOM, separador `;`, vírgula decimal. Campo calculado com erro sai como `ERRO: <mensagem>`; vazio sai vazio.

### 2.4. Interfaces

- **API** (FastAPI) e **CLI de operação** (migrar o banco, importar template, importar o `forms.db` antigo, reindexar a IA; sempre com `--equipe` e `--usuario` explícitos) chamam as **mesmas funções** de `servico.py`, que não sabe quem as chama. A CLI não é um caminho para furar permissões: ela é para quem administra o servidor.
- A API é consumida pelo **frontend deste mesmo repositório** (`frontend/`); o contrato é o **OpenAPI** gerado pelo FastAPI (§5.3).
- **Frontend** (`frontend/`): construtor de formulários com arrastar e soltar, renderizador de formulário (`FormRenderer`), telas de preenchimento, listagem e consulta, exportação. É só apresentação: **não reimplementa** o avaliador de fórmulas nem a validação (usa `/definicoes/validar`, `/definicoes/previa` e os erros da API). Textos em PT-BR.

### 2.5. Módulos de IA (opcionais — só depois do núcleo estar pronto e testado)

- **Assistente de procedimentos (RAG):** procedimentos em `.md` (escritos pelo autor, genéricos ou sintéticos), busca com **BM25 escrito à mão**, resposta do LLM **somente com os trechos recuperados**, exibindo trecho e arquivo de origem. Sem base nos documentos → responde "não encontrei". Sem internet ou chave de API → mostra só os trechos (fallback).
- **Busca híbrida (opcional dentro do RAG):** (1) filtros de metadados no SQL (equipe, formulário, datas), sempre primeiro; (2) **BM25 escrito à mão** sobre o conjunto filtrado, que continua sendo a base e o fallback; (3) se houver provedor de embeddings (chamado só via `ia/cliente.py`), vetores com **`pgvector`** (índice HNSW), com o modelo e a dimensão guardados junto de cada vetor (vetores de modelos diferentes não se comparam); (4) fusão por RRF (*reciprocal rank fusion*). Sem internet ou chave, vale só filtro + BM25.
- **Resumo de registros por IA:** o LLM redige a partir dos dados e de agregados **calculados pelo código** (contagem, média etc.), em saída estruturada (JSON). O código confere se **todos os números do texto batem com o banco**; se não baterem, o resumo é rejeitado.
- **Gerador de formulário por IA:** a pessoa descreve em texto o que quer e o LLM propõe **um ou mais formulários** (cada um uma **definição JSON**, ligados entre si quando o pedido pedir); a pessoa revisa, ajusta e **aprova** no construtor. O LLM só redige a definição (inclusive o texto das fórmulas): quem valida é o código (`validar_definicao`, §2.2), e nenhum valor de negócio sai do LLM.
  - Saída do LLM é **dado não confiável**: vira JSON no esquema da definição e passa pela mesma validação da publicação. Se houver erros, eles voltam ao LLM para correção, no máximo 2 vezes; persistindo, a proposta segue para o construtor **com a lista de erros**, para a pessoa corrigir.
  - O prompt é montado com o catálogo (tipos de campo, funções, `pi`, nomes reservados), gerado das mesmas tabelas do `GET /catalogo`, e com os **formulários existentes**: para cada um, o `nome` e os campos que ele **compartilha** (`id`, rótulo, tipo), vindos da versão atual. Com isso a IA cria **correlações** (§2.7): campos `referencia` apontando para um formulário existente **ou para outro formulário proposto no mesmo pedido** (`formulario` = nome), e fórmulas que usam `<referência>__<campo compartilhado>`. Ex.: "crie ensaio, proctor e insitu, cada um dependendo do anterior" gera os três, com os campos `compartilhado` onde a origem libera. A validação (§2.7) barra origem inexistente, campo não compartilhado e ciclo, **tratando o conjunto proposto como se já estivesse publicado**. A IA **nunca altera um formulário já publicado**; se precisar de um campo que uma origem existente não compartilha, o erro de validação aparece e a pessoa decide ajustar essa origem no construtor. Nenhum registro nem dado do banco é enviado ao LLM pelo gerador, só o texto do pedido, os metadados acima e, ao refinar, os rascunhos em edição.
  - **Nunca salva.** `POST /definicoes/gerar` recebe `{pedido, rascunhos?}` (`rascunhos` = `[{nome, definicao}]` em edição, para refinar: "adicione um campo X") e devolve `{formularios: [{nome, definicao, erros}]}` sem criar nada. A pessoa pode editar, remover ou renomear cada rascunho e então aprova o conjunto, que é publicado **de uma vez** por `POST /formularios/lote` (§2.2).
  - Sem chave ou sem internet: o recurso fica indisponível, com mensagem clara em PT-BR; o construtor manual continua funcionando. O endpoint só é montado quando o módulo `ia/` existe.
  - **Provedor de LLM neutro:** `ia/cliente.py` expõe a interface `ProvedorDeLLM` (completar, streaming, vetorizar, ferramentas, `capacidades`) com adaptadores para a **Anthropic** e para qualquer API **compatível com OpenAI** (OpenAI, Azure OpenAI, Ollama, LM Studio, vLLM, OpenRouter, Groq, Gemini no endpoint compatível), via `httpx`, mais um cliente falso para testes. O **provedor é configurado por equipe** (provedor, `base_url`, modelo, modelo de embeddings), com a chave **cifrada** em repouso (§12) e nunca devolvida pela API; a instância pode ter um padrão por variável de ambiente. A saída estruturada é portátil: JSON mode, ferramenta com esquema ou prompt com validação, sempre validada e repetida no máximo 2 vezes.
  - **Chatbot (assistente sobre o app e sobre os dados):** `POST /chat` (SSE). As fontes são os guias de ajuda (§2.16) e os **registros e definições indexados como documentos de texto por equipe** (`documentos_ia`, reindexação incremental ao salvar, excluir ou publicar). Perguntas de filtro ou de número ("quais formulários foram preenchidos dia X?", "quantos corpos de prova em outubro?") usam **ferramentas determinísticas** (`buscar_registros`, `contar_registros`, `valor_do_campo`, `agregar`): o LLM só escolhe a ferramenta e os argumentos, **validados contra a definição**; **nunca gera SQL**; o código calcula e **confere que todo número do texto bate** com o resultado. A resposta traz citações com link para o registro ou guia; sem base → "não encontrei"; sem IA → só os trechos e resultados. Conteúdo de registro é **entrada não confiável** (bloco delimitado, com a instrução de ignorar comandos ali dentro). Respeita equipe, cargo e `"ia": false` (§2.15), tem limite de uso por pessoa e por equipe e guarda conversas por usuário (apagáveis).
  - Resumo e assistente na API: `POST /formularios/{id}/resumo` (mesma versão e filtros da listagem; o código calcula os agregados e o resumo é descartado, com 502, se algum número não bater) e `POST /assistente/perguntar` (`{pergunta}`; devolve `{encontrou, texto, usou_ia, trechos}`; sem IA devolve só os trechos), que o `POST /chat` substitui. `IaIndisponivel` vira 503 e resposta da IA fora do formato, 502, ambos no erro uniforme em PT-BR.
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
- **No front (apresentação, sem regra nova):** o campo `referencia` mostra o registro de origem escolhido com os valores que ele libera (campos `compartilhado`), deixa **escolher** numa lista com busca (registros de todas as versões da origem) e, sem sair do preenchimento, **criar** ou **editar** o registro de origem numa gaveta; a origem pode depender de outra, e as gavetas se empilham. Quem valida, calcula e recalcula em cascata continua sendo o servidor.
- **Mapa de vínculos (front):** tela `#/mapa`, no estilo de um fluxo do n8n, com duas abas: *Formulários* (quem aponta para quem, pela definição atual) e *Registros e valores* (qual registro aponta para qual, com os valores já calculados e a conformidade). Cartões com portas à esquerda e à direita, setas ortogonais (azul = cadeia do item selecionado, para trás e para frente), grade pontilhada, pan e zoom e um **painel lateral** (campos liberados, "depende de", "alimenta", nomes liberados nas fórmulas, "Abrir no construtor"). **Dá para criar vínculo pelo próprio mapa**: clicar na porta direita da origem e depois na esquerda do dependente cria o campo `referencia` **no rascunho da próxima versão do dependente** (§2.2); versões publicadas nunca mudam e o servidor continua rejeitando ciclos ao publicar. Exige a permissão de publicar formulários (§2.13).

### 2.8. Campo de localização

- **`localizacao`:** guarda um ponto como `{"latitude": "-23.550520", "longitude": "-46.633308"}` (strings, no mesmo espírito do `Decimal`, §7). Valida a faixa (latitude de −90 a 90, longitude de −180 a 180); um dos dois sem o outro é erro, e `obrigatorio` vale para o par. Fica no JSON do registro, sem extensão espacial. Não pode ser usado em fórmulas. No CSV sai como `lat / lon` (ex.: `-23,550520 / -46,633308`).
- No celular, o front oferece **"Usar minha localização"** (`navigator.geolocation`, só sob gesto da pessoa, com mensagem clara se a permissão for negada); a validação continua no servidor.
- **Não há fotos nem anexos**: o tipo `foto`, o processamento de imagem, a tabela `anexos` e os endpoints `/anexos` foram removidos por decisão do autor (sem upload de arquivo no produto).

### 2.9. Aplicação web e implantação

O produto é uma **aplicação web** usada por equipes e **auto-hospedada**: tudo sobe com `docker compose up` (PostgreSQL com `pgvector`, Logto, API e, em desenvolvimento, um servidor de e-mail de teste; o frontend roda à parte, no Vite), sem serviço externo na frente. **Não há proxy reverso no repositório** (o Caddy foi removido por decisão do autor): servir o front e o HTTPS em produção está em aberto. Detalhes técnicos em §4.1.

- Acesso por navegador, com o celular em primeiro lugar, e como PWA instalável (§2.17).
- Fora do escopo: serviço externo de borda (CDN, WAF de terceiros), Kubernetes e multi-região (§3.1). Sem esse tipo de serviço, o app **não cobre DDoS volumétrico**; o que ele faz é limitar abuso de aplicação e esgotamento de recursos (§12).

### 2.10. Pastas e duplicação de formulários

Organização da lista de formulários. Não muda definição, versão nem registro.

- **Pastas:** uma árvore (pasta com subpastas, profundidade livre) que **só organiza formulários**. Um formulário está em no máximo uma pasta; sem pasta, ele fica na raiz. Pasta não afeta referências entre formulários (§2.7, que usam o **nome** do formulário, e o nome continua único dentro da equipe), versões nem registros.
  - `POST /pastas` recebe `{nome, pasta_pai_id?}`; `GET /pastas` devolve a lista **plana** `{id, nome, pasta_pai_id, criado_em}` (o front monta a árvore); `PUT /pastas/{id}` recebe `{nome, pasta_pai_id}` e **substitui** os dois (renomear e mover, sem `PATCH`).
  - `PUT /formularios/{id}/pasta` recebe `{pasta_id}` (`null` = raiz) e move o formulário. `GET /formularios` passa a trazer `pasta_id`, e `POST /formularios` aceita `pasta_id` opcional.
  - O nome da pasta é **único entre pastas irmãs** (mesma pasta pai), sem diferenciar maiúsculas/minúsculas nem espaços nas pontas; repetido → 422 no campo `nome`. Mover uma pasta para dentro dela mesma ou de uma descendente → 422 no campo `pasta_pai_id`. Pasta de destino inexistente → 422 no campo; pasta da URL inexistente → 404.
  - `DELETE /pastas/{id}` só se a pasta não tem subpastas **nem** formulários; senão 409 (nada é apagado em cascata).
- **Duplicar:** `POST /formularios/{id}/duplicar` recebe `{nome?}` e responde **201** com o formulário novo (mesmo formato de `GET /formularios/{id}`).
  - A cópia nasce com a **versão 1 igual à definição da versão atual** do original, na **mesma pasta**, **sem registros**. É um formulário independente: nenhum vínculo com o original além do conteúdo inicial. Passa pela mesma publicação de §2.2 (validação e registro das dependências).
  - Sem `nome`, o padrão é `<nome> (cópia)`; se já existir, `<nome> (cópia 2)`, `(cópia 3)` e assim por diante. `nome` informado e repetido → 422 no campo `nome` (§2.2).
  - Quem depende do original **não** passa a depender da cópia; a cópia depende das mesmas origens que o original (§2.7).

### 2.11. Experiência do front

Qualidade de interface do `frontend/`. É só apresentação (§2.4): nada aqui reimplementa fórmula nem validação. O **design de referência** é `frontend/data-collect-design-pattern.pdf` (sistema de design, telas mobile, construtor, mapa de vínculos, equipe e cargos); o front deve ficar como ele.

- **Sistema de design:** tokens definidos num só lugar. Cores: Gelo `#F6F8FB` (fundo), Papel `#FFFFFF` (cartões), Preto `#0B0F19` (texto), **Azul de ação `#1D4ED8`** (ação principal e tudo que está selecionado ou vinculado; é o único azul), Conforme `#14573A`, Não conforme `#8E1C14`, Atenção `#FBEBC8` (erro de cálculo). Tipografia: Archivo (títulos), IBM Plex Sans (interface) e IBM Plex Mono (valores de medição, ids e fórmulas), **hospedadas no próprio app** (sem Google Fonts: nada de terceiro que veja o IP de quem usa). Marca só em texto, `data-collect` com o hífen em azul, sem símbolo.
- **Estados do campo calculado** sempre com ícone **e** texto, nunca só cor: Conforme, Não conforme, Erro no cálculo, Aguardando dados.
- **Regra por cargo:** o que o cargo não pode fazer **some** quando não faz sentido para ele e fica **bloqueado com explicação** (borda tracejada, cadeado e a frase da permissão que falta) quando a pessoa esperaria encontrá-lo. A navegação deriva das **permissões** de `GET /eu`, não do nome do cargo. É conveniência: o servidor sempre barra (§3.3).
- **Skeletons** no lugar do "Carregando…": o esqueleto tem a forma da tela que vai aparecer, para a página não "pular" quando o dado chega.
- **Arrastar e soltar** do construtor com feedback claro: item arrastado com `DragOverlay`, linha azul "Soltar aqui" no ponto de destino e animações curtas, também por teclado e por toque, com alternativa sem arraste ("mover para cima/baixo").
- **Editor de fórmulas** mais próximo do Excel: autocomplete de campos e funções, assinatura da função ao digitá-la, parênteses pareados e destacados, mensagem "Fórmula válida · resultado: número" e uma forma de montar a fórmula por **blocos arrastáveis** (campos, funções, operadores e parênteses). O editor só **monta o texto** da fórmula; quem valida é `POST /definicoes/validar` e quem calcula é o servidor (§2.2, §7). A gramática continua sendo a do §7.
- **Construtor:** cabeçalho com caminho da pasta e "rascunho da vN", **Criar com IA**, **Validar** e **Publicar versão N**; a partir de 1024 px, três colunas (tipos, campos, propriedades).
- Foco visível, contraste mínimo 4,5:1, alvos de toque de 44 px e respeito a `prefers-reduced-motion`.
- Biblioteca nova só com justificativa na issue (§9.12). O `dnd-kit` já está no projeto.

### 2.12. Autenticação

- A identidade é do **Logto auto-hospedado** (OIDC): e-mail e senha, verificação de e-mail, recuperação de senha, telas em PT-BR e senha de no mínimo 10 caracteres. **Não há cadastro livre: o acesso é por convite** (§2.13). O Logto em si deixa criar conta (a tela de cadastro é a que o link do convite usa), mas uma conta sem convite **não entra em equipe nenhuma**: o app só dá acesso a quem é membro de uma equipe, e o servidor responde 403 a quem não é. Quem entra por um convite cria a conta e **aceita os Termos e a Política** (§2.15). O Logto guarda a senha (com hash); o app **nunca** a vê.
- **Token de acesso curto, de 10 minutos**, renovado pelo SDK com refresh token (rotação ligada); "Manter conectado neste aparelho" estende só a sessão, nunca o token. A renovação é sob demanda: ao receber `401` com código `token_expirado`, o front renova uma vez e repete a chamada.
- A API valida o JWT em **todo** endpoint (exceto `healthz` e `readyz`): assinatura pelo JWKS descoberto no OIDC, `iss`, `aud` e `exp`. A **equipe** vem do cabeçalho `X-Equipe`, que é só um pedido: o servidor confere no banco se a pessoa é membro ativa dela (sem o cabeçalho, vale a única equipe da pessoa). **Cargo e permissões não vêm do token**: são lidos do banco a cada requisição (§2.13), então mudar um cargo ou desativar alguém vale na hora.
- **Primeiro administrador:** a variável de ambiente `FORMS_ADMIN_EMAIL` (com o nome da equipe) faz a subida criar a equipe e convidar o administrador inicial; é idempotente.
- `GET /eu` devolve perfil, equipe, cargo e permissões, para o front esconder e bloquear.

### 2.13. Equipes, cargos e permissões (RBAC)

- **Equipe** (tabela `grupos`, coluna `grupo_id`; na interface e nas mensagens, sempre "Equipe"): formulários, pastas, registros e dados de IA pertencem a uma equipe. O nome de formulário é único **dentro da equipe** e as referências entre formulários (§2.7) resolvem dentro dela. A v1 trabalha com uma equipe ativa por pessoa; o seletor de equipe só aparece para quem está em duas ou mais.
- **Cargo:** conjunto **editável** de permissões, **um por pessoa**. As **17 permissões**: `formularios:ver`, `formularios:publicar` (criar e publicar versões), `formularios:excluir`, `formularios:organizar` (pastas); `registros:ver`, `registros:criar`, `registros:editar_proprios`, `registros:editar_todos`, `registros:excluir`, `registros:exportar`; `ia:criar_formularios`, `ia:assistente`; `equipe:ver`, `equipe:convidar` (convidar e desativar), `equipe:atribuir_cargos`, `historico:ver`, `cargos:editar`.
- **Cargos de partida** (semeados e editáveis): Administrador (as 17); Gestor (`formularios:ver`, `registros:ver`, `registros:exportar`, `equipe:ver`, `historico:ver`); Engenheiro (11: as 4 de formulários, registros exceto excluir, e as 2 de IA); Técnico (`formularios:ver`, `registros:ver`, `registros:criar`, `registros:editar_proprios`); Visualizador (`formularios:ver`, `registros:ver`).
- **Regras:** sempre existe ao menos um Administrador ativo (não se remove nem rebaixa o último); cargo em uso não é excluído; `registros:editar_proprios` compara com `criado_por`; a matriz **endpoint → permissão** é uma tabela única, usada pela API e pelo catálogo de permissões.
- **Isolamento:** todo acesso a dados filtra por `grupo_id`; recurso de outra equipe responde **404** (não 403, para não revelar que existe); testes de vazamento percorrem todas as rotas que recebem id. Row Level Security no Postgres é defesa em profundidade opcional.
- **Convites e pessoas:** convite com token de 256 bits guardado **só como hash**, validade e o **cargo** da pessoa; abas Ativos, Convites e Inativos; **desativar** tira o acesso na hora e mantém o nome e os registros. Escopo de cargo por pasta fica para depois.

### 2.14. Autoria, histórico e concorrência

- Todo registro guarda `criado_por` e `atualizado_por`. Cada alteração grava uma linha de **histórico** (valores anteriores, quem, quando), na mesma transação; a cascata (§2.7) registra "recalculado por alteração em #N". `GET /registros/{id}/historico` exige `historico:ver`; a listagem aceita o filtro "só os meus".
- **Concorrência otimista:** o registro (e o rascunho de versão) tem uma `revisao`; o `PUT` exige a lida; divergência → **409** com mensagem em PT-BR dizendo quem alterou e quando. Cascata e exclusão usam `SELECT ... FOR UPDATE` em ordem estável de ids, para não dar deadlock.

### 2.15. LGPD

- **Aceite obrigatório** dos Termos de Uso e da Política de Privacidade no cadastro (checkbox no Logto), com **registro próprio** (`consentimentos`: pessoa, documento, versão, data; sem guardar o IP, ou só truncado). Mudou a versão do documento → **reaceite** antes de continuar. Os textos ficam versionados em `legal/` e aparecem em páginas públicas, e precisam de revisão jurídica antes de produção.
- **Direitos do titular:** `GET /eu/exportar` (perfil, consentimentos, equipes e autoria) e `DELETE /eu` (remove a pessoa no Logto e no app e **anonimiza** a autoria, sem apagar o trabalho da equipe; bloqueia se for o único Administrador de uma equipe com outras pessoas).
- **IA:** desligada por padrão em cada equipe; ativar exige um aviso claro (para onde os dados vão, qual provedor) e o aceite fica registrado. Campo com `"ia": false` na definição (ex.: CPF) **nunca** entra em índice nem prompt; `localizacao` fica fora por padrão.
- **Operação:** mapa de dados e retenção documentados, **logs sem dados pessoais** (sem e-mail, valores de campo nem corpo de requisição) e um plano de resposta a incidente.
- Fontes e demais recursos de interface são servidos pelo próprio app, sem CDN de terceiros.

### 2.16. Introdução e ajuda

- **Tour** no primeiro acesso (curto, pode ser pulado e revisto; o progresso fica no servidor, por pessoa), **checklist "Primeiros passos"** marcado pelo estado real da equipe, estados vazios que ensinam e uma **galeria de exemplos** que importa os `templates/` por `POST /formularios/lote`.
- **Central de ajuda** dentro do app, com guias em Markdown (`ajuda/`) renderizados sem HTML cru e ajuda contextual ("?") em cada tela. A mesma pasta alimenta o chatbot (§2.5).

### 2.17. Mobile-first e PWA

- **Mobile primeiro**: até 640 px, uma coluna, barra de navegação embaixo (por cargo) e ação principal ao alcance do polegar, com a barra de salvar fixa no formulário; a partir de 640 px, menu lateral fixo e cartões que viram tabela quando há colunas; a partir de 1024 px, construtor em três colunas.
- Teclados certos (`inputmode="decimal"` aceitando vírgula, `type="date"` nativo), gaveta de referência como *bottom sheet* em tela estreita, filtros em folha, "carregar mais" na listagem, GPS no campo `localizacao` (§2.8) e mapa de vínculos navegável por toque (com lista indentada como alternativa).
- **PWA** instalável: manifest, ícones e um service worker que guarda **só os arquivos estáticos** do app. **Nunca** cacheia resposta da API, token nem dados da equipe; **não há uso offline de dados** (§3.1).
- Testes ponta a ponta em viewport de celular (Playwright), acessibilidade e orçamento de desempenho no CI.

### 2.18. Início, busca e notificações

- **Início:** saudação, cargo, busca, "Novo registro" e "Criar formulário" (conforme as permissões), registros recentes com estado e pastas.
- **Busca global** `GET /busca?q=`: determinística (sem IA), por nome de formulário, `#id` e valores de campos `texto` e `selecao`, limitada ao que o cargo vê; termo sempre parametrizado.
- **Notificações** no sino, só dentro do app (sem push nem e-mail): convite aceito, cargo alterado, registro seu editado por outra pessoa e erro de cálculo em cascata em registro seu.

---

## 3. Escopo — o que NÃO será feito

Estas exclusões são **deliberadas**. Não implemente, não "adiante" e não sugira como parte de uma tarefa comum. Se uma tarefa parecer exigir algo daqui, pare e pergunte.

### 3.1. Funcionalidades fora do escopo (vão para "próximos passos" no README)

- Grupo repetível (tabela de linhas) e visibilidade condicional. Consulta espacial (distância, raio) e mapas sobre `localizacao`.
- Relação um-para-muitos **dentro de um mesmo registro** (ex.: lote com vários corpos de prova como linhas). A relação *entre formulários*, por referência a um registro, está no escopo (§2.7).
- **Fotos e anexos de qualquer tipo** (decisão do autor): nada de upload de arquivo.
- Modo offline e sincronização de **dados** (o PWA só guarda arquivos estáticos, §2.17); edição simultânea ao vivo em tempo real; notificação por push ou por e-mail.
- Cadastro livre (o acesso é por convite), SSO corporativo (SAML) e criação de equipes por autoatendimento. Escopo de cargo por pasta é opcional e fica para depois.
- Aplicativo desktop ou instalável (Electron, PyInstaller), assinatura de código e loja de apps.
- **Serviço externo na frente do app** (CDN, WAF ou proteção de DDoS de terceiros), Kubernetes e multi-região: o produto é auto-hospedado e **tudo roda local**. Consequência assumida: sem mitigação de ataque volumétrico (§2.9).
- Código de interface fora de `frontend/`. O `dist/` gerado não é versionado. Para testar a API sem subir o front, use Swagger (`/docs`, só em desenvolvimento), `curl` ou `TestClient`.

### 3.2. Tecnologias proibidas

LangChain, LlamaIndex, LiteLLM (por ora), **ORM** (SQL à mão com `psycopg`), bancos vetoriais dedicados (Pinecone, Qdrant, Chroma etc.; o `pgvector` dentro do Postgres é **permitido**), serviços de identidade hospedados por terceiros (Auth0, Clerk, Logto Cloud: o Logto é **só auto-hospedado**), Electron e empacotadores de desktop. Permitidos, cada um com sua justificativa: PostgreSQL, Docker e `docker-compose`, `psycopg`, `pgvector`, `PyJWT`, `cryptography` (Fernet), `@logto/react`, `@fontsource-*`, Playwright. **Nova dependência exige justificativa**: o autor precisa conseguir defender cada uma.

### 3.3. Proibições de comportamento

- ❌ **Nunca `eval`, `exec`, `compile` ou `__import__`** para fórmulas. Só o avaliador sobre `ast` com lista de permissão. Nó de AST fora da lista → erro explícito, nunca ignorado.
- ❌ **Nunca pedir ao LLM para calcular, converter unidade, somar ou conferir número.** O LLM só redige texto sobre dados já calculados.
- ❌ Não confiar no frontend: validação, recálculo e **permissão** são do servidor, sempre. Esconder um botão não é proteção.
- ❌ **Nenhum acesso a dados sem `grupo_id`**: toda consulta filtra pela equipe; recurso de outra equipe é 404.
- ❌ **Nunca pedir ao LLM para gerar SQL** nem executar o que ele devolve; ele só escolhe ferramentas de um conjunto fechado, com argumentos validados.
- ❌ Nunca enviar à IA um campo com `"ia": false`, nem dado de uma equipe que não ativou a IA.
- ❌ Nunca guardar segredo em claro no banco: token de convite só como hash, chave de LLM cifrada; senha é do Logto.
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
| Persistência | **PostgreSQL 16** com `psycopg` 3 e pool, SQL à mão e **sem ORM**; dados dinâmicos em `jsonb`; migrações em arquivos SQL numerados |
| Vetores | extensão `pgvector` |
| Fórmulas | módulo `ast` com lista de permissão |
| CLI | `argparse` (operação) |
| API | FastAPI, Uvicorn, Pydantic v2 **só na borda** (nunca no domínio) |
| Autenticação | **Logto** auto-hospedado (OIDC); `PyJWT[crypto]` valida o token na API; `@logto/react` no front |
| Segredos | `cryptography` (Fernet) para a chave de LLM de cada equipe |
| Recuperação (opcional) | filtros SQL + BM25 escrito à mão + `pgvector`, sem framework |
| IA (opcional) | provedores de LLM atrás de `ia/cliente.py` (Anthropic e compatíveis com OpenAI), via SDK ou `httpx` |
| Configuração | `python-dotenv`, `.env` fora do git |
| Frontend (`frontend/`) | React, TypeScript (`strict`), Vite, Tailwind CSS; `npm`; fontes hospedadas (`@fontsource`); PWA |
| Infraestrutura | Docker e `docker-compose`. Sem proxy reverso por ora: o HTTPS e a entrega do front em produção estão em aberto (um proxy, Caddy, nginx ou Traefik, volta por decisão do autor) |
| Qualidade do front | Vitest + Testing Library, Playwright (e2e em viewport mobile), ESLint, Prettier |
| Qualidade | `pytest` contra Postgres real, `httpx` (TestClient), `ruff` (com a regra `S608`), GitHub Actions |

**Execução:** `docker compose up` sobe tudo (§4.1). **Desenvolvimento do front:** `npm run dev` (Vite, porta 5173) chamando a API; como são origens diferentes, a API habilita **CORS só para as origens configuradas** por variável de ambiente; nunca `*`. Em desenvolvimento tudo é HTTP no `localhost` (front `:5173`, API `:8000`, login `:3001`), então não há certificado; os endereços vêm de `APP_URL`, `AUTH_URL` e `API_URL`. Em produção, a origem do front também entra no CORS enquanto não houver proxy que una front e API.

### 4.1. Implantação (Docker Compose)

- **Serviços:** `postgres` (com `pgvector`), `logto` e um `logto-setup` que provisiona tudo como código e de forma idempotente (aplicativo SPA com refresh token rotativo, aplicativo M2M da API, API resource com token de 10 minutos, conector SMTP, tela de login em PT-BR com senha mínima de 10 caracteres e aceite dos termos). O `iss` do token é o endereço público do login, mas a API busca as chaves (JWKS) e fala com a Management API pela rede interna (`LOGTO_INTERNO`), `api`, um `backup` diário com `pg_dump` (volume `backups`, com retenção) e, só em desenvolvimento (`docker-compose.override.yml`, carregado sozinho), um servidor de e-mail de teste (Mailpit) e as portas do Postgres, da API e do Logto no `127.0.0.1`. **O `docker-compose.yml` principal não publica porta nenhuma**; só o override de desenvolvimento publica, e só no `127.0.0.1`. O front roda com `npm run dev` e descobre o id do aplicativo do Logto por `public/config.json` (gerado do `logto-setup`) ou pelas variáveis `VITE_*`.
- **Configuração** por variáveis de ambiente (`.env.example` documentado; `.env` nunca vai ao git, à imagem nem ao banco).
- **Banco:** migrações aplicadas por `forms migrar` (e opcionalmente na subida) com trava `pg_advisory_lock`; o banco persiste entre versões, então migração de esquema é crítica (§5.2). Backup com `pg_dump` agendado e restauração testada; `GET /healthz` e `GET /readyz` para os healthchecks.
- **Proteção local:** timeouts do uvicorn contra conexão lenta, limite de corpo (413), limites por pessoa e por equipe nos endpoints caros, limites de CPU e memória por contêiner e `statement_timeout` no Postgres (§12). **Sem proxy, não há limite por IP nem `fail2ban`**, e o que faltar aqui volta quando houver um proxy. **Não cobre DDoS volumétrico** (sem serviço de borda, por decisão).
- **CI:** Postgres como serviço, `ruff`, `pytest` (Linux), build da imagem da API, o job do `frontend/` e o e2e (compose sem proxy mais o Vite).
- Dependências da infraestrutura e por quê: Docker (ambiente reproduzível e subida em um comando), Logto (identidade e e-mail/senha prontos, sem escrever autenticação), `PyJWT` (validar o token sem escrever criptografia), `pgvector` (busca vetorial no próprio banco), `cryptography` (cifrar a chave de LLM).

---

## 5. Arquitetura

```
src/forms/   models.py  tipos_campo.py  formulas.py  validacao.py
             exportacao.py  repositorio.py  segredos.py  cli.py
             migracoes/  0001_baseline.sql ...  (esquema versionado)
             api.py  api_esquemas.py  api_rotas.py  api_extensoes.py  auth.py  exportar_openapi.py
             servico.py (fachada)  servico_base.py  servico_registros.py  servico_consulta.py
             servico_pastas.py  servico_equipes.py (equipes, cargos, convites)  servico_rascunhos.py
             rag/  chunker.py  indice.py  semantico.py  responder.py  extensao.py  (opcional)
             ia/   cliente.py (provedores)  resumo.py  validacao.py  gerador.py  chat.py  extensao.py  (opcional)
templates/   corpo_de_prova.json  inspecao_obra.json  (exemplos)
ajuda/       guias em .md (central de ajuda e base do chatbot)
legal/       Termos de Uso e Política de Privacidade (versionados)
docs/        procedimentos em .md (base do assistente)
frontend/    React + TypeScript + Vite + Tailwind (§4); data-collect-design-pattern.pdf
docker/      Dockerfiles, backup, init do Postgres e guia de operação
docker-compose.yml
tests/       test_formulas.py  test_validacao.py  test_servico.py  test_api.py ...
```

**Resumos de pasta:** cada pasta com código tem um `README.md` curto (o que é, o que tem, como se conecta, como testar), mantido pelo `doc-writer`. `src/forms/` tem um só, com uma seção por módulo. O resumo descreve o que **existe** no código; as regras e o alvo continuam aqui. As pastas `docs/`, `ajuda/` e `legal/` guardam conteúdo (base do RAG, guias e textos legais) e não recebem esses resumos.

### 5.1. Camadas e direção de dependência

```
api.py / cli.py  →  servico.py  →  validacao.py, formulas.py, tipos_campo.py, segredos.py
                                →  repositorio.py  →  psycopg  →  PostgreSQL
```

- **`models.py`**: `dataclasses` do domínio. Sem Pydantic, sem I/O.
- **`tipos_campo.py`**: o que cada tipo aceita, valida e normaliza.
- **`formulas.py`**: parse, grafo de dependências, detecção de ciclo e avaliação. Funções puras, sem I/O.
- **`validacao.py`**: valida um registro contra uma definição.
- **`segredos.py`**: hash de token (SHA-256, comparação em tempo constante) e cifra e decifra da chave de LLM (Fernet). É o **único** lugar que mexe com criptografia.
- **`repositorio.py`**: único módulo que fala SQL. Sempre com parâmetros (`%s`), nunca f-string em SQL (a regra `S608` do `ruff` e um teste de varredura garantem); identificador dinâmico, se um dia houver, só com `psycopg.sql`. **Todo método recebe o `grupo_id`** e o aplica na consulta. O esquema vem de `migracoes/` (§5.2).
- **`servico.py`**: casos de uso (importar template, publicar versão, validar definição, prévia de fórmulas, catálogo, criar/atualizar registro, listar, exportar). Ponto de entrada comum de API e CLI. Cada caso de uso recebe o **contexto da requisição** (`usuario_id`, `grupo_id`, permissões) por parâmetro; o `servico` não sabe de HTTP. Para não virar um arquivo gigante, os casos de uso de registros (`servico_registros.py`), consulta/exportação (`servico_consulta.py`), pastas (`servico_pastas.py`), equipes, cargos e convites (`servico_equipes.py`) e rascunhos de versão (`servico_rascunhos.py`) moram em módulos próprios, e as peças comuns (transação, campos compartilhados) em `servico_base.py`; `servico.py` os reexporta, então API e CLI chamam tudo por `servico.<função>`.
- **`exportacao.py`**: formatação das células e geração do CSV (§2.3, §12). Funções puras, sem I/O; usada por `servico_consulta.py`.
- **`api.py`**: Pydantic e HTTP só aqui; traduz erros de domínio em respostas HTTP. Fica dividida em `api.py` (app, CORS, cabeçalhos de segurança, limites, tratadores de erro), `auth.py` (validação do JWT do Logto e montagem do contexto da requisição), `api_esquemas.py` (modelos Pydantic de entrada e saída) e `api_rotas.py` (endpoints); `api_extensoes.py` descobre e monta as rotas dos módulos opcionais; `exportar_openapi.py` gera o `openapi.json` do front.
- **`cli.py`**: `argparse` fino, só para operação (§2.4); só chama `servico.py`.
- Dependências apontam **para baixo**: o núcleo nunca importa `api`, `cli`, `rag` ou `ia`.
- **Módulos opcionais** (`rag/`, `ia/`) dependem do núcleo, nunca o contrário; o app inteiro funciona com eles removidos. Cada um publica um `EXTENSAO` em `extensao.py` (rotas e tratadores de erro), e o núcleo o procura **pelo nome** em execução (`descobrir_extensoes()`), sem importá-lo; só a ausência do próprio módulo é tolerada. Sem a pasta do módulo, o app sobe normalmente.

### 5.2. Modelo de dados (PostgreSQL)

```
grupos                  id, nome, criado_em
usuarios                id, logto_sub (único), nome, email, ativo, criado_em, ultimo_acesso_em
cargos                  id, grupo_id, nome, descricao, padrao
cargo_permissoes        cargo_id, permissao
membros_grupo           grupo_id, usuario_id, cargo_id, entrou_em
convites                id, grupo_id, email, cargo_id, token_hash, expira_em, usado_em
consentimentos          usuario_id, documento, versao, aceito_em
formularios             id, grupo_id, nome (único por grupo), pasta_id (nulo = raiz), criado_em
pastas                  id, grupo_id, nome, pasta_pai_id (nulo = raiz), criado_em
versoes_formulario      id, formulario_id, numero, definicao (jsonb), publicada_em
rascunhos_formulario    formulario_id, definicao (jsonb), base_versao_id, atualizado_por, atualizado_em, revisao
registros               id, grupo_id, formulario_id, versao_id, dados (jsonb), revisao, criado_por, atualizado_por, criado_em, atualizado_em
historico_registro      id, registro_id, usuario_id, quando, valores_anteriores (jsonb), motivo
dependencias_formulario formulario_id, depende_de_id
referencias_registro    registro_id, campo_id, destino_id
```

- Tabelas de IA (`config_ia_grupo` com a chave cifrada, `documentos_ia` com `vector`, `conversas_ia`, `mensagens_ia`, `uso_ia`), de notificações e de progresso do tour seguem o mesmo padrão e nascem nas issues do roadmap; **toda tabela de dados da equipe leva `grupo_id`**.
- `dependencias_formulario` é preenchida ao publicar e o vínculo permanece enquanto o formulário existir (versões antigas e seus registros ainda apontam). `referencias_registro` é mantida ao salvar o registro. As duas existem para bloquear exclusões e achar dependentes na cascata sem varrer colunas JSON (§2.7).
- Todo registro aponta para a `versao_id` com que nasceu. Editar o registro **não muda a versão**: ele é validado e recalculado contra a versão de origem. Migrar registro para versão nova está fora do escopo (próximos passos).
- Esquema versionado em **arquivos SQL numerados** (`migracoes/`), aplicados em ordem por um executor pequeno (tabela `esquema_versao`, trava `pg_advisory_lock`), sem ferramenta de migração externa. O banco persiste entre versões do app, então toda mudança de esquema exige **teste de atualização a partir do esquema anterior**.

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

Valores de `tipo`: `texto`, `numero`, `data`, `selecao`, `sim_nao`, `calculado`, `secao`, `referencia`, `localizacao`. Campo `referencia` exige `"formulario"` (nome do formulário de origem); qualquer campo (exceto `secao` e `referencia`) aceita `"compartilhado": true` (§2.7). Campo `selecao` exige `"opcoes"`: lista não vazia de strings, sem duplicatas (ex.: `"opcoes": ["Aprovado", "Reprovado"]`). Qualquer campo aceita `"ia": false` (nunca vai à IA, §2.15). A definição aceita, no nível de `campos`, a propriedade **opcional** `"exibicao": {"destaque": "resistencia_mpa", "status": "conforme", "resumo": ["data_moldagem"]}`: `destaque` é campo numérico (ou calculado numérico), `status` é campo calculado **booleano** e `resumo` lista campos existentes; a publicação rejeita ids inexistentes ou de tipo errado. Sem ela, o servidor usa o primeiro calculado numérico e o primeiro calculado booleano.

### 5.3. Contrato com o frontend (`frontend/`, mesmo repositório)

- O frontend está no mesmo repositório, mas o **backend é a fonte da verdade** de dados, validação, cálculo e do esquema da definição de formulário.
- O contrato tem duas partes: o **OpenAPI** do FastAPI (`/openapi.json`, `/docs`) e o **formato do JSON de definição** (§6). Modelos Pydantic da API têm nomes e campos estáveis e `response_model` explícito em todo endpoint.
- Mudança **compatível** (campo opcional novo, endpoint novo): livre. Mudança **incompatível** (renomear/remover campo, mudar tipo, mudar semântica): só com aviso explícito na tarefa/PR, descrevendo o impacto no front; o ajuste do `frontend/` entra no mesmo PR. Os tipos TypeScript da API são **gerados do OpenAPI** (`openapi-typescript`), nunca escritos à mão, e o CI falha se o arquivo gerado estiver desatualizado.
- Erros da API têm formato uniforme (`{"detalhe": "...", "erros": [{"campo": "...", "mensagem": "..."}]}`) com mensagens em PT-BR, para o front exibir no campo certo. Erro de validação de registro → 422; recurso inexistente (ou de outra equipe) → 404; definição inválida ao publicar → 422; exclusão bloqueada por vínculo (§2.7) → 409; edição com `revisao` antiga (§2.14) → 409; sem token ou token inválido → 401 (com o código `token_expirado` quando só expirou); sem permissão → 403; termos pendentes → 403 com o código `termos_pendentes`; limite de uso → 429 e corpo grande demais → 413.
- **Localização de erro de definição:** `campo` usa o **id do campo** (`resistencia_mpa.formula`), nunca o índice, porque o índice muda quando o usuário reordena campos no editor e o id não. Exceção: quando o problema é o próprio id (ausente, duplicado ou reservado), usa o índice (`campos[3].id`), já que não há id confiável; erro global (ex.: definição sem a chave `campos`) usa `campos`. Erro de fórmula pode trazer `posicao` opcional (`{"inicio": 12, "fim": 20}`, offsets do `ast` no texto da fórmula) para o front sublinhar o trecho. Ciclo cita os campos envolvidos.
- Endpoints não dependem de estado de sessão nem de cookie: toda chamada leva `Authorization: Bearer <token do Logto>` (§2.12) e o servidor confere a permissão do cargo (§2.13) a cada requisição.
- Texto livre ou número vindo do front nunca é confiável (§3.3).
- **Valores numéricos trafegam como string** nas respostas, para não perder precisão no front; a entrada aceita número ou string (§7). Campos calculados vêm como `{"valor", "erro"}` (§7).
- `POST /definicoes/validar` não é uma resposta de erro: devolve 200 com `{"valida", "erros"}` (§2.2), então não segue o formato `{"detalhe", "erros"}` acima, mas cada item de `erros` usa o mesmo `{"campo", "mensagem"}`.

---

## 6. Idiomas

| Onde | Idioma |
|---|---|
| **Vocabulário de domínio** (`formulario`, `registro`, `versao`, `rotulo`, `obrigatorio`, módulos `servico.py`, `tipos_campo.py`…, tabelas, chaves do JSON de definição e campos da API) | **Português** (sem acentos em identificadores) |
| **Termos técnicos/infra** (`handler`, `middleware`, `router`, `fixture`) | **Inglês** quando já são o nome padrão da técnica |
| **Código do front** (`frontend/`) | Identificadores de domínio em português (`Formulario`, `registro`, `rotulo`); termos técnicos em inglês (`component`, `hook`, `props`) |
| **Textos visíveis ao usuário**, mensagens de erro e de validação | **Português brasileiro**; o grupo se chama **Equipe** e o papel se chama **Cargo** (no banco e no código, `grupo` e `cargo`) |
| **Comentários, README, `AI_NOTES.md`, este arquivo, PRs** | **Português brasileiro** |
| **Mensagens de commit** | **Inglês** (Conventional Commits) |

Regra de ouro: **o JSON de definição e o OpenAPI são contratos** com o `frontend/` (`campos`, `id`, `tipo`, `rotulo`, `unidade`, `casas_decimais`, `opcoes`, `compartilhado`, `formulario`, `exibicao`, `ia`, `obrigatorio`, `formula`). Não traduza nem renomeie por conveniência de um lado só (ver §5.3).

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
- **Número no JSON (fronteira):** na entrada a API aceita número JSON ou string e converte direto para `Decimal` (`Decimal(str(valor))`, nunca via `float`). Na saída da API e na coluna `dados` (`jsonb`), número vai **sempre como string** (`"25.50"`), porque número JSON vira `float` no JavaScript e perderia a precisão. Datas em ISO (`"2026-11-01"`). Contrato com o front (§5.3).
- **Casas decimais:** `casas_decimais` é opcional na definição do campo e orienta **só a exibição** (o front arredonda) e a **exportação CSV**, que sai arredondada com ele (campo sem `casas_decimais` sai com o valor completo). O `valor` guardado e devolvido mantém a precisão total, e as fórmulas sempre calculam sobre ela, nunca sobre o valor arredondado. Aceito em campos `numero` e em `calculado` cujo tipo inferido é numero; deve ser inteiro `>= 0`. Em outro tipo, ou com valor inválido, a publicação rejeita com mensagem clara.
- **Tipos na fórmula (checados ao publicar):** o avaliador infere o tipo de cada expressão sem executá-la. Tipos: `numero`, `data`, `booleano` e `duracao` (resultado de `dias(n)`). Campo `numero` → numero; `data` → data; `sim_nao` → booleano; `calculado` → tipo inferido da própria fórmula. Combinações aceitas:
  - `numero` com `+ - * / **` → numero; `soma`, `media`, `min` e `max` só sobre numero → numero.
  - `data + duracao` e `data - duracao` → data; `data - data` → numero (dias, `Decimal`).
  - `== != < <= > >=` entre dois numero ou duas data → booleano; entre dois booleano só `==` e `!=`.
  - `and`, `or` e `not` só sobre booleano.
  - `se(cond, a, b)`: `cond` booleano, `a` e `b` do mesmo tipo, resultado nesse tipo.
  - `dias(n)`: `n` numero → duracao.
  Qualquer outra combinação (`data * 2`, `data + data`, `data >= 3`, `duracao` como resultado final do campo) é **rejeitada ao publicar**, com mensagem e `posicao` na fórmula. Campos `texto`, `selecao`, `secao` e `localizacao` não podem ser referenciados em fórmulas (a allowlist não tem constante de texto); reavaliar se surgir a necessidade.
- **Formato do campo calculado no registro:** todo campo `calculado` é sempre `{"valor": ..., "erro": ...}`; campos de entrada continuam valor simples. Entrada vazia → `{"valor": null, "erro": null}` (ainda não dá para calcular); falha de execução → `{"valor": null, "erro": "mensagem em PT-BR"}`. Fórmula que depende de campo calculado com erro também fica com erro, citando o campo de origem. Este formato é contrato com o front (§5.3).
- Cobrir com testes: caminho feliz, cada operador, cada função, entradas vazias, divisão por zero, nó proibido, tentativa de injeção (`__import__('os')`, `().__class__`…), ciclo, dependência inexistente, cada combinação de tipos aceita e rejeitada (incluindo comparação entre datas), campo compartilhado vazio ou com erro na origem, ciclo entre formulários, cascata de recálculo.

---

## 8. TDD

TDD é a regra para o **núcleo**: `formulas.py`, `validacao.py`, `tipos_campo.py`, `servico.py` e `repositorio.py`.

1. **Red** — escreva o teste que falha primeiro.
2. **Green** — o mínimo de código para passar.
3. **Refactor** — melhore com a rede de segurança dos testes.

- Estilo: `pytest`, **Arrange / Act / Assert** explícito, um comportamento por teste, nome descritivo (`test_ciclo_entre_campos_e_rejeitado_ao_publicar`).
- Banco de teste: **PostgreSQL real** (o do `docker compose` localmente e um serviço no CI), com schema isolado por teste; nunca o banco de uso. O Postgres de teste usa a imagem com `pgvector`.
- **Autenticação e RBAC:** token de teste assinado com chaves geradas no próprio teste (nunca o Logto real); tabela de verdade de cada permissão contra cada endpoint; **testes de vazamento entre equipes** percorrendo todas as rotas que recebem id (grupo B contra recurso do grupo A → 404).
- API: `fastapi.testclient.TestClient` (via `httpx`).
- LLM: **sempre** substituído por um cliente falso nos testes. Nenhum teste faz chamada de rede nem exige chave.
- **Prioridade de cobertura:** `formulas.py` e `validacao.py` primeiro e mais fundo. É o que o autor vai defender em voz alta.
- Contrato: teste de API confere o formato de erro uniforme e que os campos dos modelos de resposta não mudaram sem querer (compare com o JSON esperado).
- Verificação manual: suba a API e exercite o fluxo em `/docs` (Swagger) ou `curl`, além dos testes.
- **Frontend:** Vitest + Testing Library para a lógica e os componentes (montagem da definição no construtor, `FormRenderer`, exibição de erros por campo). TDD vale para a lógica; tela puramente visual dispensa teste de snapshot. Como o front não tem regra de negócio, não há teste dela lá. Verificação manual: `npm run dev` com a API no ar, golden path + 1 caso de borda.
- **Ponta a ponta:** Playwright em viewport de celular e de desktop (login em desenvolvimento, criar formulário, preencher, filtrar, convidar), com verificação de acessibilidade e orçamento de desempenho no CI.
- **Segurança:** testes de injeção de SQL (nome e valor de filtro), do avaliador de fórmulas e de prompt injection no chatbot, com cliente falso.

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
- O roadmap da versão web está na issue #164 e nas filhas; cada uma traz o que mudar neste arquivo e no README quando for entregue.

---

## 11. Linha de corte

Se o tempo apertar, corte **nesta ordem**:

1. Sino de notificações e PWA
2. Chatbot sobre os dados (fica só a ajuda do app)
3. Resumo por IA
4. Gerador de formulário por IA
5. Assistente RAG
6. CLI além de migrar e importar
7. Exportação CSV
8. Endpoint de prévia de fórmulas (o front ainda calcula só ao salvar)

**Nunca cortar:** autenticação, isolamento entre equipes, permissões no servidor e aceite LGPD.

**Nunca cortar:** README, `AI_NOTES.md`, ensaio em voz alta e **testes de fórmulas e validação**.

---

### Pontos que o autor precisa saber defender

- **IA não calcula:** é onde ela erra (aritmética, valores inventados). O cálculo é de um avaliador determinístico e o resumo por IA é validado contra o banco.
- **Formulário é dado, não código:** definição em JSON versionado; registros apontam para a versão com que nasceram, então evoluir um formulário não quebra o histórico.
- **Fórmulas sem `eval`:** avaliador sobre `ast` com allowlist, porque executar texto digitado pelo usuário é falha de segurança. Ordem por dependência, ciclos rejeitados.
- **Servidor é a fonte da verdade:** valida e recalcula sempre; o cliente nunca é confiável.
- **Núcleo independente das interfaces:** API e CLI são camadas finas sobre `servico.py`.
- **Permissão e isolamento no servidor:** o cargo é lido do banco a cada requisição e toda consulta filtra por equipe; o que o front esconde é só conveniência. Tem teste de vazamento entre equipes.
- **Segredo certo para cada caso:** senha é do Logto (hash), token de convite é só hash, chave de LLM é cifrada porque precisa ser reutilizada.
- **Chatbot sem engolir os dados:** filtros no SQL, BM25 à mão e vetores só sobre o que sobrou; contagens e médias vêm de ferramentas determinísticas, e o LLM nunca gera SQL.
- **Framework só no encanamento** (FastAPI): o que se explica linha por linha (fórmulas, validação, versionamento, RAG) é código próprio.

---

## 12. Segurança

- **Rede:** o compose principal não publica porta; em desenvolvimento o override publica API, Logto, Postgres e Mailpit só no `127.0.0.1`. **Não há HTTPS no repositório** (sem proxy): não exponha o app na internet até haver um.
- **Autenticação:** JWT do Logto validado em todo endpoint (JWKS, `iss`, `aud`, `exp`); a equipe vem de `X-Equipe` e é conferida contra `membros_grupo`, token de 10 minutos (§2.12). Cargo e permissões vêm do banco a cada requisição, nunca do token nem do front.
- **Isolamento:** todo acesso filtra por `grupo_id`; recurso de outra equipe é 404; testes de vazamento por rota. Row Level Security no Postgres como defesa em profundidade, quando adotado.
- **SQL sempre parametrizado** (`%s`), sem f-string nem concatenação (regra `S608` do `ruff` e teste de varredura); usuário do banco da aplicação com privilégio mínimo (sem DDL; migrações com outro papel); `statement_timeout`.
- **Segredos:** a senha fica no Logto (hash); o token de convite só como hash SHA-256; a chave de LLM cifrada (Fernet) com chave-mestra só no ambiente e nunca devolvida pela API; chaves e `.env` nunca no frontend, no git, em imagem, em log nem em backup junto do dump.
- **Limites:** rate limit por pessoa e equipe nos endpoints caros (exportar, prévia de fórmulas, IA, convites), com 429 e `Retry-After`; corpo de no máximo 1 MB para JSON (413); timeouts do uvicorn contra conexão lenta; limites de recurso por contêiner. Limite por IP e `fail2ban` dependem de um proxy, que não existe hoje. Sem serviço de borda, **DDoS volumétrico não é coberto** (§2.9).
- **CORS** só para as origens configuradas, nunca `allow_origins=["*"]`; cabeçalhos de segurança (CSP restritiva, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` liberando só a geolocalização; CSP do front e HSTS ficam para o proxy que vier); `/docs` e `/openapi.json` fechados em produção.
- **IA:** saída do LLM é **dado não confiável**: valide contra o esquema esperado e contra o banco antes de exibir. Conteúdo de registro também é entrada não confiável (prompt injection). O LLM nunca gera SQL; campo `"ia": false` nunca é enviado; sem consentimento da equipe, nada é enviado.
- Texto vindo do usuário (rótulos, opções, valores) é tratado como dado, nunca executado; a API não devolve HTML e o front renderiza Markdown de forma segura.
- Exportação CSV: neutralizar células **de texto** iniciadas por `=`, `+`, `-`, `@`, tab ou `CR` (injeção de fórmula em planilha), prefixando com `'`. Não vale para números: um `Decimal` negativo (`-3,5`) começa com `-` e não pode ser corrompido, e número só entra no CSV via formatação de `Decimal`.
- **Logs** com identificador de requisição (`X-Request-Id`) e **sem dados pessoais**: `forms.acesso` grava uma linha por requisição com o **molde da rota** (nunca o caminho real, que pode ter id ou o token do convite), status e duração; sem e-mail, valores de campo, corpo, query string nem IP. O log de acesso do uvicorn fica desligado por imprimir o caminho real. Mapa de dados, retenção e plano de incidente: `docker/OPERACAO.md`.
- **PWA:** o service worker nunca cacheia resposta da API, token nem dados de equipe.
- LGPD: aceite, direitos do titular e consentimento para IA em §2.15.

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
- [ ] CI verde no PR (`.github/workflows/ci.yml` roda `uv sync --locked`, ruff check, ruff format --check e pytest, o pytest contra um Postgres de serviço, em Linux; o job do `frontend/` roda `npm ci`, lint, typecheck, testes e build). Se mudar dependência, commite `pyproject.toml` e `uv.lock` juntos
- [ ] **Testado manualmente** quando mexer em API/CLI: golden path + 1 caso de borda via `/docs` ou `curl` (testes não substituem ver funcionando)
- [ ] Contrato (OpenAPI / JSON de definição) inalterado ou mudança incompatível sinalizada (§5.3)
- [ ] Mudou o esquema do banco? Teste de atualização a partir do esquema anterior (§5.2)
- [ ] Nenhum `eval`/`exec`, nenhum SQL por concatenação (`ruff S608` verde), nenhum segredo no diff
- [ ] Mexeu em dados? **Todo acesso filtra por `grupo_id`** e há teste de vazamento entre equipes
- [ ] Mexeu em endpoint? A permissão está na matriz e testada por cargo
- [ ] Algo novo pode ir à IA? Respeita `"ia": false` e o consentimento da equipe
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
- Frontend: `frontend/` neste repositório (design de referência em `frontend/data-collect-design-pattern.pdf`)
- Logto: https://docs.logto.io · PostgreSQL: https://www.postgresql.org/docs · psycopg: https://www.psycopg.org/psycopg3/docs · pgvector: https://github.com/pgvector/pgvector
- React: https://react.dev · Vite: https://vite.dev · Tailwind: https://tailwindcss.com
