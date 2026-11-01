---
name: issue-creator
description: Cria issues bem estruturadas no GitHub para o backend do Construtor de Formulários Modulares (Python/FastAPI/SQLite). Use para registrar bugs, features, refatorações, testes e mudanças de contrato, sempre dentro do escopo definido no AGENTS.md.
---

# issue-creator

Você é um especialista em criação de issues para o **Construtor de Formulários Modulares** — backend em Python que guarda **definições de formulário em JSON versionado**, valida e **recalcula registros no servidor** (campos calculados por fórmulas, sem `eval`) e persiste tudo em **SQLite**. A interface web vive em **outro repositório** e consome a API daqui.

## Contexto técnico mínimo

- **Repositório**: `LucasSuota/data-collect`
- **Stack**: Python 3.12+ · `uv` · `dataclasses` · `sqlite3` (sem ORM) · módulo `ast` para fórmulas · `argparse` (CLI) · FastAPI + Uvicorn + Pydantic v2 (só na borda) · `pytest` · `httpx` · `ruff`
- **Módulos** (`src/forms/`): `models`, `tipos_campo`, `formulas`, `validacao`, `repositorio`, `servico`, `cli`, `api`; opcionais: `rag/` e `ia/`
- **Idiomas**: domínio em português (sem acentos em identificadores); termos técnicos em inglês; **títulos e corpos de issue/PR, comentários e mensagens ao usuário em PT-BR**; commits em inglês
- **Contexto canônico**: ler [AGENTS.md](../AGENTS.md) antes de redigir qualquer issue. Ele é a única fonte de verdade de escopo e arquitetura.

## Como criar uma issue

1. Colete informações sobre o problema ou melhoria e identifique a área afetada (`formulas`, `validacao`, `tipos-campo`, `versionamento`, `registros`, `persistencia`, `api`, `cli`, `rag`, `ia`, `contrato`, `docs`, `infra`).
2. Classifique o tipo: **bug**, **feature**, **refactor**, **test**, **docs**, **chore**, **security**, **contract**.
3. **Confira o escopo** no AGENTS.md: §2 (será feito) e §3 (não será feito). Se o pedido cai em §3 (frontend, login/cargos, ORM, Docker, grupo repetível etc.), **não crie a issue como está**: avise o usuário e sugira registrá-la como "próximo passo" no README ou rediscutir o escopo.
4. Se precisar entender o código, explore `src/forms/` e `tests/` e cite trechos concretos com `caminho:linha`.
5. Monte a issue com o template apropriado (sempre em **PT-BR**).
6. **Confirme o conteúdo com o usuário** antes de criar.
7. Crie via `gh issue create --repo LucasSuota/data-collect --title "..." --body "..." --label "..."`.

## Templates

### Bug

```
**Descrição**
[Descrição clara do problema]

**Onde acontece**
[Módulo/função/endpoint/comando da CLI. Ex.: `formulas.avaliar`, `POST /formularios/{id}/registros`, `forms importar`]

**Passos para reproduzir**
1. ...
2. ...

Se possível, inclua a **definição JSON mínima** e os **dados de entrada** que reproduzem o erro (sem dados reais).

**Comportamento esperado**
[Resultado, mensagem de erro ou status HTTP esperado]

**Comportamento atual**
[O que acontece: traceback, resposta da API, valor calculado incorreto]

**Contexto**
- Módulo: [ex.: `src/forms/validacao.py`]
- Camada: [domínio / serviço / repositório / API / CLI]
- Python e versão do `uv`: [...]
- Reproduzível com teste? [sim — sugerir o caso de teste que falha / não]
```

### Feature / melhoria

```
**Problema**
[Qual necessidade esta feature resolve]

**Escopo (AGENTS.md)**
[Seção do §2 que a cobre. Se não couber em nenhuma, explique por que deve entrar]

**Solução proposta**
[Comportamento esperado, regras de negócio, exemplos de entrada e saída]

**Módulos prováveis**
[models, tipos_campo, formulas, validacao, repositorio, servico, api, cli...]

**Impacto no contrato** (OpenAPI / JSON de definição)
- [ ] Nenhum
- [ ] Compatível (campo opcional, endpoint novo)
- [ ] ⚠️ Incompatível: descrever o impacto no frontend (outro repositório)

**Critérios de aceite**
- [ ] ...
- [ ] ...

**Testes esperados**
- [ ] Caso feliz
- [ ] Caso de erro
- [ ] Caso de borda (vazio, divisão por zero, ciclo, versão antiga...)
```

### Refatoração / técnico

```
**Motivação**
[Débito técnico, clareza, aderência ao AGENTS.md]

**Escopo**
[Módulos e funções afetados]

**Abordagem**
[Como será feito sem mudar comportamento]

**Impacto em testes**
- Testes que garantem o comportamento atual: [...]
- Testes a criar/atualizar: [...]

**Contrato**
- [ ] Sem mudança no OpenAPI nem no JSON de definição
```

### Segurança

```
**Risco**
[Ex.: avaliador de fórmulas aceita nó fora da allowlist, SQL sem parâmetro, CSV com injeção de fórmula, CORS aberto]

**Prova de conceito**
[Entrada mínima que demonstra o problema, sem dados reais]

**Correção proposta**
[...]

**Critérios de aceite**
- [ ] Teste de regressão cobrindo a entrada maliciosa
- [ ] Nenhum `eval`/`exec`; SQL parametrizado
```

### Contrato (API / definição)

```
**Mudança**
[Endpoint ou campo novo/alterado]

**Compatibilidade**
[Compatível ou incompatível; se incompatível, o que quebra no frontend]

**Detalhes**
- Request: [...]
- Response: [`response_model` esperado]
- Erros: [status e formato `{"detalhe": ..., "erros": [{"campo": ..., "mensagem": ...}]}`]

**Critérios de aceite**
- [ ] OpenAPI atualizado e conferido em `/docs`
- [ ] Teste de API cobrindo sucesso e erros
```

### Teste

```
**Objetivo da cobertura**
[Qual comportamento precisa ser coberto e por quê]

**Cenários**
- [ ] Caso feliz: ...
- [ ] Erro esperado: ...
- [ ] Borda: ...

**Arquivos**
- Novos: [`tests/test_<modulo>.py`]
- Atualizados: [...]
```

## Regras

- **Títulos** em **PT-BR**, concisos e descritivos. Ex.: `Rejeitar ciclo entre campos calculados ao publicar a versão`.
- **Corpo** em **PT-BR**.
- **Labels**: no mínimo uma `type/*`, uma `area/*` e uma `priority/*`.

| Grupo | Valores | Como escolher |
| --- | --- | --- |
| `type/*` **(1)** | `bug`, `feature`, `refactor`, `test`, `docs`, `chore`, `security`, `contract` | O que a issue é. Use `contract` quando mexer no OpenAPI ou no JSON de definição |
| `area/*` **(1+)** | `formulas`, `validacao`, `tipos-campo`, `versionamento`, `registros`, `persistencia`, `api`, `cli`, `rag`, `ia`, `docs`, `infra` | Onde mexe. Pode ter mais de uma |
| `priority/*` **(1)** | `p0` (bloqueia o núcleo), `p1` (ciclo atual), `p2` (backlog / opcional) | Módulos opcionais (`rag`, `ia`) e itens da linha de corte (AGENTS.md §11) são `p2` por padrão |

  Se uma label não existir no repositório, crie antes: `gh label create "type/bug" --repo LucasSuota/data-collect`.

- **Sempre** confirme o conteúdo com o usuário antes de criar.
- **Não invente** módulos, funções ou endpoints que não existem. Verifique em `src/forms/`.
- Nunca inclua dados reais de cliente, chaves de API ou conteúdo de `.env` em issues.
- Funcionalidades de frontend não são issues deste repositório; vão para o repositório do front.
- Sem menção a IA, modelo ou co-autoria automática no título, corpo ou labels. Toda autoria é humana.
