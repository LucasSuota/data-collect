# src/forms

> Backend Python do construtor de formulários: definições em JSON versionadas, validação, fórmulas e persistência em SQLite.

Hoje existem `models.py`, `formulas.py`, `tipos_campo.py` e `repositorio.py`. Os demais módulos descritos em AGENTS.md §5 ainda não foram implementados.

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
Ler o texto de uma fórmula e devolver a árvore já verificada, sem executar nada. Ainda não avalia valores, não infere tipos e não monta o grafo de dependências.

### O que tem aqui
| Símbolo | Papel |
|---|---|
| `analisar_formula(texto)` | `ast.parse` em modo `eval` + verificação da árvore; devolve `ast.Expression` ou levanta `FormulaInvalida` com `posicao` |
| `FUNCOES_PERMITIDAS` | Nomes de função aceitos em chamadas (provisório, até existir a tabela única de funções) |

### Como se conecta
- **Depende de:** `ast` e `forms.models` (`FormulaInvalida`, `Posicao`).
- **É usado por:** nenhum módulo ainda.

### Decisões que moldam este código
- Allowlist de nós de expressão: constante numérica ou booleana, nome, `+ - * / **`, `-` e `not` unários, `and`/`or`, comparações simples e chamadas às funções permitidas (AGENTS.md §7).
- Nó fora da lista é erro explícito, nunca ignorado; só o primeiro problema é reportado.
- A `posicao` é em caracteres: o `ast` mede em bytes UTF-8, e o front sublinha por caracteres.

### Como testar
`uv run pytest tests/test_formulas.py`

### Cuidados
- Nunca chamar `eval`, `exec`, `compile` nem `__import__`; um teste confere o fonte do módulo.
- Constantes como `0.1` chegam da árvore como `float`; quem avaliar deve criar o `Decimal` a partir do texto original, nunca do `float` (AGENTS.md §7).

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
