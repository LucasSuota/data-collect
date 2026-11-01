# Construtor de Formulários Modulares (backend)

Backend para montar formulários por definição JSON versionada, preencher registros e guardá-los em SQLite. Os campos calculados usam fórmulas avaliadas por um avaliador próprio, sem `eval`.

Princípio central: **a IA nunca calcula, só busca e redige.** Quem calcula e valida é código determinístico.

A interface web fica em outro repositório e consome esta API. O contexto completo do projeto (escopo, arquitetura, regras) está em [AGENTS.md](AGENTS.md).

## Como rodar

Requer [uv](https://docs.astral.sh/uv) e Python 3.12+.

```bash
uv sync
cp .env.example .env
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

A API e a CLI ainda não existem; este README será atualizado conforme forem criadas.

## Próximos passos (fora do escopo atual)

- Grupo repetível, visibilidade condicional, foto e localização.
- Relação entre formulários (ex.: lote com vários corpos de prova).
- Usuários, cargos e permissões.
- IA que sugere um formulário a partir de uma descrição em texto, com a saída validada contra o esquema de definição.
- `Dockerfile` mínimo, se alguém sem Python precisar subir a API ou houver deploy.
