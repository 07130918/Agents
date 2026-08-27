#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="${ROOT}/codex/skills/review-remediation-harness"
TESTS="${ROOT}/tests/review_harness_artifacts"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="${PROJECT}/src:${TESTS}"

uv run --isolated --frozen --project "${PROJECT}" \
  python -m unittest discover -s "${TESTS}" -p 'test_*.py' -v

uv run --isolated --frozen --project "${PROJECT}" \
  review-harness-artifacts --version >/dev/null

echo "Review Harness artifact tests passed."
