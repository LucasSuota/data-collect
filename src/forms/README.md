# src/forms

> Backend Python do construtor de formulários: definições em JSON versionadas, validação, fórmulas e persistência em SQLite.

Hoje existem `models.py`, `formulas.py`, `tipos_campo.py`, `validacao.py`, `repositorio.py`, `fotos.py`, `exportacao.py` e os módulos `servico*.py`. Os demais módulos descritos em AGENTS.md §5 ainda não foram implementados.

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

### Como se conecta
- **Depende de:** `sqlite3` e `forms.models`.
- **É usado por:** nenhum módulo ainda.
- **Contratos e dados:** as seis tabelas de AGENTS.md §5.2, na versão 2 do esquema.

### Decisões que moldam este código
- O relógio entra por parâmetro (`agora`, em UTC); o módulo nunca lê a hora. Todas as datas usam o mesmo formato ISO, então comparar texto é comparar tempo.
- A transação é de quem chama: as funções não fazem commit, para a cascata de recálculo entrar ou sair inteira (AGENTS.md §2.7).
- Filtro: o nome do campo precisa estar em `campos_permitidos` (calculado pelo serviço a partir da definição) **e** ter formato de identificador; o caminho JSON e o valor vão como parâmetro (AGENTS.md §2.3 e §12).
- Exclusões já são bloqueadas no banco (sem `ON DELETE`, o SQLite recusa), além da checagem do serviço (AGENTS.md §2.7).
- Migração num `BEGIN` explícito: sem ele o `sqlite3` não abre transação para DDL. A migração 2 (`nome_chave`) calcula a chave em Python porque o `lower()` do SQLite só entende ASCII.

### Como testar
`uv run pytest tests/test_repositorio_*.py`

### Cuidados
- Nunca edite uma migração já publicada (o banco do usuário persiste); acrescente outra. Um teste compara a migração 1 com o esquema publicado, escrito literalmente, e outro atualiza um banco real da v1 para a v2.
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
| `servico.py` | Fachada: formulários e versões (criar, publicar, lote, validar, catálogo) e reexportação de todo o resto, então a API chama `servico.<função>` |
| `servico_base.py` | Transação (`transacao`), campos compartilhados dos formulários publicados e o `Cache` de uma operação |
| `servico_registros.py` | Criar, atualizar (com cascata), excluir registro, excluir formulário e prévia |
| `servico_anexos.py` | Upload de foto em duas etapas, leitura do WebP, limpeza de órfãos e os arquivos da pasta de dados |
| `servico_consulta.py` | Listagem com colunas da definição, filtros, paginação e exportação CSV |

### Como se conecta
- **Depende de:** `repositorio`, `validacao`, `formulas`, `tipos_campo`, `fotos`, `exportacao` e `models`.
- **É usado por:** nenhum módulo ainda (`api.py` e `cli.py` virão).

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
