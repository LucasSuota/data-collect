# API (FastAPI) do data-collect. Multi-stage: dependências com `uv`, imagem final sem dev e sem build.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS construir
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --extra ia
COPY src ./src
COPY README.md ./
RUN uv sync --locked --no-dev --extra ia

FROM python:3.12-slim-bookworm
# Usuário sem privilégios: um bug na API não vira acesso de root no contêiner.
RUN useradd --system --create-home --uid 10001 app && mkdir /config && chown app /config
WORKDIR /app
COPY --from=construir /app/.venv /app/.venv
COPY --from=construir /app/src /app/src
COPY templates ./templates
COPY ajuda ./ajuda
COPY legal ./legal
COPY docs ./docs
COPY docker/api/entrada.sh /entrada.sh
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 \
    FORMS_AJUDA_DIR=/app/ajuda FORMS_LEGAL_DIR=/app/legal FORMS_TEMPLATES_DIR=/app/templates \
    FORMS_DOCS_DIR=/app/docs
USER app
EXPOSE 8000
ENTRYPOINT ["/entrada.sh"]
CMD ["uvicorn", "forms.api.app:app_do_ambiente", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--limit-concurrency", "200", "--timeout-keep-alive", "5", "--no-access-log"]
