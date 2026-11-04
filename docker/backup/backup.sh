#!/bin/sh
# Backup diário com `pg_dump` (formato custom, restaurável com `pg_restore`), com retenção.
# Restaurar: docker compose exec -T postgres pg_restore -U forms -d forms --clean < /backups/forms-AAAA-MM-DD.dump
set -eu

while true; do
  dia=$(date -u +%Y-%m-%d)
  for banco in $BANCOS; do
    arquivo="/backups/${banco}-${dia}.dump"
    if pg_dump --format=custom --no-owner "$banco" > "${arquivo}.parcial"; then
      mv "${arquivo}.parcial" "$arquivo"
      echo "backup ok: $arquivo ($(du -h "$arquivo" | cut -f1))"
    else
      rm -f "${arquivo}.parcial"
      echo "backup FALHOU: $banco" >&2
    fi
  done
  find /backups -name '*.dump' -mtime "+${RETENCAO_DIAS}" -delete
  sleep 86400
done
