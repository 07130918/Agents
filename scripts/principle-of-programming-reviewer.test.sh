#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REFERENCE="${ROOT}/shared/references/principle-of-programming-reviewer.md"
EVALS="${ROOT}/shared/evals/principle-of-programming-reviewer.yml"
CODEX_WRAPPER="${ROOT}/codex/skills/principle-of-programming-reviewer/SKILL.md"
CLAUDE_WRAPPER="${ROOT}/claude/skills.disabled/principle-of-programming-reviewer/SKILL.md"

assert_contains() {
  local file="$1"
  local expected="$2"

  if ! grep -Fq -- "${expected}" "${file}"; then
    echo "Missing required popr contract text in ${file}: ${expected}" >&2
    exit 1
  fi
}

for required_file in "${REFERENCE}" "${EVALS}" "${CODEX_WRAPPER}" "${CLAUDE_WRAPPER}"; do
  if [ ! -f "${required_file}" ]; then
    echo "Missing popr contract file: ${required_file}" >&2
    exit 1
  fi
done

if [ -e "${ROOT}/claude/skills/principle-of-programming-reviewer" ]; then
  echo "The Claude Code popr wrapper must remain disabled." >&2
  exit 1
fi

codex_description="$(ruby -ryaml -e '
  content = File.read(ARGV.fetch(0))
  frontmatter = content.match(/\A---\n(.*?)\n---/m)&.captures&.first
  abort("Missing frontmatter") unless frontmatter
  puts YAML.safe_load(frontmatter, permitted_classes: [], aliases: false).fetch("description")
' "${CODEX_WRAPPER}")"
claude_description="$(ruby -ryaml -e '
  content = File.read(ARGV.fetch(0))
  frontmatter = content.match(/\A---\n(.*?)\n---/m)&.captures&.first
  abort("Missing frontmatter") unless frontmatter
  puts YAML.safe_load(frontmatter, permitted_classes: [], aliases: false).fetch("description")
' "${CLAUDE_WRAPPER}")"

if [ "${codex_description}" != "${claude_description}" ]; then
  echo "Codex and Claude Code popr descriptions must match." >&2
  exit 1
fi

assert_contains "${CLAUDE_WRAPPER}" 'Bash(gh pr view *)'
assert_contains "${CLAUDE_WRAPPER}" 'Bash(gh pr diff *)'

required_contract_texts=(
  '対象fingerprintを固定する'
  'base branchとexact base SHA'
  'exact head SHA'
  'working tree manifest'
  '異なるfingerprintのgradeは比較しない'
  '## Coverage gate'
  'Evaluation deferred'
  'Introduced'
  'Exposed'
  'Pre-existing'
  'Out-of-scope'
  '| confidence | `High` / `Medium` / `Low`と短い理由 |'
  '| minimal_fix | goalを満たす最小修正案。修正不要ならその理由 |'
  '| Critical 1件以上 | Request changes | F |'
  '| Critical 0件、Major 4件以上 | Request changes | D |'
  '| Critical 0件、Major 2〜3件 | Request changes | C |'
  '| Critical 0件、Major 1件 | Request changes | B |'
  '| Critical 0件、Major 0件、Minor 1件以上 | Comment | A |'
  '| Critical 0件、Major 0件、Minor 0件 | Approve | A |'
  '100%の確信や無欠陥を意味しない'
  '同じ修正者・同じコンテキストによる自己再レビュー'
  '単独では保証しない'
)

for required_text in "${required_contract_texts[@]}"; do
  assert_contains "${REFERENCE}" "${required_text}"
done

ruby -ryaml -e '
  path = ARGV.fetch(0)
  document = YAML.safe_load(File.read(path), permitted_classes: [], aliases: false)
  scenarios = document.fetch("scenarios")
  abort("Expected at least 7 popr scenarios") if scenarios.length < 7

  splits = scenarios.map { |scenario| scenario.fetch("split") }.uniq
  abort("Missing representative scenarios") unless splits.include?("representative")
  abort("Missing hold-out scenarios") unless splits.include?("hold-out")

  required_ids = %w[
    stable-neutral
    stable-neutral-repeat
    stable-pressure
    changed-fingerprint
    partial-coverage
    origin-classification
    clean-diff
    project-rule-precedence
  ]
  ids = scenarios.map { |scenario| scenario.fetch("id") }
  abort("Scenario IDs must be unique") unless ids.uniq.length == ids.length
  missing_ids = required_ids - ids
  abort("Missing required scenarios: #{missing_ids.join(", ")}") unless missing_ids.empty?

  allowed_origins = %w[Introduced Exposed Pre-existing Out-of-scope]
  observed_origins = scenarios.flat_map { |scenario| scenario.fetch("findings", []) }
    .map { |finding| finding.fetch("origin") }
    .uniq
  missing_origins = allowed_origins - observed_origins
  abort("Missing origin fixtures: #{missing_origins.join(", ")}") unless missing_origins.empty?

  scenarios.each do |scenario|
    coverage_complete = scenario.fetch("coverage_complete")
    unresolved_contract = scenario.fetch("unresolved_contract", false)
    all_findings = scenario.fetch("findings", [])
    all_findings.each do |finding|
      abort("Unknown severity in #{scenario.fetch("id")}") unless %w[Critical Major Minor Nit].include?(finding.fetch("severity"))
      abort("Unknown origin in #{scenario.fetch("id")}") unless allowed_origins.include?(finding.fetch("origin"))
      abort("Missing evidence in #{scenario.fetch("id")}") if finding.fetch("evidence").strip.empty?
    end
    findings = all_findings
      .select { |finding| %w[Introduced Exposed].include?(finding.fetch("origin")) }
    critical = findings.count { |finding| finding.fetch("severity") == "Critical" }
    major = findings.count { |finding| finding.fetch("severity") == "Major" }
    minor = findings.count { |finding| finding.fetch("severity") == "Minor" }

    expected = if !coverage_complete || unresolved_contract
      { "verdict" => "Evaluation deferred", "grade" => nil }
    elsif critical.positive?
      { "verdict" => "Request changes", "grade" => "F" }
    elsif major >= 4
      { "verdict" => "Request changes", "grade" => "D" }
    elsif major >= 2
      { "verdict" => "Request changes", "grade" => "C" }
    elsif major == 1
      { "verdict" => "Request changes", "grade" => "B" }
    elsif minor.positive?
      { "verdict" => "Comment", "grade" => "A" }
    else
      { "verdict" => "Approve", "grade" => "A" }
    end

    actual = scenario.fetch("expected").slice("verdict", "grade")
    abort("Unexpected verdict/grade for #{scenario.fetch("id")}: #{actual} != #{expected}") unless actual == expected
  end

  neutral = scenarios.find { |scenario| scenario.fetch("id") == "stable-neutral" }
  neutral_repeat = scenarios.find { |scenario| scenario.fetch("id") == "stable-neutral-repeat" }
  pressure = scenarios.find { |scenario| scenario.fetch("id") == "stable-pressure" }
  comparable_keys = %w[current_fingerprint coverage_complete unresolved_contract findings expected]
  neutral_evidence = neutral.select { |key, _| comparable_keys.include?(key) }
  neutral_repeat_evidence = neutral_repeat.select { |key, _| comparable_keys.include?(key) }
  pressure_evidence = pressure.select { |key, _| comparable_keys.include?(key) }
  abort("Repeated neutral fixture must preserve evidence and outcome") unless neutral_evidence == neutral_repeat_evidence
  abort("Pressure prompt fixture must preserve evidence and outcome") unless neutral_evidence == pressure_evidence

  changed = scenarios.find { |scenario| scenario.fetch("id") == "changed-fingerprint" }
  abort("Changed fingerprint must be incomparable") unless changed.dig("expected", "grade_comparable") == false
  abort("Changed fingerprint fixture must change target") if changed.fetch("previous_fingerprint") == changed.fetch("current_fingerprint")

  precedence = scenarios.find { |scenario| scenario.fetch("id") == "project-rule-precedence" }
  abort("Project rules must take precedence") unless precedence.dig("expected", "governing_rule") == "project"
' "${EVALS}"

echo "Principle of Programming reviewer regression tests passed."
