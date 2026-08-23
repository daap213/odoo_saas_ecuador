#!/usr/bin/env bash
# Actualiza odoo_saas_ecuador en el servidor y aplica upgrades de modulos.
# Uso manual:
#   sudo DB_NAME=demo MODULES=l10n_ec_sri bash /opt/odoo19/odoo_saas_ecuador/scripts/deploy_saas.sh
set -euo pipefail

ODOO_USER="odoo19"
ODOO_HOME="/opt/odoo19"
SAAS_DIR="${ODOO_HOME}/third-party-addons/odoo_saas_ecuador"
ODOO_VENV="${ODOO_HOME}/venv"
ODOO_SOURCE="${ODOO_HOME}/odoo"
ODOO_CONFIG="${ODOO_HOME}/config/odoo.conf"

DB_NAME="${DB_NAME:-}"
MODULES="${MODULES:-l10n_ec_sri}"

log() { echo -e "\n\033[1;34m==>\033[0m $1"; }

require_root() {
  [[ $EUID -eq 0 ]] || { echo "Correr como root (sudo)." >&2; exit 1; }
}

pull_repo() {
  log "git pull en ${SAAS_DIR}"
  sudo -u "${ODOO_USER}" git -C "${SAAS_DIR}" fetch origin 19.0
  sudo -u "${ODOO_USER}" git -C "${SAAS_DIR}" reset --hard origin/19.0
}

detect_db() {
  if [[ -n "${DB_NAME}" ]]; then echo "${DB_NAME}"; return; fi
  sudo -u postgres psql -lqt 2>/dev/null \
    | awk '$1!~/^(template|postgres|\|)$/ && $1!="" {print $1}' \
    | head -1
}

apply_modules() {
  local db
  db="$(detect_db)"
  [[ -n "${db}" ]] || { log "No se detecto ninguna BD, omito upgrade"; return; }
  [[ -n "${MODULES}" ]] || { log "MODULES vacio, omito upgrade"; return; }

  log "Aplicando MODULES='${MODULES}' a BD '${db}'"
  systemctl stop odoo19

  IFS=',' read -ra mods <<< "${MODULES}"
  for m in "${mods[@]}"; do
    m="$(echo "$m" | xargs)"
    [[ -z "$m" ]] && continue
    local state log_file
    state="$(sudo -u postgres psql -d "${db}" -tAc \
      "SELECT state FROM ir_module_module WHERE name='${m}';" 2>/dev/null | xargs || true)"
    log_file="/tmp/deploy_${m}.log"
    local flag="-u"
    [[ "${state}" != "installed" ]] && flag="-i"

    log "${m} (estado: ${state:-not found}) -> ${flag}"
    set +e
    sudo -u "${ODOO_USER}" "${ODOO_VENV}/bin/python3" "${ODOO_SOURCE}/odoo-bin" \
      -c "${ODOO_CONFIG}" -d "${db}" --no-http --stop-after-init \
      "${flag}" "${m}" --log-level=warn --logfile="${log_file}"
    local rc=$?
    set -e
    if [[ ${rc} -ne 0 ]]; then
      echo ">>> FALLO ${flag} ${m} (exit ${rc}). Ultimas 30 lineas:"
      tail -30 "${log_file}" || true
      return 1
    fi
  done
}

main() {
  require_root
  trap 'systemctl is-active --quiet odoo19 || systemctl start odoo19' EXIT
  pull_repo
  apply_modules
  systemctl restart odoo19
  sleep 3
  systemctl is-active odoo19 || systemctl status odoo19 --no-pager
  log "OK - deploy completado"
}

main "$@"
