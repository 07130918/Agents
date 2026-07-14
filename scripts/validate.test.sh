#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERENA_PROBE=""
SECRET_PROBE=""

cleanup() {
  [ -z "${SERENA_PROBE}" ] || rm -f "${SERENA_PROBE}"
  [ -z "${SECRET_PROBE}" ] || rm -f "${SECRET_PROBE}"
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

echo "Validation regression tests passed."
