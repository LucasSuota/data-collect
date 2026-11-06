# src/forms

> Backend Python do data-collect: definições em JSON versionadas, validação, fórmulas, equipes com cargos e permissões, API autenticada e módulos opcionais de IA. Persistência em PostgreSQL com SQL à mão.

Este arquivo resume cada módulo (o que é, como se conecta, como testar). As **regras** e o alvo estão no [AGENTS.md](../../AGENTS.md); aqui está o que **existe** no código.

```
api/ , cli.py  →  servicos/  →  dominio/ (validacao, formulas, tipos_campo...), infra/segredos.py
                              →  repositorios/  →  infra/banco.py  →  psycopg  →  PostgreSQL
```

## dominio/models.py

### Responsabilidade
Tipos comuns do domínio e exceções de domínio. Não valida, não calcula e não faz I/O.

### O que tem aqui
| Símbolo | Papel |
|---|---|
| `TipoCampo` | `StrEnum` com os 9 valores de `tipo` do JSON de definição |
| `Campo`, `Definicao` | Definição de um formulário; `opcoes` é tupla e `Definicao.campos` também. `para_json()` dá a forma canônica do contrato (só o que não é padrão); `de_json()` lê uma definição **já validada**, como a do banco |
| `Formulario`, `Versao`, `Registro` | Linhas do banco como dataclasses imutáveis |
| `Posicao`, `ErroDeCampo` | Erro localizado `{campo, mensagem}` com `posicao` opcional na fórmula (AGENTS.md §5.3) |
| `ResultadoCalculado` | Formato `{valor, erro}` do campo calculado (AGENTS.md §7) |
| `ValorJson` | Alias de tipo para JSON arbitrário, no lugar de `Any` |
| `ErroDeDominio` | Base das exceções abaixo; `api.py` a traduz para HTTP |
| `FormulaInvalida` | Fórmula rejeitada, com `posicao` opcional |
| `DefinicaoInvalida`, `RegistroInvalido` | Carregam `erros: tuple[ErroDeCampo, ...]` |
| `CicloDeDependencia` | Subclasse de `DefinicaoInvalida`; cita os campos em `campos` |
| `Pasta` | Pasta da árvore que organiza formulários (§2.10); `Formulario.pasta_id` nulo = raiz |
| `PastaInvalida` | Nome vazio ou repetido, destino inexistente ou ciclo; carrega `erros` como `RegistroInvalido` |
| `ValorInvalido` | Um valor isolado não serve para o tipo do campo (levantada por `tipos_campo.py`) |
| `ErroDeCalculo` | Falha ao executar uma fórmula válida; `calcular_campos` a guarda no campo |
| `LoteInvalido`, `ErrosDoFormulario` | Erros agrupados por formulário quando um lote é recusado (nada é criado) |
| `NaoEncontrado`, `ExclusaoBloqueada` | Recurso inexistente (404) e exclusão bloqueada por vínculo (409) |

### Como se conecta
- **Depende de:** só da biblioteca padrão (`dataclasses`, `enum`).
- **É usado por:** nenhum módulo ainda; é a base de todo o núcleo.

### Decisões que moldam este código
- Dataclasses `frozen=True`; `Registro.dados` é um `dict` e portanto mutável por dentro (AGENTS.md §9).
- `CicloDeDependencia` é uma `DefinicaoInvalida`, para virar 422 sem tratamento à parte (AGENTS.md §5.3).
- Os nomes dos atributos de `Campo` espelham as chaves do JSON de definição, que é contrato com o front (AGENTS.md §6).

### Como testar
`uv run pytest tests/test_models.py`

### Cuidados
- Não importar nenhuma outra camada do projeto aqui; um teste confere isso.
- Renomear atributo de `Campo` ou de `ErroDeCampo` quebra o contrato com o `frontend/`.

## dominio/formulas.py

### Responsabilidade
Tudo sobre fórmulas, sem I/O: ler o texto e verificar a árvore, inferir tipos ao publicar, achar a ordem de cálculo e avaliar com `Decimal`. Não conhece registro, banco nem API. Quem monta os tipos dos campos e os valores de entrada é a validação e o serviço.

### O que tem aqui
| Símbolo | Papel |
|---|---|
| `analisar_formula(texto)` / `carregar_formula(texto)` | `ast.parse` em modo `eval` + allowlist de nós, aridade e profundidade; `carregar_formula` devolve `Formula` (texto + árvore) |
| `FUNCOES`, `CONSTANTES`, `NOMES_RESERVADOS` | A tabela única de funções (assinatura, descrição, exemplo, aridade, regra de tipo, implementação), `pi` e os nomes que nenhum `id` pode ter |
| `inferir_tipo(formula, tipos, nao_utilizaveis)` | Tipo do resultado (`numero`, `data`, `booleano`) sem executar; `duracao` só aparece no meio |
| `nomes_usados(formula)` | Campos usados, na ordem do texto, sem funções nem `pi` |
| `ordenar_calculados(dependencias)` | Ordem topológica determinística; ciclo (inclusive auto-referência) levanta `CicloDeDependencia` |
| `avaliar(formula, valores)` | Calcula uma fórmula; falha vira `ErroDeCalculo` em PT-BR |
| `calcular_campos(campos, entradas, compartilhados)` | A única função de cálculo: devolve `{valor, erro}` de cada `calculado` (salvar e prévia usam esta) |
| `ValorDeCampo` | Valor tipado de um campo compartilhado, com o erro da origem |

### Como se conecta
- **Depende de:** biblioteca padrão e `forms.models`.
- **É usado por:** nenhum módulo ainda.

### Decisões que moldam este código
- Allowlist de nós: constante numérica ou booleana, nome, `+ - * / **`, `-` e `not` unários, `and`/`or`, comparação simples e chamada às funções da tabela (AGENTS.md §7).
- Vazio propaga em tudo: todos os operandos são avaliados, e qualquer vazio torna o resultado vazio, até em `and`/`or` e nas funções. A exceção é `se`, que avalia só o ramo escolhido.
- Aritmética em contexto `Decimal` fixo (precisão 28, divisão por zero e estouro viram exceção). `pi` tem 28 dígitos.
- Constantes como `0.1` viram `Decimal` pelo texto original, nunca pelo `float`. Resultado não finito (`0 ** -1`) vira erro de cálculo.
- Teto de 150 níveis de aninhamento no parse: garante que inferência e avaliação, recursivas, não estourem a pilha.
- `casas_decimais` não entra aqui: o valor guardado mantém a precisão total (AGENTS.md §7).

### Como testar
`uv run pytest tests/test_formulas*.py`

### Cuidados
- Nunca chamar `eval`, `exec`, `compile` nem `__import__`; um teste confere o fonte.
- `TipoFormula` é `StrEnum` e portanto também é `str`: não distinga tipo de mensagem com `isinstance(x, str)`.
- Mudar `FUNCOES` muda o parser, a inferência, o avaliador e o catálogo ao mesmo tempo, de propósito.
- Este arquivo ficou grande (parse, tipos, grafo e avaliação). Se crescer mais, dividir é a próxima refatoração.

## dominio/tipos_campo.py

### Responsabilidade
Dizer o que cada tipo de campo aceita, validar e normalizar um valor isolado. Não olha o registro inteiro (isso é da validação) e não calcula fórmulas.

### O que tem aqui
| Símbolo | Papel |
|---|---|
| `eh_vazio(valor)` | Regra única de vazio: `None` ou string vazia. Zero, `False` e espaço não são vazios |
| `normalizar_valor(campo, valor)` | Devolve o valor tipado (`Decimal`, `date`, `str`, `bool`) ou `None` se vazio; levanta `ValorInvalido` |
| `valor_para_json(valor)` | Volta ao formato guardado: número e data como string |
| `ESPECIFICACOES`, `especificacao_do_tipo(nome)` | Tabela dos 10 tipos com rótulo em PT-BR e propriedades aceitas; base do `GET /catalogo` |
| `PROPRIEDADES_COMUNS` | `id`, `tipo` e `rotulo`, que todo campo tem |

### Como se conecta
- **Depende de:** `forms.models` (`Campo`, `TipoCampo`, `ValorInvalido`, `ValorJson`).
- **É usado por:** nenhum módulo ainda.

### Decisões que moldam este código
- Número nunca passa por `float`: `0.1` vira `Decimal("0.1")` pelo texto do float (AGENTS.md §7).
- A string de número é conferida por regex ASCII antes do `Decimal`, que aceitaria `NaN`, `1_000` e dígitos de outros alfabetos.
- A data é só `AAAA-MM-DD`; `date.fromisoformat` sozinho aceitaria também `20261101` e `2026-W44-1`.
- Texto, número, data, seleção, sim/não, localização e referência são normalizados aqui. Calculado e seção nunca recebem valor do cliente. Referência confere só o formato (inteiro positivo); a existência do registro é do serviço.
- Localização vira `Localizacao(latitude, longitude)` em `Decimal`, com faixa -90 a 90 e -180 a 180; um sem o outro é erro.

### Como testar
`uv run pytest tests/test_tipos_campo.py`

### Cuidados
- `bool` é subclasse de `int`: o número rejeita `true`/`false` de propósito.
- Mudar o rótulo ou as propriedades de um tipo muda o catálogo que o front lê.

## dominio/validacao.py

### Responsabilidade
Validar uma definição de formulário e um registro contra ela, devolvendo **todos** os erros de uma vez, localizados pelo `id` do campo (AGENTS.md §5.3). Não calcula (isso é de `formulas.py`), não normaliza valor isolado (isso é de `tipos_campo.py`) e não faz I/O: o que viria do banco entra por parâmetro.

### O que tem aqui
| Símbolo | Papel |
|---|---|
| `analisar_definicao(dados, origens)` | Lê o JSON não confiável e devolve `AnaliseDeDefinicao`: `erros`, `definicao` (só se não houver erro) e `tipos_calculados` |
| `validar_definicao(dados, origens)` | Só a tupla de erros; é o que `/definicoes/validar` vai usar |
| `exigir_definicao_valida(dados, origens)` | Para publicar: devolve `Definicao` ou levanta `DefinicaoInvalida` com todos os erros |
| `CampoCompartilhado`, `Origens` | O que cada formulário de origem libera (tipo e tipo na fórmula), recebido por parâmetro |
| `validar_registro(definicao, dados)` | Devolve `ValidacaoDeRegistro`: `erros` por `id` e `valores` já normalizados (`Decimal`, `date`...) |

### Como se conecta
- **Depende de:** `forms.formulas` (parse, tipos, ordem), `forms.tipos_campo` e `forms.models`.
- **É usado por:** nenhum módulo ainda.

### Decisões que moldam este código
- Localização do erro: `id.propriedade`; quando o problema é o próprio `id` (ausente, duplicado, reservado, inválido) usa o índice, `campos[3].id`; erro global usa `campos` (AGENTS.md §5.3).
- O `id` deve casar com `[A-Za-z_][A-Za-z0-9_]*`: ele vira nome em fórmula, e `meu-campo` seria lido como subtração. É uma regra a mais que o AGENTS.md não cita.
- Propriedade que o tipo não aceita é erro, não é ignorada: um `"obrigatório"` com acento não pode sumir em silêncio.
- Campo `calculado` com erro de fórmula não gera erro em cascata nos que dependem dele; só a origem é apontada.
- Chave de campo calculado, de seção ou inexistente no registro é erro (aceitar e ignorar esconderia bug no front). Erro de cálculo nunca passa por aqui (AGENTS.md §7).

### Como testar
`uv run pytest tests/test_validacao_definicao.py tests/test_validacao_registro.py`

### Cuidados
- `tipos_calculados` é a base da regra de contrato dos compartilhados (nova versão da origem não pode mudar o tipo inferido).
- `compartilhados_da_definicao` entrega o que o formulário libera aos dependentes; ciclo entre *formulários* e o contrato entre versões são do serviço, que conhece os outros formulários.

## infra/banco.py e infra/migracoes/

### Responsabilidade
A conexão com o PostgreSQL e o esquema versionado. `Conexao` (subclasse de `psycopg.Connection`) carrega o **contexto da requisição** (`grupo_id`, `usuario_id`, permissões) e o declara no banco: `definir_contexto` grava `app.grupo_id`, que o Row Level Security lê.

### O que tem aqui
| Símbolo | Papel |
|---|---|
| `abrir_conexao`, `criar_pool` | Conexão avulsa (CLI, migração, testes) e pool da API (uma conexão por requisição). `criar_pool(papel=...)` faz `SET ROLE`: os testes da API assumem `forms_app` |
| `migrar`, `Migracao` | Aplica `migracoes/NNNN_*.sql` em ordem, com `pg_advisory_lock` e a tabela `esquema_versao`. Recusa banco mais novo que o código (`EsquemaMaisNovo`) |
| `0001_nucleo.sql`, `0002_ia.sql`, `0003_extras.sql` | Esquema, Row Level Security (em `cargos`, `pastas`, `formularios`, `versoes_formulario`, `rascunhos_formulario`, `registros`, `historico_registro`, `dependencias_formulario`, `referencias_registro`) e as permissões do papel `forms_app` |

### Cuidados
- **RLS e o papel do dono:** o superusuário ignora o Row Level Security. Toda consulta que lê uma tabela com RLS antes de a equipe ser declarada vê **zero linhas** no papel `forms_app`: foi assim que o convite "sumia" e a única administradora conseguia excluir a conta. Use `servico_equipes.declarar_equipe` ao ler `cargos` fora do contexto de uma equipe.
- Toda mudança de esquema exige teste de atualização a partir do esquema anterior (`tests/test_banco.py`).

### Como testar
`docker compose up -d postgres` e `uv run pytest tests/test_banco.py` (Postgres real em `127.0.0.1:5433`, ou `FORMS_TEST_DSN`).

## repositorios/ (formularios.py, equipes.py, extras.py)

### Responsabilidade
**Único** lugar que fala SQL, sempre com parâmetros (`%s`); identificador dinâmico só com `psycopg.sql`. Todo método de dados da equipe recebe o `grupo_id` e o aplica na consulta (e o RLS repete a barreira no banco). Sem ORM.

### O que tem aqui
| Arquivo | Papel |
|---|---|
| `repositorio.py` | Formulários, versões, rascunhos, pastas, registros (com `revisao`, autoria e histórico), referências, dependências, busca e contagem por estado |
| `repositorios/equipes.py` | Pessoas, equipes, membros, cargos e permissões, convites (token só como hash) e consentimentos |
| `repositorios/extras.py` | Notificações, progresso do passeio e os dados que a busca global e o Início usam |

### Como testar
`uv run pytest tests/test_repositorio_*.py tests/test_sql_seguro.py` (o segundo varre o código: SQL por f-string ou `%` é rejeitado; exceção só com `noqa` e justificativa na linha).

## infra/segredos.py, dominio/permissoes.py, infra/legal.py, infra/ajuda.py

| Arquivo | Papel |
|---|---|
| `segredos.py` | **Único** lugar com criptografia: `hash_do_token` (SHA-256), comparação em tempo constante e Fernet para a chave de LLM de cada equipe |
| `permissoes.py` (dominio) | As 17 permissões e os cargos de partida |
| `api/matriz_permissoes.py` | A **matriz endpoint → permissão** (uma tabela só, usada pela API e por `GET /catalogo/permissoes`) |
| `legal.py` | Lê `legal/*.md` (a primeira linha traz a `versao:`): é a versão que o aceite LGPD compara |
| `ajuda.py` | Lê os guias de `ajuda/*.md` (central de ajuda e base do chatbot) |

## servicos/ (servico.py e um arquivo por assunto)

### Responsabilidade
Os casos de uso, chamados igualmente por `api*.py` e `cli.py`. Toda regra de negócio fica aqui e abaixo. Recebe a conexão (com o contexto: equipe, pessoa, permissões) e o relógio (`agora`) por parâmetro, controla a transação e não conhece HTTP.

### O que tem aqui
| Arquivo | Papel |
|---|---|
| `servico.py` | Fachada: formulários e versões (criar, publicar, lote, duplicar, validar, catálogo) e reexportação de todo o resto, então a API chama `servico.<função>` |
| `servicos/base.py` | Transação (`conexao.transaction()`), campos compartilhados dos formulários publicados e o `Cache` de uma operação |
| `servicos/registros.py` | Criar, atualizar (com `revisao`, histórico e cascata), excluir registro, excluir formulário e prévia |
| `servicos/rascunhos.py` | Rascunho compartilhado da próxima versão (salvar com `revisao`, publicar, descartar) |
| `servicos/pastas.py` | Pastas e subpastas e mover formulário |
| `servicos/consulta.py` | Listagem com colunas da definição, filtros, `meus`, paginação, contagens por estado e exportação CSV |
| `servicos/equipes.py` | Pessoas, equipes, cargos, convites, consentimentos e o contexto da requisição (`contexto_da_pessoa`, `declarar_equipe`) |
| `servicos/extras.py` | Início (recentes com estado), busca global, notificações, passeio, exportar e excluir os dados da pessoa (LGPD) |
| `servicos/importacao.py` | Importar o `forms.db` antigo (SQLite) e a galeria de exemplos (`templates/`) |

### Decisões que moldam este código
- Publicar um formulário, uma versão, um rascunho e um lote usam **o mesmo motor** de validação: mensagens e posições são idênticas.
- O registro nasce numa versão **explícita** e é sempre validado e recalculado contra ela; editar não muda a versão. O `PUT` exige a `revisao` lida (409 se outra pessoa salvou antes).
- Uma só função de cálculo (`formulas.calcular_campos`) serve ao salvar, à cascata e à prévia. A cascata roda na mesma transação, e erro de cálculo vira erro no campo.
- **Ninguém dá o que não tem:** convite, cargo e permissão acima do próprio são recusados; sempre existe ao menos uma administradora ativa.
- O filtro da listagem só aceita igualdade em campos `selecao`, `sim_nao`, `texto` e `calculado` booleano; o nome do campo vem de uma allowlist derivada da definição.

### Como testar
`uv run pytest tests/test_servico_*.py tests/test_rascunhos.py tests/test_exportacao.py`

## api/auth.py, infra/logto.py e infra/provisionar_logto.py

| Arquivo | Papel |
|---|---|
| `auth.py` | `ValidadorDeToken`: assinatura pelo JWKS do Logto (só algoritmos assimétricos), `iss`, `aud` e `exp`. O `iss` é o endereço público; as chaves vêm do endereço interno (`LOGTO_INTERNO`). Cargo e permissões **não** vêm do token |
| `logto.py` | Cliente mínimo da Management API (M2M): ler o perfil de quem entra e apagar a conta (LGPD). O segredo nunca aparece em `repr` nem em log |
| `provisionar_logto.py` | `python -m forms.provisionar_logto` (serviço `logto-setup` do compose): cria ou atualiza, de forma idempotente, o API resource (token de 10 minutos), o aplicativo SPA (refresh rotativo), o aplicativo M2M da API, o conector SMTP e a tela de login; escreve `api.env` e `frontend-config.json` |

### Cuidados
- O Logto escolhe o tenant pelo **host** da requisição: o token do `m-default` só sai de `localhost:3002` (o provisionador envia esse `Host`).
- Testes: `uv run pytest tests/test_provisionar_logto.py tests/test_api/seguranca.py` (o Logto real nunca é usado nos testes; o token é assinado com chaves geradas no teste).

## api/ (app.py, rotas_*.py, esquemas.py...)

### Responsabilidade
A fronteira HTTP. Traduz JSON em chamadas ao `servico` e exceções de domínio em status HTTP. **Nenhuma regra de negócio.** Pydantic só existe aqui.

### O que tem aqui
| Arquivo | Papel |
|---|---|
| `api.py` | `criar_app(Configuracao)`, `app_do_ambiente` (fábrica do uvicorn), CORS, cabeçalhos de segurança, limite de corpo (413), tratadores de erro e o primeiro administrador (`FORMS_ADMIN_EMAIL`) |
| `api/dependencias.py` | Autenticação e contexto por requisição: identifica a pessoa, valida `X-Equipe` contra `membros_grupo`, lê o cargo do banco, exige os termos e confere a permissão da matriz |
| `api/seguranca.py` | Limite de requisições por pessoa e por equipe nos endpoints caros (429 com `Retry-After`) |
| `api/esquemas.py` | Modelos Pydantic de entrada e saída; nomes e campos são o contrato com o front |
| `rotas_formularios.py`, `rotas_equipes.py`, `rotas_extras.py`, `matriz_permissoes.py` | Os endpoints: formulários e registros, equipes/cargos/convites, Início/busca/notificações/LGPD e o catálogo de permissões |
| `api/extensoes.py` | `descobrir_extensoes()`: monta as rotas de `ia/` e `rag/` **pelo nome**, em execução, sem o núcleo importá-los |
| `exportar_openapi.py` | `forms-openapi`: grava o `openapi.json` do front; `--conferir` falha se estiver desatualizado |

### Configuração (variáveis de ambiente, ver `.env.example`)
`FORMS_DATABASE_URL` (papel `forms_app`), `FORMS_MIGRATION_URL` (dono, só para migrar), `FORMS_CORS_ORIGINS`, `LOGTO_ENDPOINT` (público), `LOGTO_INTERNO`, `LOGTO_API_RESOURCE`, `LOGTO_M2M_ID`/`LOGTO_M2M_SECRET`, `FORMS_AMBIENTE`, `FORMS_ADMIN_EMAIL`, `FORMS_EQUIPE_INICIAL`, `FORMS_CHAVE_MESTRA`.

### Decisões que moldam este código
- Erro uniforme `{detalhe, erros, codigo}` em português, inclusive nos erros do Pydantic, 404/405 e 500 (sem vazar a causa). 401 com `token_expirado` só quando expirou; 403 com `termos_pendentes`, `sem_equipe` ou `sem_permissao`; 409 em `revisao_desatualizada`.
- **Falha fechada:** sem Logto configurado, toda chamada autenticada é recusada. Recurso de outra equipe é 404, nunca 403.
- CORS só para as origens configuradas; `*` é recusado na configuração. `/docs` e `/openapi.json` ficam fechados em produção.
- Mudar nome ou campo de um modelo de resposta, ou o conjunto de rotas, é **mudança incompatível** com o `frontend/`: `tests/test_api_contrato.py` falha de propósito (regenere o contrato quando a mudança for intencional).

### Como testar
`uv run pytest tests/test_api*.py` (a fixture sobe a API com o pool no papel `forms_app` e token de teste).

## cli.py

CLI de **operação** (`argparse`, só chama `servico.py`; nenhuma regra de negócio): `forms migrar`, `forms importar-template`, `forms importar-sqlite` (traz o `forms.db` antigo), `forms reindexar` (IA), `forms criar-registro`, `forms listar` e `forms exportar`. Sempre com `--equipe` e `--usuario` explícitos: a CLI é para quem administra o servidor, não um caminho para furar permissões. Teste: `uv run pytest tests/test_cli.py tests/test_importacao_sqlite.py`.

## dominio/exportacao.py

Funções puras que formatam as células e geram o CSV para o Excel em português (UTF-8 com BOM, `;`, vírgula decimal; números arredondados por `casas_decimais`; células de texto que começam por `=`, `+`, `-`, `@`, tab ou CR recebem `'`). Teste: `uv run pytest tests/test_exportacao.py`.

## ia/ — opcional

### Responsabilidade
Tudo que usa um LLM, atrás de uma interface neutra de provedor. A IA só redige e escolhe ferramentas; quem calcula e valida é código determinístico (AGENTS.md §2.5, §3.3). O app inteiro funciona com esta pasta removida.

### O que tem aqui
| Arquivo | Papel |
|---|---|
| `cliente.py` | O **único** lugar que importa SDK ou fala com provedor: `ProvedorDeLLM` (completar, streaming, vetorizar, ferramentas, `capacidades`), adaptadores para a Anthropic e para APIs compatíveis com OpenAI (`httpx`) e um cliente falso para testes |
| `configuracao.py` | Provedor por equipe (`base_url`, modelo, embeddings), chave cifrada em repouso e nunca devolvida, aviso e aceite, limites de uso por pessoa e por equipe |
| `indexacao.py` | Registros e definições como documentos de texto por equipe (`documentos_ia`), reindexação incremental; campo com `"ia": false` e `localizacao` nunca entram |
| `busca.py` | Busca híbrida: filtros no SQL, BM25 à mão e `pgvector` (com modelo e dimensão guardados) fundidos por RRF; sem embeddings vale só filtro + BM25 |
| `ferramentas.py` | `buscar_registros`, `contar_registros`, `valor_do_campo` e `agregar`: o LLM só escolhe a ferramenta e os argumentos, **validados contra a definição**; nunca gera SQL |
| `chat.py` | `POST /chat` (SSE): responde com citações; todo número do texto é conferido contra o resultado das ferramentas; conteúdo de registro entra como bloco delimitado (prompt injection) |
| `gerador.py`, `resumo.py`, `validacao.py` | Gerador de formulários (validado como a publicação, no máximo 2 correções) e resumo conferido número a número |
| `repositorio.py`, `extensao.py` | SQL das tabelas de IA e as rotas (descobertas por nome) |

### Cuidados
- **Nenhuma chamada a um LLM real foi feita**: os adaptadores foram escritos contra a documentação, e a primeira chamada real pode pedir ajustes (nome do modelo, formato da resposta, chamada de ferramenta).
- Sem IA (equipe com a IA desligada, sem chave ou sem internet), o chat devolve só os trechos e resultados; as rotas de geração respondem 503 em português.

### Como testar
`uv run pytest tests/test_ia_*.py tests/test_api_ia*.py`. Nenhum teste faz chamada de rede nem exige chave.

## rag/ — opcional

O assistente de procedimentos: `chunker.py` divide os `.md` em trechos, `indice.py` tem o BM25 escrito à mão, `semantico.py` e `responder.py` fazem a busca semântica opcional e a resposta **só com os trechos**, e `extensao.py` monta a rota e escolhe o provedor da equipe e a pasta dos guias (`FORMS_AJUDA_DIR`). Sem base nos documentos, responde "não encontrei". Teste: `uv run pytest tests/test_rag*.py`.
