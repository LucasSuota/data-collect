# src/forms

> Backend Python do construtor de formulários: definições em JSON versionadas, validação, fórmulas e persistência em SQLite.

Hoje existem `models.py`, `formulas.py`, `tipos_campo.py`, `repositorio.py` e `fotos.py`. Os demais módulos descritos em AGENTS.md §5 ainda não foram implementados.

## models.py

### Responsabilidade
Tipos comuns do domínio e exceções de domínio. Não valida, não calcula e não faz I/O.

### O que tem aqui
| Símbolo | Papel |
|---|---|
| `TipoCampo` | `StrEnum` com os 10 valores de `tipo` do JSON de definição |
| `Campo`, `Definicao` | Definição de um formulário; `opcoes` é tupla e `Definicao.campos` também |
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
- Só texto, número, data, seleção e sim/não são normalizados aqui; localização, foto e referência ficam com a validação de registro.

### Como testar
`uv run pytest tests/test_tipos_campo.py`

### Cuidados
- `bool` é subclasse de `int`: o número rejeita `true`/`false` de propósito.
- Mudar o rótulo ou as propriedades de um tipo muda o catálogo que o front lê.

## repositorio.py

### Responsabilidade
Único módulo que fala SQL. Por enquanto só abre a conexão e mantém o esquema; as funções de formulários, versões, registros e anexos chegam nas próximas issues.

### O que tem aqui
| Símbolo | Papel |
|---|---|
| `abrir_conexao(caminho)` | Abre o SQLite com `foreign_keys` ligado, linhas acessíveis por nome e esquema migrado |
| `migrar(conexao, migracoes)` | Aplica as migrações pendentes, cada uma numa transação junto com o `PRAGMA user_version` |
| `MIGRACOES`, `VERSAO_ATUAL_DO_ESQUEMA` | Lista ordenada de migrações; a posição N leva o banco da versão N à N+1 |
| `EsquemaMaisNovo` | Banco criado por um app mais novo é recusado, em vez de ser lido errado |

### Como se conecta
- **Depende de:** `sqlite3` e `forms.models` (`ErroDeDominio`).
- **É usado por:** nenhum módulo ainda.
- **Contratos e dados:** as seis tabelas de AGENTS.md §5.2 (`formularios`, `versoes_formulario`, `registros`, `dependencias_formulario`, `referencias_registro`, `anexos`).

### Decisões que moldam este código
- Datas em texto ISO; definição e dados em colunas JSON de texto (AGENTS.md §5.2).
- Exclusões bloqueadas já no banco (sem `ON DELETE`, o SQLite recusa), além da checagem do serviço (AGENTS.md §2.7).
- Migração num `BEGIN` explícito: sem ele o `sqlite3` não abre transação para DDL e uma falha deixaria o banco pela metade.
- A conexão entra por parâmetro; não há singleton (AGENTS.md §9).

### Como testar
`uv run pytest tests/test_repositorio_esquema.py`

### Cuidados
- Nunca edite uma migração já publicada (o banco do usuário persiste); acrescente outra. Um teste compara a migração 1 com o esquema publicado, escrito literalmente.
- Toda mudança de esquema exige teste de atualização a partir do esquema anterior (AGENTS.md §5.2).
- `PRAGMA user_version` não aceita `?`; o número vem de um `int` interno, nunca de texto externo.

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
