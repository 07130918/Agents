#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERENA_PROBE=""
SECRET_PROBE=""
FALSE_POSITIVE_PROBE=""
ACTIVE_AGENT_PROBE=""
DUPLICATE_SKILL_PROBE=""

cleanup() {
  [ -z "${SERENA_PROBE}" ] || rm -f "${SERENA_PROBE}"
  [ -z "${SECRET_PROBE}" ] || rm -f "${SECRET_PROBE}"
  [ -z "${FALSE_POSITIVE_PROBE}" ] || rm -f "${FALSE_POSITIVE_PROBE}"
  [ -z "${ACTIVE_AGENT_PROBE}" ] || rmdir "${ACTIVE_AGENT_PROBE}"
  [ -z "${DUPLICATE_SKILL_PROBE}" ] || rmdir "${DUPLICATE_SKILL_PROBE}"
}
trap cleanup EXIT

mkdir -p "${ROOT}/.serena"
SERENA_PROBE="$(mktemp "${ROOT}/.serena/validate-test.XXXXXX")"
printf 's%s\n' 'k-validation-probe' >"${SERENA_PROBE}"

if ! "${ROOT}/scripts/validate.sh" >/dev/null; then
  echo "Validation must ignore .serena runtime state." >&2
  exit 1
fi

FALSE_POSITIVE_PROBE="$(mktemp "${ROOT}/validate-risk-reviewer-test.XXXXXX")"
printf '%s\n' 'name = "pr-risk-reviewer"' >"${FALSE_POSITIVE_PROBE}"

if ! "${ROOT}/scripts/validate.sh" >/dev/null; then
  echo "Validation must not treat pr-risk-reviewer as an API key." >&2
  exit 1
fi

rm -f "${FALSE_POSITIVE_PROBE}"
FALSE_POSITIVE_PROBE=""

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

ACTIVE_AGENT_PROBE="${ROOT}/claude/agents"
mkdir "${ACTIVE_AGENT_PROBE}"

if output="$("${ROOT}/scripts/validate.sh" 2>&1)"; then
  echo "Validation must reject an active Claude Code agents directory." >&2
  exit 1
fi

if [[ "${output}" != *"Claude Code agents must remain disabled"* ]]; then
  echo "Validation failed for an unexpected reason: ${output}" >&2
  exit 1
fi

rmdir "${ACTIVE_AGENT_PROBE}"
ACTIVE_AGENT_PROBE=""

DUPLICATE_SKILL_PROBE="${ROOT}/claude/skills.disabled/visualize-architecture-flow"
mkdir "${DUPLICATE_SKILL_PROBE}"

if output="$("${ROOT}/scripts/validate.sh" 2>&1)"; then
  echo "Validation must reject a Claude Code skill that is both active and disabled." >&2
  exit 1
fi

if [[ "${output}" != *"Claude Code skill cannot be both active and disabled"* ]]; then
  echo "Validation failed for an unexpected reason: ${output}" >&2
  exit 1
fi

rmdir "${DUPLICATE_SKILL_PROBE}"
DUPLICATE_SKILL_PROBE=""

echo "Validation regression tests passed."
