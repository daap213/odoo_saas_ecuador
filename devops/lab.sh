#!/usr/bin/env bash
# Laboratorio local: Odoo 19 + PostgreSQL con ESTE repo montado.
#
# Se apoya en ../odoo_template (docker-compose.yaml + docker-compose.test.yaml)
# y le añade devops/docker-compose.lab.yaml, que monta el directorio de trabajo
# — el checkout real o un worktree — en /mnt/extra-addons/odoo_saas_ecuador.
#
#   ./devops/lab.sh up          levanta el stack (primer arranque ~4 min)
#   ./devops/lab.sh init        crea la BD `lab` y deja admin/admin
#   ./devops/lab.sh install     instala base -> edi -> sri
#   ./devops/lab.sh install l10n_ec_full
#   ./devops/lab.sh update l10n_ec_sri
#   ./devops/lab.sh test        corre la suite de l10n_ec_sri
#   ./devops/lab.sh test l10n_ec_base
#   ./devops/lab.sh shell       odoo shell sobre la BD `lab`
#   ./devops/lab.sh logs | ps | down
#
# Odoo queda en http://localhost:18069 (BD `lab`, usuario admin, clave admin).
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB="${LAB_DB:-lab}"

# El repo puede estar en su checkout o en un worktree bajo .claude/worktrees/,
# así que se busca odoo_template subiendo directorios en vez de asumir el nivel.
if [ -z "${TEMPLATE_DIR:-}" ]; then
    d="$REPO_DIR"
    while [ "$d" != "/" ] && [ -n "$d" ]; do
        if [ -f "$d/odoo_template/docker-compose.yaml" ]; then
            TEMPLATE_DIR="$d/odoo_template"; break
        fi
        d="$(dirname "$d")"
    done
fi

if [ ! -f "$TEMPLATE_DIR/docker-compose.yaml" ]; then
    echo "ERROR: no encuentro odoo_template en $TEMPLATE_DIR" >&2
    echo "       Fija TEMPLATE_DIR=/ruta/a/odoo_template" >&2
    exit 1
fi

# COMPOSE_PATH_SEPARATOR es ':' y las rutas de Windows llevan 'D:', así que el
# tercer fichero se pasa RELATIVO al directorio del template. El volumen sí usa
# ruta absoluta, vía EC_ADDONS_PATH.
REL_LAB="$(realpath --relative-to="$TEMPLATE_DIR" "$REPO_DIR" 2>/dev/null || true)"
if [ -z "$REL_LAB" ]; then
    echo "ERROR: no puedo calcular la ruta relativa del repo respecto al template." >&2
    echo "       Pásala a mano en COMPOSE_FILE, o instala coreutils (realpath)." >&2
    exit 1
fi

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-odoolab}"
export COMPOSE_PATH_SEPARATOR=":"
export COMPOSE_FILE="docker-compose.yaml:docker-compose.test.yaml:${REL_LAB}/devops/docker-compose.lab.yaml"
export COMPOSE_ENV_FILES=.env.test
export ENV_FILE=.env.test
export EC_ADDONS_PATH="$REPO_DIR"
cd "$TEMPLATE_DIR" || exit 1
# `--no-http` es imprescindible: el Odoo ya en marcha tiene tomados 8069 y 8072 y un
# segundo proceso muere con "Address already in use".
#
# Sin límites de memoria ni de tiempo: `config/odoo.conf` los fija en 650/800 MB
# pensando en workers de producción, y cargar el registro entero de `l10n_ec_full`
# (medio ERP) los supera. El proceso muere **sin imprimir nada**, así que parece que
# la orden "terminó" cuando en realidad la mataron.
odoo_run() { docker compose exec -T odoo odoo -d "$DB" "$@" \
    --limit-memory-soft=0 --limit-memory-hard=0 --limit-time-real=0 \
    --stop-after-init --no-http --workers=0 --max-cron-threads=0; }

case "${1:-up}" in
  up)
    mkdir -p .test-data/{data,postgresql,share,extra-addons,traefik}
    docker compose up -d
    echo "Levantando. El healthcheck da hasta 300s: docker compose ps"
    ;;
  init)
    docker compose exec -T odoo odoo -d "$DB" --init base --without-demo=all \
      --stop-after-init --workers=0 --max-cron-threads=0
    docker compose exec -T odoo odoo shell -d "$DB" --no-http --workers=0 --max-cron-threads=0 <<'PY'
env['res.users'].browse(2).write({'password': 'admin'})
env.cr.commit()
PY
    ;;
  install)  shift; odoo_run -i "${*:-l10n_ec_base,l10n_ec_edi,l10n_ec_sri}" ;;
  update)   shift; odoo_run -u "${*:-l10n_ec_sri}" ;;
  test)
    # `--test-enable` levanta el servidor HTTP aunque se pase `--no-http` (lo necesita
    # para los HttpCase), así que choca con el Odoo que ya está sirviendo en 8069/8072.
    # Se le dan puertos propios en vez de apagar el servicio.
    # MSYS_NO_PATHCONV: en Git Bash sobre Windows, `/l10n_ec_sri` se traduce a
    # `C:/Program Files/Git/l10n_ec_sri` antes de llegar a Odoo, que lo rechaza con
    # "Invalid tag" y ejecuta 0 tests sin fallar. Silencioso y muy fácil de tomar por
    # "todo verde".
    # Sin límites de memoria: `config/odoo.conf` los fija en 650/800 MB pensando en
    # workers de producción, y una suite que carga el plan de cuentas `ec` una vez por
    # clase de test los supera. El proceso muere **sin imprimir el resumen**, así que
    # parece que la suite "terminó" cuando en realidad la mataron.
    # `--log-handler odoo.tests:INFO` no es cosmético: con `log_level = warn` (lo que
    # fija config/odoo.conf) la línea "N failed, M error(s) of X tests" sólo se ve
    # CUANDO HAY FALLOS, porque entonces se emite a nivel ERROR. Si todo pasa se emite
    # a INFO y desaparece, así que una suite verde parecía una suite que murió a medias.
    shift; m="${1:-l10n_ec_sri}"
    MSYS_NO_PATHCONV=1 docker compose exec -T odoo odoo -d "$DB" -u "$m" \
      --test-enable --test-tags "/$m" \
      --http-port=8169 --gevent-port=8172 \
      --log-handler odoo.tests:INFO \
      --limit-memory-soft=0 --limit-memory-hard=0 --limit-time-real=0 \
      --stop-after-init --workers=0 --max-cron-threads=0
    ;;
  shell)    docker compose exec odoo odoo shell -d "$DB" --no-http --workers=0 --max-cron-threads=0 ;;
  logs)     docker compose logs -f --tail=200 odoo ;;
  ps)       docker compose ps ;;
  config)   docker compose config ;;
  down)     docker compose down ;;
  *)        echo "uso: $0 {up|init|install|update|test|shell|logs|ps|config|down}"; exit 1 ;;
esac
