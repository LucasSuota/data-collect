#!/bin/sh
# Lê a configuração que o `logto-setup` escreveu (aplicativo, API resource, credenciais M2M) e
# entrega ao comando. Sem o arquivo (por exemplo, no `logto-setup` em si), segue só com o ambiente.
set -eu
if [ -f "${FORMS_CONFIG_DIR:-/config}/api.env" ]; then
  set -a
  . "${FORMS_CONFIG_DIR:-/config}/api.env"
  set +a
fi
exec "$@"
