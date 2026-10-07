#!/usr/bin/env bash
set -euo pipefail

lan_ip() {
  if command -v ip >/dev/null 2>&1; then
    ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") {print $(i+1); exit}}'
  elif command -v ifconfig >/dev/null 2>&1; then
    ifconfig 2>/dev/null | awk '/^[a-z0-9]+:/{dev=$1} /inet /&&$2!="127.0.0.1"{print dev, $2; exit}' | awk '{print $2}'
  fi
}

public_ip() {
  curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null || true
}

lan=$(lan_ip || true)
wan=$(public_ip)

printf 'Локальный IP: %s\n' "${lan:-не найден}"
printf 'Публичный IP: %s\n' "${wan:-недоступен}"