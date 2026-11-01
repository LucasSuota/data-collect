# Resumo do projeto: Construtor de Formulários Modulares

## O que é
Uma aplicação para **montar formulários arrastando e soltando campos**, preencher esses formulários e guardar os registros em SQLite. Sem foco em um setor: o mesmo sistema serve para inspeção de obra, ensaios de laboratório, checklists ou qualquer cadastro. Inspiração: Fulcrum (coleta de dados por formulários personalizáveis), mas local, simples e sem usuários nem cargos por enquanto.

Princípio central (mantido): **a IA nunca calcula, só busca e redige**. Quem calcula e valida é código determinístico, agora na forma de campos calculados com fórmulas.

O controle de corpos de prova de concreto, que era o projeto original, vira um **template de demonstração** (`templates/corpo_de_prova.json`). Ele prova que o sistema genérico dá conta de um caso real, com cálculo de resistência e conformidade.

## Como funciona

**1. Construtor de formulários (arrastar e soltar)**
- Paleta de tipos de campo à esquerda, área de montagem no centro, propriedades do campo selecionado à direita.
- Arrastar da paleta para a área de montagem, reordenar arrastando, editar rótulo, obrigatoriedade, opções e fórmula.
- Prévia ao vivo usando o **mesmo componente** que será usado no preenchimento.
- Salvar publica uma nova **versão** do formulário.

**2. Tipos de campo**
- MVP: texto, número (com unidade), data, seleção, sim/não, calculado, seção (só visual).
- Depois: grupo repetível (tabela de linhas), visibilidade condicional, foto, localização.

**3. Núcleo (sem IA)**
- Formulário = definição em JSON, versionada. Registro = dados em JSON + versão com que foi criado. Editar um formulário nunca quebra registros antigos.
- **Validação no servidor** contra a definição: tipo, obrigatório, opções válidas.
- **Campos calculados:** fórmulas avaliadas por um avaliador próprio, construído sobre o módulo `ast` do Python com lista de permissão (operadores, comparações, `se`, `min`, `max`, `media`, `soma`, `pi`, `dias`). Nunca `eval`.
- O servidor **recalcula sempre** ao salvar. O frontend pode mostrar prévia, mas não é fonte da verdade.
- A ordem de cálculo segue as dependências entre campos; ciclo é rejeitado ao publicar a versão.
- Campo de entrada vazio gera resultado vazio, e erro de fórmula (ex.: divisão por zero) aparece no campo, sem derrubar o registro.

**4. Preenchimento e consulta**
- Tela para preencher um formulário publicado.
- Lista de registros com colunas geradas a partir da definição, filtro simples e exportação CSV.

**5. Módulos de IA (opcionais, só depois do núcleo)**
- **Assistente de procedimentos (RAG):** procedimentos em `.md` (escritos por você, genéricos ou sintéticos), busca nos trechos com um BM25 escrito por você, resposta do LLM **só com os trechos recuperados**, exibindo trecho e arquivo de origem. Sem base nos documentos, responde "não encontrei". Sem internet ou chave de API, mostra apenas os trechos (fallback).
- **Resumo de registros por IA:** o LLM redige um texto a partir dos dados e dos agregados **calculados pelo código** (contagem, média etc.), em saída estruturada (JSON). Seu código confere se todos os números do texto batem com o banco. Se não baterem, o resumo é rejeitado.

**6. Interfaces**
- **CLI (enxuta):** importar template, criar registro a partir de JSON, listar e exportar registros.
- **Web:** aplicação React com telas de Formulários, Construtor, Registros (preencher e consultar) e, se sobrar tempo, Assistente e Resumo.
- CLI e API chamam as **mesmas funções do núcleo** (`servico.py`), que não sabem quem as chama.
- Sem login, usuários ou cargos nesta fase: uso local, com a API ouvindo só em `127.0.0.1`.

## Modelo de dados (SQLite)

```
formularios          id, nome, criado_em
versoes_formulario   id, formulario_id, numero, definicao (JSON), publicada_em
registros            id, formulario_id, versao_id, dados (JSON), criado_em, atualizado_em
```

Exemplo de definição (trecho do template de corpo de prova):

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

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Linguagem e ambiente | Python 3.12+, `uv`, `pyproject.toml` |
| Domínio | `dataclasses`, type hints |
| Persistência | `sqlite3`, dados dinâmicos em colunas JSON |
| Fórmulas | módulo `ast` com lista de permissão, sem `eval` |
| CLI | `argparse` |
| API | FastAPI, Uvicorn, Pydantic v2 (só na borda) |
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Arrastar e soltar | `dnd-kit` |
| Recuperação (opcional) | BM25 escrito por você, sem framework |
| IA (opcional) | SDK de um LLM (ex.: Anthropic), isolado em `ia/cliente.py` |
| Configuração | `python-dotenv`, `.env` no `.gitignore` antes do primeiro commit |
| Qualidade | `pytest`, `httpx` (TestClient), `ruff`, GitHub Actions |

**Desenvolvimento:** Vite na porta 5173 com proxy para o FastAPI na 8000. **Uso local:** `npm run build` e o FastAPI serve `frontend/dist`.

**De fora, de propósito:** LangChain, LlamaIndex, bancos vetoriais, ORM, Docker, Postgres, bibliotecas de estado globais, autenticação e cargos, modo offline e sincronização, mapas. Entram no README como "próximos passos".

## Arquitetura

```
src/forms/  models.py  tipos_campo.py  formulas.py  validacao.py
            repositorio.py  servico.py  cli.py  api.py
            rag/  chunker.py  indice.py  responder.py        (opcional)
            ia/   cliente.py  resumo.py  validacao.py        (opcional)
frontend/src/
            schema/    tipos TS da definição de formulário
            builder/   paleta, área de montagem, painel de propriedades
            runtime/   FormRenderer (único, usado na prévia e no preenchimento)
            pages/     Formularios, Construtor, Registros
templates/  corpo_de_prova.json  inspecao_obra.json  (exemplos)
docs/       (procedimentos em .md, para o assistente)
tests/      test_formulas.py  test_validacao.py  test_servico.py  test_api.py ...
```

## Pontos para defender na entrevista
- **IA não calcula:** é onde ela erra (aritmética, valores inventados). O cálculo é de um avaliador determinístico e o resumo por IA é validado contra o banco.
- **Formulário é dado, não código:** a definição é um JSON versionado; registros apontam para a versão com que nasceram, então evoluir um formulário não quebra o histórico.
- **Fórmulas sem `eval`:** avaliador sobre `ast` com lista de permissão, porque executar texto digitado pelo usuário é uma falha de segurança. Ordem de cálculo por dependência, ciclos rejeitados.
- **Servidor é a fonte da verdade:** valida e recalcula sempre; o frontend nunca é confiável.
- **Um único renderizador:** a prévia do construtor e o preenchimento usam o mesmo componente.
- **Núcleo independente das interfaces:** CLI e web são camadas finas por cima.
- **Framework só no encanamento** (FastAPI, React): o que você precisa explicar linha por linha (fórmulas, validação, versionamento, RAG) é seu.
- **`AI_NOTES.md`:** registro de erros reais da IA durante a construção.

## Cronograma e linha de corte
- **Sábado:** setup, `models.py`, `tipos_campo.py`, `formulas.py` com testes (é a parte mais testável e a mais importante), esquema SQLite.
- **Domingo:** `validacao.py`, repositório, `servico.py`, `api.py`; no frontend, esqueleto Vite + Tailwind, `FormRenderer` e o construtor com `dnd-kit` (paleta, área de montagem, propriedades).
- **Segunda:** salvar e publicar versão, preencher e listar registros, template do corpo de prova funcionando, README, `AI_NOTES.md` e ensaio em voz alta.
- **Se apertar, corte nesta ordem:** resumo por IA, assistente RAG, CLI além de importar e listar, exportação CSV, acabamento visual. Nunca o README, o `AI_NOTES.md`, o ensaio e os testes de fórmulas e validação.

## Próximos passos (fora do escopo agora)
- Grupo repetível, visibilidade condicional, foto e localização.
- Relação entre formulários (ex.: lote com vários corpos de prova).
- Usuários, cargos e permissões.
- IA que sugere um formulário a partir de uma descrição em texto, com a saída validada contra o esquema de definição antes de aparecer no construtor.
