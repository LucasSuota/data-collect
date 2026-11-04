-- Notificações do sino e progresso do tour (AGENTS.md §2.16 e §2.18).
CREATE TABLE notificacoes (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grupo_id BIGINT NOT NULL REFERENCES grupos (id) ON DELETE CASCADE,
    usuario_id BIGINT NOT NULL REFERENCES usuarios (id) ON DELETE CASCADE,
    tipo TEXT NOT NULL,
    referencia JSONB NOT NULL DEFAULT '{}',
    lida_em TIMESTAMPTZ,
    criada_em TIMESTAMPTZ NOT NULL
);
CREATE INDEX notificacoes_por_usuario ON notificacoes (usuario_id, lida_em, id DESC);

CREATE TABLE onboarding_progresso (
    usuario_id BIGINT PRIMARY KEY REFERENCES usuarios (id) ON DELETE CASCADE,
    tour_concluido BOOLEAN NOT NULL DEFAULT FALSE,
    passo INTEGER NOT NULL DEFAULT 0,
    checklist_dispensado BOOLEAN NOT NULL DEFAULT FALSE,
    atualizado_em TIMESTAMPTZ NOT NULL
);

ALTER TABLE notificacoes ENABLE ROW LEVEL SECURITY;
CREATE POLICY isolamento ON notificacoes
    USING (grupo_id = NULLIF(current_setting('app.grupo_id', true), '')::bigint)
    WITH CHECK (grupo_id = NULLIF(current_setting('app.grupo_id', true), '')::bigint);

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO forms_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO forms_app;
