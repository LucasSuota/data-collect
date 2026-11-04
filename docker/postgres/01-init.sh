#!/bin/bash
# Roda uma vez, na primeira subida do volume do Postgres: cria os bancos e o papel do aplicativo.
# O app conecta como `forms_app` (sem BYPASSRLS, §12); as migrações rodam com o dono (`forms`).
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE ROLE forms_app LOGIN PASSWORD '${FORMS_APP_PASSWORD:-forms_app}';
CREATE DATABASE logto OWNER $POSTGRES_USER;
CREATE DATABASE forms_test OWNER $POSTGRES_USER;
SQL

# O pgvector precisa existir em cada banco do app (a migração também o cria, se faltar).
for banco in "$POSTGRES_DB" forms_test; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$banco" \
    -c "CREATE EXTENSION IF NOT EXISTS vector;"
done
