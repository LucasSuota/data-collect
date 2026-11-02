# src/forms

> Backend Python do construtor de formulários: definições em JSON versionadas, validação, fórmulas e persistência em SQLite.

Hoje existem `models.py`, `formulas.py`, `tipos_campo.py`, `validacao.py`, `repositorio.py`, `fotos.py`, `exportacao.py`, `cli.py`, `app.py`, `api.py` (com `api_esquemas.py`, `api_rotas.py`, `api_extensoes.py` e `exportar_openapi.py`), os módulos `servico*.py` e os pacotes opcionais `ia/` e `rag/` (últimas seções).

## models.py

### Responsabilidade
Tipos comuns do domínio e exceções de domínio. Não valida, não calcula e não faz I/O.

### O que tem aqui
| Símbolo | Papel |
|---|---|
| `TipoCampo` | `StrEnum` com os 10 valores de `tipo` do JSON de definição |
| `Campo`, `Definicao` | Definição de um formulário; `opcoes` é tupla e `Definicao.campos` também. `para_json()` dá a forma canônica do contrato (só o que não é padrão); `de_json()` lê uma definição **já validada**, como a do banco |
| `Formulario`, `Versao`, `Registro` | Linhas do banco como dataclasses imutáveis |
| `Posicao`, `ErroDeCampo` | Erro localizado `{campo, mensagem}` com `posicao` opcional na fórmula (AGENTS.md §5.3) |
| `ResultadoCalculado` | Formato `{valor, erro}` do campo calculado (AGENTS.md §7) |
| `ValorJson` | Alias de tipo para JSON arbitrário, no lugar de `Any` |
| `ErroDeDominio` | Base das exceções abaixo; `api.py` a traduz para HTTP |
| `FormulaInvalida` | Fórmula rejeitada, com `posicao` opcional |
| `DefinicaoInvalida`, `RegistroInvalido` | Carregam `erros: tuple[ErroDeCampo, ...]` |
| `CicloDeDependencia` | Subclasse de `DefinicaoInvalida`; cita os campos em `campos` |
| `ValorInvalido` | Um valor isolado não serve para o tipo do campo (levantada por `tipos_campo.py`) |
| `FotoInvalida` | Imagem recusada; a mensagem já traz o motivo em PT-BR (levantada por `fotos.py`) |
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

## formulas.py

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

## tipos_campo.py

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
- Texto, número, data, seleção, sim/não, localização, foto e referência são normalizados aqui. Calculado e seção nunca recebem valor do cliente. Referência confere só o formato (inteiro positivo); a existência do registro é do serviço.
- Localização vira `Localizacao(latitude, longitude)` em `Decimal`, com faixa -90 a 90 e -180 a 180; um sem o outro é erro. Foto é a lista de ids de anexo, sem repetição e até `maximo`.

### Como testar
`uv run pytest tests/test_tipos_campo.py`

### Cuidados
- `bool` é subclasse de `int`: o número rejeita `true`/`false` de propósito.
- Mudar o rótulo ou as propriedades de um tipo muda o catálogo que o front lê.

## repositorio.py

### Responsabilidade
Único módulo que fala SQL (sempre com `?`). Guarda e devolve formulários, versões, registros, relações e metadados de anexos como dataclasses do `models.py`. Não valida regra de negócio, não decide exclusão (só o banco recusa o que viola chave estrangeira) e não faz commit.

### O que tem aqui
| Símbolo | Papel |
|---|---|
| `abrir_conexao`, `migrar`, `MIGRACOES` | Conexão com `foreign_keys` ligado e esquema migrado por `PRAGMA user_version`; cada migração é transacional |
| `criar_formulario`, `obter_formulario(_por_nome)`, `listar_formularios`, `excluir_formulario` | Nome único sem diferenciar caixa, espaços nas pontas nem a forma dos acentos (`chave_do_nome`); nome repetido levanta `DefinicaoInvalida` no campo `nome` |
| `inserir_versao`, `obter_versao(_atual)`, `listar_versoes` | Versões imutáveis: não há `update` nem `delete` de versão. O número é o anterior + 1, calculado no próprio `INSERT` |
| `inserir_`/`atualizar_`/`obter_`/`excluir_registro`, `listar_registros` | Dados em JSON; listagem por versão, do mais recente ao mais antigo, com `total`, `FiltroDeIgualdade` e janela de datas |
| `registrar_dependencias`, `listar_dependencias`, `formularios_dependentes` | Dependência entre formulários, direta ou transitiva |
| `substituir_referencias`, `obter_referencias`, `registros_que_referenciam`, `registros_dependentes` | Referências entre registros; os dependentes vêm na ordem de recálculo da cascata |
| `criar_anexo`, `vincular_`/`desvincular_`/`apagar_anexo`, `listar_anexos_do_registro`, `listar_anexos_orfaos` | Metadados das fotos; `caminho` sempre com `/` e relativo à pasta de dados |
| `listar_vetores`, `guardar_vetores`, `apagar_vetores` | Embeddings dos trechos dos procedimentos (BLOB), usados só pela busca semântica do `rag/` |

### Como se conecta
- **Depende de:** `sqlite3` e `forms.models`.
- **É usado por:** nenhum módulo ainda.
- **Contratos e dados:** as seis tabelas de AGENTS.md §5.2 mais `vetores_trechos` (busca semântica, opcional), na versão 3 do esquema.

### Decisões que moldam este código
- O relógio entra por parâmetro (`agora`, em UTC); o módulo nunca lê a hora. Todas as datas usam o mesmo formato ISO, então comparar texto é comparar tempo.
- A transação é de quem chama: as funções não fazem commit, para a cascata de recálculo entrar ou sair inteira (AGENTS.md §2.7).
- Filtro: o nome do campo precisa estar em `campos_permitidos` (calculado pelo serviço a partir da definição) **e** ter formato de identificador; o caminho JSON e o valor vão como parâmetro (AGENTS.md §2.3 e §12).
- Exclusões já são bloqueadas no banco (sem `ON DELETE`, o SQLite recusa), além da checagem do serviço (AGENTS.md §2.7).
- Migração num `BEGIN` explícito: sem ele o `sqlite3` não abre transação para DDL. A migração 2 (`nome_chave`) calcula a chave em Python porque o `lower()` do SQLite só entende ASCII.

### Como testar
`uv run pytest tests/test_repositorio_*.py`

### Cuidados
- Nunca edite uma migração já publicada (o banco do usuário persiste); acrescente outra. Um teste compara a migração 1 com o esquema publicado, escrito literalmente; outros atualizam um banco real da v1 para a v2 e da v2 para a v3 (a tabela de vetores) sem perder dados.
- Toda mudança de esquema exige teste de atualização a partir do esquema anterior (AGENTS.md §5.2).
- `PRAGMA user_version` não aceita `?`; o número vem de um `int` interno, nunca de texto externo.
- `listar_registros` exige `campos_permitidos` para qualquer filtro: sem a allowlist, o filtro é recusado.

## fotos.py

### Responsabilidade
Transformar a foto enviada num WebP pequeno e sem metadados (AGENTS.md §2.8). Função pura de bytes para bytes: não lê nem grava arquivo, não guarda o original e não conhece registro, campo nem anexo (isso é do `servico.py`).

### O que tem aqui
| Símbolo | Papel |
|---|---|
| `processar_foto(dados)` | Valida, orienta, remove metadados e comprime; devolve `FotoProcessada` ou levanta `FotoInvalida` |
| `FotoProcessada` | `dados` (WebP), `largura`, `altura` e `tamanho_bytes` |
| Constantes (`TAMANHO_MAXIMO_SAIDA`, `LADO_MAIOR_INICIAL`, `QUALIDADE_INICIAL`...) | Parâmetros do algoritmo, nomeados no módulo |

### Como se conecta
- **Depende de:** `Pillow` (dependência nova, só para decodificar, converter e remover EXIF) e `forms.models` (`FotoInvalida`).
- **É usado por:** nenhum módulo ainda.

### Decisões que moldam este código
- Formato reconhecido pelo conteúdo (`Image.open(..., formats=[...])`), nunca pela extensão. HEIC tem mensagem própria.
- Tamanho e número de pixels são conferidos antes de decodificar (AGENTS.md §12).
- Remover metadados = copiar os pixels para uma imagem nova, que não herda `info` (EXIF, XMP, ICC, textos do PNG).
- Transparência vira fundo branco; `convert("RGB")` deixaria o transparente preto.
- O algoritmo persegue só o teto de 80 KB; os 50 KB são alvo típico, não piso. A qualidade desce de 5 em 5 antes de reduzir as dimensões em 15%.

### Como testar
`uv run pytest tests/test_fotos.py` (leva alguns segundos: o pior caso é um ruído grande).

### Cuidados
- O perfil de cor é descartado sem conversão para sRGB; fotos em Display P3 podem ficar um pouco menos saturadas.
- Imagem animada (GIF não entra; WebP/PNG animados) usa só o primeiro quadro.

## validacao.py

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

## servico.py (e servico_*.py)

### Responsabilidade
Os casos de uso, chamados igualmente por `api.py` e `cli.py`. Toda regra de negócio fica aqui e abaixo. Recebe a conexão e o relógio (`agora`) por parâmetro, controla a transação (cada caso de uso grava tudo ou nada) e não conhece HTTP.

### O que tem aqui
| Arquivo | Papel |
|---|---|
| `servico.py` | Fachada: formulários e versões (criar, publicar, lote, validar, catálogo, importar template) e reexportação de todo o resto, então a API chama `servico.<função>` |
| `servico_base.py` | Transação (`transacao`), campos compartilhados dos formulários publicados e o `Cache` de uma operação |
| `servico_registros.py` | Criar, atualizar (com cascata), excluir registro, excluir formulário e prévia |
| `servico_anexos.py` | Upload de foto em duas etapas, leitura do WebP, limpeza de órfãos e os arquivos da pasta de dados |
| `servico_consulta.py` | Listagem com colunas da definição, filtros, paginação e exportação CSV |

### Como se conecta
- **Depende de:** `repositorio`, `validacao`, `formulas`, `tipos_campo`, `fotos`, `exportacao` e `models`.
- **É usado por:** `cli.py` e `api_rotas.py`/`api.py`.

### Decisões que moldam este código
- Publicar um formulário, uma versão e um lote usam **o mesmo motor** (`_validar_conjunto`): um formulário é o conjunto de 1, então mensagens e posições são idênticas.
- O registro nasce numa versão **explícita** e é sempre validado e recalculado contra ela; editar não muda a versão (AGENTS.md §5.2).
- Uma só função de cálculo (`formulas.calcular_campos`) serve ao salvar, à cascata e à prévia.
- Cascata (§2.7): atualizar uma origem recalcula os dependentes transitivos **na mesma transação**, cada um contra a sua versão; erro de cálculo vira erro no campo e só falha de infraestrutura desfaz tudo. Quem não mudou não é regravado.
- Arquivo de foto só é apagado **depois** do commit; falha antes dele preserva o arquivo. O caminho guardado é conferido para nunca sair da pasta de dados.
- A prévia trata vazio e valor pela metade como vazio: não reclama de obrigatório (isso é do salvar).
- O filtro só aceita igualdade em `selecao`, `sim_nao`, `texto` e `calculado` booleano; o nome do campo vem de uma allowlist derivada da definição.

### Como testar
`uv run pytest tests/test_servico_*.py tests/test_exportacao.py`

### Cuidados
- `transacao` usa `BEGIN` explícito e não aceita ser chamada com uma transação já aberta: quem chama não deve deixar uma aberta.
- Os campos compartilhados de uma origem e o tipo inferido de um `calculado` são recalculados reanalisando a definição publicada (não são guardados); `Cache` evita repetir isso dentro de uma operação.
- A exportação CSV é a primeira candidata a corte se o tempo apertar (AGENTS.md §11).

## cli.py

### Responsabilidade
Linha de comando enxuta sobre o `servico`: importar template, criar registro a partir de JSON, listar e exportar. Só `argparse` e impressão; **nenhuma regra de negócio** (um teste confere que não importa repositório, validação, fórmulas nem `sqlite3`).

### O que tem aqui
| Comando | Papel |
|---|---|
| `forms importar-template ARQUIVO... [--nome N]` | Cria formulários a partir de JSON; vários de uma vez entram em lote, em qualquer ordem |
| `forms criar-registro FORMULARIO --dados ARQUIVO\|- [--versao ID]` | Cria um registro e mostra os campos calculados |
| `forms listar [FORMULARIO] [--filtro CAMPO=VALOR]... [--limite N] [--deslocamento N]` | Sem argumento, lista os formulários; com ele, os registros |
| `forms exportar FORMULARIO [--saida ARQUIVO] [--filtro ...]` | CSV para o Excel em português (UTF-8 com BOM, `;`, vírgula decimal) |

O banco vem de `--banco` (ou da variável `FORMS_DB_PATH`; padrão `forms.db`). O formulário é dado pelo nome ou pelo id.

### Como se conecta
- **Depende de:** `forms.servico`, `forms.exportacao` (só para formatar células) e `forms.models`.
- **É usado por:** o comando `forms` (`[project.scripts]` em `pyproject.toml`).

### Decisões que moldam este código
- Erro de domínio vira mensagem em português no `stderr` e código de saída 1; erro de uso do `argparse` sai com 2.
- O relógio entra por parâmetro em `main` (`relogio`), então os testes são determinísticos.
- Foto não é suportada pela CLI (o envio usa o seletor de arquivo do front).

### Como testar
`uv run pytest tests/test_cli.py`

### Cuidados
- CLI além de importar e listar é linha de corte (AGENTS.md §11).
- A exportação sem `--saida` escreve bytes (com BOM) em `stdout.buffer`, para um redirecionamento `> arquivo.csv` abrir certo no Excel.

## api.py (e api_esquemas.py, api_rotas.py, exportar_openapi.py)

### Responsabilidade
A fronteira HTTP. Traduz JSON em chamadas ao `servico` e exceções de domínio em status HTTP. **Nenhuma regra de negócio.** Pydantic só existe aqui.

### O que tem aqui
| Arquivo | Papel |
|---|---|
| `api.py` | `criar_app(Configuracao)`, o `app` do uvicorn, o token por execução, o CORS e os tratadores de erro |
| `api_esquemas.py` | Modelos Pydantic de entrada e saída; seus nomes e campos são o contrato com o front |
| `api_rotas.py` | Os endpoints (formulários, versões, lote, validar, prévia, catálogo, registros, CSV, anexos) e as dependências (conexão por requisição, relógio, pasta de dados) |
| `api_extensoes.py` | `Extensao`, `descobrir_extensoes()` e `resposta_de_erro()`: como os módulos opcionais (`ia/`, `rag/`) acrescentam rotas sem o núcleo importá-los |
| `exportar_openapi.py` | `forms-openapi`: grava o `openapi.json` do front; `--conferir` falha se estiver desatualizado |

### Como se conecta
- **Depende de:** `forms.servico` (e dos tipos de `models`/`repositorio` só para montar respostas).
- **É usado por:** o uvicorn (`uv run uvicorn forms.api:app --host 127.0.0.1 --port 8000`), o front e o Electron.
- **Configuração** (variáveis de ambiente, ver `.env.example`): `FORMS_DB_PATH`, `FORMS_DATA_DIR`, `FORMS_TOKEN`, `FORMS_SKIP_TOKEN`, `FORMS_CORS_ORIGINS`.

### Decisões que moldam este código
- Erro uniforme `{detalhe, erros: [{campo, mensagem, posicao?}]}` em português, inclusive nos erros do próprio Pydantic, 404/405 e 500 (sem vazar a causa). 422 validação e definição inválida, 404 inexistente, 409 exclusão bloqueada, 401 token.
- Token por execução no cabeçalho `X-Forms-Token`, **falha fechada**: sem token configurado e sem `FORMS_SKIP_TOKEN`, toda requisição é recusada. O middleware do token fica *dentro* do CORS, para o preflight (que não leva token) passar e o 401 também levar os cabeçalhos CORS.
- CORS só para as origens do front (padrão: as duas do Vite); `*` é recusado na configuração.
- Conexão aberta e fechada por requisição (dependência); o relógio também é dependência, então os testes o fixam. Importar o módulo não abre banco nem cria arquivo.
- Filtro por campo na listagem e no CSV: `?filtro=campo:valor`, repetível (o `id` nunca contém `:`).
- Erro de lote: o `campo` leva o nome do formulário como prefixo (`proctor.umidade.formula`).
- `definicao`, `valores` e `dados` são `object`: chegam como JSON não confiável, e a validação com erros por `id` é do servidor, não do Pydantic. Campo a mais num corpo de requisição é recusado.
- Na inicialização, remove os anexos nunca vinculados há mais de 24 h.
- **Extensões opcionais:** `criar_app(..., extensoes=descobrir_extensoes())`. O núcleo procura `forms.ia.extensao` e `forms.rag.extensao` **pelo nome**, em execução, então não os importa (AGENTS.md §5.1) e o app sobe igual, só sem essas rotas, se a pasta for removida. Só a ausência do próprio módulo é aceita: um `import` quebrado lá dentro aparece como erro. As rotas das extensões entram antes do front e do middleware do token, então também exigem o token. O PyInstaller não vê imports por nome: `empacotamento/` os declara com `--hidden-import`.

### Como testar
`uv run pytest tests/test_api*.py` (`conftest.py` traz o app com banco temporário, token e relógio fixos).

### Cuidados
- Mudar nome ou campo de um modelo de resposta, ou o conjunto de rotas, é **mudança incompatível** com o `frontend/`: `tests/test_api_contrato.py` falha de propósito (AGENTS.md §5.3).
- O `TestClient` do Starlette emite um aviso sobre `httpx`; é só aviso.

## app.py

### Responsabilidade
A entrada do backend no app instalável (AGENTS.md §4.1). **Só monta as peças**: lê a configuração, escolhe a porta, monta a API com o front e entrega ao uvicorn. Não abre janela (isso é do Electron) e não tem regra de negócio.

### O que tem aqui
| Símbolo | Papel |
|---|---|
| `main()` | Sobe tudo; imprime `{"porta": N}` como **primeira linha** da saída, que o Electron lê |
| `configuracao_do_app(ambiente)` | Banco e fotos na pasta de dados do sistema (`platformdirs`; `FORMS_DATA_DIR` sobrescreve); exige `FORMS_TOKEN` |
| `localizar_front(ambiente)` | Acha o `frontend/dist`: `FORMS_FRONTEND_DIST`, o executável empacotado (`sys._MEIPASS/frontend_dist`) ou o repositório |
| `abrir_soquete_local()` | Reserva uma porta livre **só em 127.0.0.1**, já escutando, e a entrega ao uvicorn |

### Como se conecta
- **Depende de:** `forms.api` (`criar_app(configuracao, pasta_do_front, extensoes)`), `platformdirs` (pasta de dados correta em cada sistema; nova dependência).
- **É usado por:** o executável do PyInstaller (`empacotamento/`) e o Electron, que o inicia como processo filho.

### Decisões que moldam este código
- O soquete é entregue ao uvicorn em vez de "achar uma porta livre e fechar", que deixaria uma janela para outro processo ocupá-la.
- Sem `FORMS_TOKEN` o app não sobe (falha fechada, código de saída 2). O app instalado **nunca** dispensa o token, mesmo com `FORMS_SKIP_TOKEN` no ambiente.
- Na mesma origem não há CORS. O front estático não pede token (o navegador não manda cabeçalho ao carregar a página), mas **toda rota da API e a documentação continuam exigindo**: o middleware só isenta o que nenhuma rota da API reconhece.
- Os dados nunca ficam dentro do pacote do app (um teste confere); caminhos sempre com `pathlib`.

### Como testar
`uv run pytest tests/test_app.py` (inclui subir o servidor de verdade numa thread e consultar pela porta anunciada).

### Cuidados
- A primeira linha da saída é contrato com o Electron: nada pode ser impresso antes dela.
- Rodar à mão: `FORMS_TOKEN=abc uv run python -m forms.app` (depois de `npm run build` no `frontend/`).

## ia/ (cliente.py, gerador.py, resumo.py, validacao.py, extensao.py) — opcional

### Responsabilidade
Os recursos que usam um LLM: **gerar formulários** a partir de um pedido e **resumir registros**. A IA só redige; quem calcula e valida é código determinístico (AGENTS.md §2.5 e §3.3). O app inteiro funciona com esta pasta removida.

### O que tem aqui
| Arquivo | Papel |
|---|---|
| `cliente.py` | O **único** lugar que importa o SDK (`anthropic`, importado só na hora de usar). `ClienteDeLLM` (protocolo: `completar`, `vetorizar`, `modelo_de_vetores`), `ClienteAnthropic`, `ClienteFalso` (testes), `criar_cliente(ambiente)` e `IaIndisponivel` |
| `gerador.py` | `gerar(conexao, cliente, pedido, rascunhos)`: monta o prompt com o catálogo e os formulários existentes, lê o JSON proposto, valida o conjunto com `servico.validar_conjunto` e devolve os erros ao LLM para corrigir, no máximo 2 vezes. **Nunca salva** |
| `resumo.py` | `calcular_agregados` (contagem, mínimo, máximo, soma, média, frequências, feitos em código sobre **todos** os registros que passam nos filtros) e `resumir`, que só envia os agregados ao LLM |
| `validacao.py` | `validar_resumo`: formato do JSON, limites de tamanho e **todo número do texto tem de bater com os agregados** (arredondado para as casas escritas, meio para cima); senão `ResumoRejeitado` |
| `extensao.py` | As rotas `POST /definicoes/gerar` e `POST /formularios/{id}/resumo` e os tratadores `IaIndisponivel` → 503, `RespostaDaIaInvalida` e `ResumoRejeitado` → 502 |

### Como se conecta
- **Depende de:** o núcleo (`servico`, `models`) e, na `extensao.py`, de `api_rotas`/`api_extensoes`. O SDK é um extra opcional (`uv sync --extra ia`).
- **É usado por:** a API (descoberta por nome, ver `api.py`) e o front (`frontend/src/ia/`).
- **Configuração:** `ANTHROPIC_API_KEY` no `.env` (nunca em log, em `repr` nem em mensagem de erro) e `FORMS_LLM_MODELO` (padrão `claude-sonnet-5-5`).

### Decisões que moldam este código
- A saída do LLM é **dado não confiável**: o gerador passa pela mesma validação da publicação, e o resumo é conferido número a número contra o que o código calculou.
- O LLM nunca recebe registro nem texto livre do banco: só o pedido, metadados dos formulários (nome e campos compartilhados) e, no resumo, os agregados numéricos e as frequências de seleção e sim/não.
- Sem chave ou sem internet, as rotas respondem 503 em português e o resto do app segue; o construtor manual continua funcionando.
- O prompt trata `<pedido>` e `<agregados>` como dado, nunca como instrução.

### Como testar
`uv run pytest tests/test_ia_*.py tests/test_api_ia.py`. Os testes usam só o `ClienteFalso`: nenhum faz chamada de rede nem exige chave.

### Cuidados
- **Nenhuma chamada real ao LLM foi testada**: o `ClienteAnthropic` foi escrito contra a documentação do SDK, e a primeira chamada real pode mostrar ajustes (nome do modelo, formato da resposta).
- Sem chave, a validação do corpo da requisição vem *depois* do 503 (a dependência do cliente roda antes); com chave, um pedido grande demais dá 422.
- O `ClienteAnthropic` não tem embeddings (`vetorizar` levanta `IaIndisponivel`): a busca semântica só liga com outro provedor que implemente `ClienteDeLLM`.

## rag/ (chunker.py, indice.py, semantico.py, responder.py, extensao.py) — opcional

### Responsabilidade
O **assistente de procedimentos**: responde perguntas **só com trechos** dos `.md` de `docs/`, mostrando o trecho e o arquivo de origem. Sem base nos documentos, diz que não encontrou (AGENTS.md §2.5).

### O que tem aqui
| Arquivo | Papel |
|---|---|
| `chunker.py` | `dividir_em_trechos` (um trecho por seção, quebrado por parágrafos acima de 800 caracteres) e `carregar_documentos` |
| `indice.py` | BM25 escrito à mão (`IndiceBm25`), `tokenizar` (sem acento, sem palavras vazias, **sem stemming**) e o protocolo `Buscador` |
| `semantico.py` | Busca semântica opcional: vetores em BLOB no SQLite (`vetores_trechos`), cosseno em Python, `IndiceHibrido` (BM25 + semântico fundidos por RRF) e `carregar_vetores`, que só vetoriza o que ainda não está no banco |
| `responder.py` | `perguntar`: busca, pede ao LLM uma resposta **só com os trechos** e descarta a resposta se tiver número que não está neles. Sem LLM ou com falha, devolve só os trechos |
| `extensao.py` | `POST /assistente/perguntar` e `localizar_docs` (`FORMS_DOCS_DIR`, o executável empacotado ou `docs/` do repositório) |

### Como se conecta
- **Depende de:** `ia/cliente.py` (`ClienteDeLLM`), `repositorio` e `servico_base.transacao` (só na busca semântica).
- **É usado por:** a API (extensão descoberta por nome).

### Decisões que moldam este código
- O BM25 é a base e o **fallback**: sem provedor de embeddings, sem internet ou sem chave, vale só ele. A busca nunca falha por causa dos embeddings.
- A chave do vetor é o hash do **modelo** e do texto do trecho: trocar o modelo ou editar o trecho gera vetor novo, e o antigo é apagado. A chamada de rede fica fora da transação.
- O cosseno tem **limiar** (`LIMIAR_DE_SIMILARIDADE = 0,3`): sem ele o "vizinho mais próximo" sempre apareceria e "não encontrei" nunca existiria. O valor depende do modelo de embeddings e deve ser ajustado com perguntas reais.
- RRF funde só as posições (`1 / (60 + posição)`), então BM25 e cosseno, que têm escalas diferentes, não precisam ser normalizados.
- O índice é montado a cada pergunta (algumas centenas de trechos): editar um `.md` vale na hora, sem cache para invalidar.

### Como testar
`uv run pytest tests/test_rag.py tests/test_rag_semantico.py tests/test_api_ia.py`

### Cuidados
- Sem stemming: "romper" e "rompidos" são termos diferentes no BM25. É uma limitação conhecida, que a busca semântica ameniza.
- O PyInstaller leva `docs/` junto (`--add-data`), mas só os `.md` do repositório; a pessoa não os edita no app instalado.
