-- IA (AGENTS.md §2.5): provedor por equipe, documentos indexados, vetores e conversas.
CREATE EXTENSION IF NOT EXISTS vector;

-- A chave do LLM é cifrada (Fernet) antes de chegar aqui e nunca sai pela API (§12).
CREATE TABLE config_ia_grupo (
    grupo_id BIGINT PRIMARY KEY REFERENCES grupos (id) ON DELETE CASCADE,
    ativa BOOLEAN NOT NULL DEFAULT FALSE,
    consentimento_por BIGINT REFERENCES usuarios (id) ON DELETE SET NULL,
    consentimento_em TIMESTAMPTZ,
    provedor TEXT NOT NULL DEFAULT 'anthropic',
    base_url TEXT,
    modelo TEXT,
    modelo_embeddings TEXT,
    chave_cifrada TEXT,
    atualizado_por BIGINT REFERENCES usuarios (id) ON DELETE SET NULL,
    atualizado_em TIMESTAMPTZ
);

-- Um documento de texto por registro ou definição, para a busca do chatbot.
CREATE TABLE documentos_ia (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grupo_id BIGINT NOT NULL REFERENCES grupos (id) ON DELETE CASCADE,
    tipo TEXT NOT NULL,
    origem_id BIGINT NOT NULL,
    formulario_id BIGINT,
    texto TEXT NOT NULL,
    hash TEXT NOT NULL,
    metadados JSONB NOT NULL DEFAULT '{}',
    criado_em TIMESTAMPTZ,
    atualizado_em TIMESTAMPTZ NOT NULL,
    UNIQUE (grupo_id, tipo, origem_id)
);
CREATE INDEX documentos_por_formulario ON documentos_ia (grupo_id, formulario_id);

-- Vetores sem dimensão fixa na coluna: o índice HNSW exige dimensão, então ele é criado por
-- modelo (índice parcial) quando o grupo configura os embeddings.
CREATE TABLE vetores_documentos (
    documento_id BIGINT NOT NULL REFERENCES documentos_ia (id) ON DELETE CASCADE,
    modelo TEXT NOT NULL,
    vetor vector NOT NULL,
    PRIMARY KEY (documento_id, modelo)
);

-- Vetores dos guias de ajuda (globais, iguais para todas as equipes).
CREATE TABLE vetores_trechos (
    chave TEXT PRIMARY KEY,
    vetor BYTEA NOT NULL
);

CREATE TABLE conversas_ia (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grupo_id BIGINT NOT NULL REFERENCES grupos (id) ON DELETE CASCADE,
    usuario_id BIGINT NOT NULL REFERENCES usuarios (id) ON DELETE CASCADE,
    titulo TEXT NOT NULL DEFAULT '',
    criada_em TIMESTAMPTZ NOT NULL
);

CREATE TABLE mensagens_ia (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversa_id BIGINT NOT NULL REFERENCES conversas_ia (id) ON DELETE CASCADE,
    papel TEXT NOT NULL,
    texto TEXT NOT NULL,
    citacoes JSONB NOT NULL DEFAULT '[]',
    criada_em TIMESTAMPTZ NOT NULL
);

-- Só contagens: nunca o conteúdo das mensagens (AGENTS.md §2.15).
CREATE TABLE uso_ia (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grupo_id BIGINT NOT NULL REFERENCES grupos (id) ON DELETE CASCADE,
    usuario_id BIGINT REFERENCES usuarios (id) ON DELETE SET NULL,
    provedor TEXT NOT NULL,
    tokens_entrada INTEGER NOT NULL DEFAULT 0,
    tokens_saida INTEGER NOT NULL DEFAULT 0,
    quando TIMESTAMPTZ NOT NULL
);
CREATE INDEX uso_ia_por_grupo ON uso_ia (grupo_id, quando);

DO $$
DECLARE
    tabela TEXT;
BEGIN
    FOREACH tabela IN ARRAY ARRAY['config_ia_grupo', 'documentos_ia', 'conversas_ia', 'uso_ia']
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
