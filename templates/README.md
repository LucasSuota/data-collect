# templates

> Definições de formulário prontas para importar, que provam que o sistema genérico dá conta de casos reais.

## Responsabilidade
Guardar exemplos de definição (JSON, o formato do contrato de AGENTS.md §5.2). Não têm código: quem lê e cria o formulário é `servico.importar_template` / `servico.importar_templates`.

## O que tem aqui
| Arquivo | Papel |
|---|---|
| `corpo_de_prova.json` | Controle de corpos de prova de concreto: resistência (com `casas_decimais`), data de ruptura aos 28 dias e conformidade |
| `inspecao_obra.json` | Inspeção de obra: seções, seleção, sim/não, localização, foto e um calculado sobre dois sim/não |
| `ensaio_umidade.json` | Teor de umidade do solo pelas pesagens (cápsula, úmido, seco); libera `umidade_pct` para quem depende dele |
| `proctor.json` | Ensaio de compactação: depende do `ensaio_umidade` (umidade natural), calcula o desvio para a umidade ótima e libera `umidade_otima_pct` e `gamad_max` |
| `densidade_insitu.json` | Controle de compactação em campo: depende do `proctor` e do `ensaio_umidade`, calcula a massa específica seca de campo, o grau de compactação e a conformidade |

## Como se conecta
- **O nome do arquivo é o nome do formulário** criado, e é como a referência de outro template o encontra (`"formulario": "ensaio"`).
- Vários templates que dependem uns dos outros entram juntos por `importar_templates`, em qualquer ordem (a origem é criada primeiro).
- `ensaio_umidade` → `proctor` → `densidade_insitu` (e `densidade_insitu` também lê `ensaio_umidade`) é a cadeia de exemplo das referências entre formulários (AGENTS.md §2.7); é ela que o mapa de dependências do front mostra.
- **Usado por:** `servico.importar_template(s)`, a CLI (`forms importar-template`) e `tests/test_templates.py`.

## Como testar
`uv run pytest tests/test_templates.py`

## Cuidados
- São contrato com o front: mudar o `id` ou o `tipo` de um campo muda o que o front renderiza.
- Todo template novo precisa de teste de importação e de um registro de exemplo.
