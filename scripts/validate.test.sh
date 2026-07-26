#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERENA_PROBE=""
SECRET_PROBE=""
ACTIVE_CONFIGURATION_PROBE=""

cleanup() {
  [ -z "${SERENA_PROBE}" ] || rm -f "${SERENA_PROBE}"
  [ -z "${SECRET_PROBE}" ] || rm -f "${SECRET_PROBE}"
  [ -z "${ACTIVE_CONFIGURATION_PROBE}" ] || rmdir "${ACTIVE_CONFIGURATION_PROBE}"
}
trap cleanup EXIT

mkdir -p "${ROOT}/.serena"
SERENA_PROBE="$(mktemp "${ROOT}/.serena/validate-test.XXXXXX")"
printf 's%s\n' 'k-validation-probe' >"${SERENA_PROBE}"

if ! "${ROOT}/scripts/validate.sh" >/dev/null; then
  echo "Validation must ignore .serena runtime state." >&2
  exit 1
fi

SECRET_PROBE="$(mktemp "${ROOT}/validate-test.XXXXXX")"
printf 's%s\n' 'k-validation-probe' >"${SECRET_PROBE}"

if output="$("${ROOT}/scripts/validate.sh" 2>&1)"; then
  echo "Validation must reject secret-like content outside .serena." >&2
  exit 1
fi

if [[ "${output}" != *"Potential secret found"* ]]; then
  echo "Validation failed for an unexpected reason: ${output}" >&2
  exit 1
fi

rm -f "${SECRET_PROBE}"
SECRET_PROBE=""

for configuration_name in skills agents; do
  ACTIVE_CONFIGURATION_PROBE="${ROOT}/claude/${configuration_name}"
  mkdir "${ACTIVE_CONFIGURATION_PROBE}"

  if output="$("${ROOT}/scripts/validate.sh" 2>&1)"; then
    echo "Validation must reject an active Claude Code ${configuration_name} directory." >&2
    exit 1
  fi

  if [[ "${output}" != *"Claude Code ${configuration_name} must remain disabled"* ]]; then
    echo "Validation failed for an unexpected reason: ${output}" >&2
    exit 1
  fi

  rmdir "${ACTIVE_CONFIGURATION_PROBE}"
  ACTIVE_CONFIGURATION_PROBE=""
done

echo "Validation regression tests passed."
