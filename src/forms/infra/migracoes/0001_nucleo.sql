-- Esquema do núcleo (AGENTS.md §5.2): equipes, pessoas, cargos, formulários e registros.
-- Toda tabela de dados da equipe leva `grupo_id`; o Row Level Security (no fim) garante o
-- isolamento mesmo que uma consulta esqueça o filtro. Identificadores sem acento (§6).

CREATE TABLE grupos (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome TEXT NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL
);

CREATE TABLE usuarios (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    logto_sub TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    email TEXT,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL,
    ultimo_acesso_em TIMESTAMPTZ
);

CREATE TABLE cargos (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grupo_id BIGINT NOT NULL REFERENCES grupos (id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    nome_chave TEXT NOT NULL,
    descricao TEXT NOT NULL DEFAULT '',
    padrao BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (grupo_id, nome_chave)
);

CREATE TABLE cargo_permissoes (
    cargo_id BIGINT NOT NULL REFERENCES cargos (id) ON DELETE CASCADE,
    permissao TEXT NOT NULL,
    PRIMARY KEY (cargo_id, permissao)
);

-- Uma pessoa tem um cargo por equipe. Sem ON DELETE no cargo: cargo em uso não é apagado.
CREATE TABLE membros_grupo (
    grupo_id BIGINT NOT NULL REFERENCES grupos (id) ON DELETE CASCADE,
    usuario_id BIGINT NOT NULL REFERENCES usuarios (id) ON DELETE CASCADE,
    cargo_id BIGINT NOT NULL REFERENCES cargos (id),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    entrou_em TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (grupo_id, usuario_id)
);
CREATE INDEX membros_por_usuario ON membros_grupo (usuario_id);

-- O token do convite nunca é guardado: só o hash SHA-256 (AGENTS.md §12).
CREATE TABLE convites (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grupo_id BIGINT NOT NULL REFERENCES grupos (id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    cargo_id BIGINT NOT NULL REFERENCES cargos (id),
    token_hash TEXT NOT NULL UNIQUE,
    criado_por BIGINT REFERENCES usuarios (id) ON DELETE SET NULL,
    criado_em TIMESTAMPTZ NOT NULL,
    expira_em TIMESTAMPTZ NOT NULL,
    usado_em TIMESTAMPTZ,
    revogado_em TIMESTAMPTZ
);

CREATE TABLE consentimentos (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    usuario_id BIGINT NOT NULL REFERENCES usuarios (id) ON DELETE CASCADE,
    documento TEXT NOT NULL,
    versao TEXT NOT NULL,
    aceito_em TIMESTAMPTZ NOT NULL,
    UNIQUE (usuario_id, documento, versao)
);

CREATE TABLE pastas (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grupo_id BIGINT NOT NULL REFERENCES grupos (id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    nome_chave TEXT NOT NULL,
    pasta_pai_id BIGINT REFERENCES pastas (id),
    criado_em TIMESTAMPTZ NOT NULL
);
-- NULL não conta como igual num índice único: a raiz entra como 0 (os ids começam em 1).
CREATE UNIQUE INDEX pastas_por_nome_entre_irmas
    ON pastas (grupo_id, COALESCE(pasta_pai_id, 0), nome_chave);

CREATE TABLE formularios (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grupo_id BIGINT NOT NULL REFERENCES grupos (id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    nome_chave TEXT NOT NULL,
    pasta_id BIGINT REFERENCES pastas (id),
    criado_em TIMESTAMPTZ NOT NULL,
    UNIQUE (grupo_id, nome_chave)
);
CREATE INDEX formularios_por_pasta ON formularios (pasta_id);

-- Apagar o formulário apaga suas versões; só é possível sem registros (RESTRICT em registros).
CREATE TABLE versoes_formulario (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grupo_id BIGINT NOT NULL REFERENCES grupos (id) ON DELETE CASCADE,
    formulario_id BIGINT NOT NULL REFERENCES formularios (id) ON DELETE CASCADE,
    numero INTEGER NOT NULL,
    definicao JSONB NOT NULL,
    publicada_em TIMESTAMPTZ NOT NULL,
    UNIQUE (formulario_id, numero)
);

-- Um rascunho por formulário, compartilhado pela equipe (§2.2).
CREATE TABLE rascunhos_formulario (
    grupo_id BIGINT NOT NULL REFERENCES grupos (id) ON DELETE CASCADE,
    formulario_id BIGINT NOT NULL PRIMARY KEY REFERENCES formularios (id) ON DELETE CASCADE,
    definicao JSONB NOT NULL,
    base_versao_id BIGINT REFERENCES versoes_formulario (id) ON DELETE SET NULL,
    atualizado_por BIGINT REFERENCES usuarios (id) ON DELETE SET NULL,
    atualizado_em TIMESTAMPTZ NOT NULL,
    revisao INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE registros (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grupo_id BIGINT NOT NULL REFERENCES grupos (id) ON DELETE CASCADE,
    formulario_id BIGINT NOT NULL REFERENCES formularios (id),
    versao_id BIGINT NOT NULL REFERENCES versoes_formulario (id),
    dados JSONB NOT NULL,
    revisao INTEGER NOT NULL DEFAULT 1,
    criado_por BIGINT REFERENCES usuarios (id) ON DELETE SET NULL,
    atualizado_por BIGINT REFERENCES usuarios (id) ON DELETE SET NULL,
    criado_em TIMESTAMPTZ NOT NULL,
    atualizado_em TIMESTAMPTZ NOT NULL
);
CREATE INDEX registros_por_versao ON registros (grupo_id, formulario_id, versao_id, criado_em);

CREATE TABLE historico_registro (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grupo_id BIGINT NOT NULL REFERENCES grupos (id) ON DELETE CASCADE,
    registro_id BIGINT NOT NULL,
    usuario_id BIGINT REFERENCES usuarios (id) ON DELETE SET NULL,
    quando TIMESTAMPTZ NOT NULL,
    acao TEXT NOT NULL,
    valores_anteriores JSONB,
    motivo TEXT
);
CREATE INDEX historico_por_registro ON historico_registro (registro_id, id);

CREATE TABLE dependencias_formulario (
    grupo_id BIGINT NOT NULL REFERENCES grupos (id) ON DELETE CASCADE,
    formulario_id BIGINT NOT NULL REFERENCES formularios (id) ON DELETE CASCADE,
    depende_de_id BIGINT NOT NULL REFERENCES formularios (id),
    PRIMARY KEY (formulario_id, depende_de_id)
);

-- Apagar um registro apaga as referências que ele fazia; apagar o destino é recusado.
CREATE TABLE referencias_registro (
    grupo_id BIGINT NOT NULL REFERENCES grupos (id) ON DELETE CASCADE,
    registro_id BIGINT NOT NULL REFERENCES registros (id) ON DELETE CASCADE,
    campo_id TEXT NOT NULL,
    destino_id BIGINT NOT NULL REFERENCES registros (id),
    PRIMARY KEY (registro_id, campo_id)
);
CREATE INDEX referencias_por_destino ON referencias_registro (destino_id);

-- Row Level Security: o aplicativo conecta como `forms_app` (sem BYPASSRLS) e cada conexão
-- declara a equipe em `app.grupo_id`. Quem não declara não enxerga nada (defesa em profundidade).
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'forms_app') THEN
        CREATE ROLE forms_app NOLOGIN;
    END IF;
END
$$;

DO $$
DECLARE
    tabela TEXT;
BEGIN
    FOREACH tabela IN ARRAY ARRAY[
        'cargos', 'pastas', 'formularios', 'versoes_formulario', 'rascunhos_formulario',
        'registros', 'historico_registro', 'dependencias_formulario', 'referencias_registro'
    ]
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tabela);
        EXECUTE format(
            'CREATE POLICY isolamento ON %I USING (grupo_id = NULLIF(current_setting(''app.grupo_id'', true), '''')::bigint)'
            ' WITH CHECK (grupo_id = NULLIF(current_setting(''app.grupo_id'', true), '''')::bigint)',
            tabela
        );
    END LOOP;
END
$$;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO forms_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO forms_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO forms_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO forms_app;
