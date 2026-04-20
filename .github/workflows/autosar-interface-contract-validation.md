---
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
  workflow_dispatch:

permissions:
  contents: read
  pull-requests: read
  issues: read

engine: copilot

tools:
  github:
    toolsets: [default]

network: defaults
timeout-minutes: 30

safe-outputs:
  add-comment:
    max: 1
---

# AUTOSAR Interface Contract Compliance Validation

Validate AUTOSAR interface contract compliance by checking for drift between:
1. ARXML interface definitions (source of truth)
2. C source/header implementation
3. Project documentation

## Rules

- Do not modify repository files.
- Do not create pull requests or issues.
- Always produce a job summary in `$GITHUB_STEP_SUMMARY`.
- When the trigger is a pull request, also post a PR comment with the findings via the `add-comment` safe output.
- Fail the run if one or more violations are found.

## Validation procedure

1. Discover files:
   - ARXML: `**/*.arxml`
   - C code: `**/*.c`, `**/*.h`
   - Documentation: `README*`, `**/*.md`, `**/*.rst`, `**/*.txt`

2. Build an ARXML contract map using a script (Python is preferred):
   - Use Python 3.11+ with standard library only (`xml.etree.ElementTree`, `re`, `pathlib`, `json`) to avoid dependency/setup drift.
   - Parse XML with namespace-safe matching.
   - Extract interface-like and port/data-signal-like identifiers from element tags and `SHORT-NAME` values.
   - Build a unique canonical set of contract identifiers.

3. Build code and documentation identifier sets:
   - From C files and docs, extract candidate identifiers using robust tokenization (word boundaries, snake/camel case-friendly patterns).
   - Treat AUTOSAR interface-like identifiers as tokens matching `\b[A-Za-z][A-Za-z0-9_]*\b`.
   - Keep all matches as raw candidates.
   - Apply a second-pass filter that marks as high-confidence AUTOSAR references only tokens containing contract cues such as `Port`, `Interface`, `If`, `Com`, `Pdu`, `Signal`, `DataElement`, `Require`, `Provide`, `Rx`, `Tx`.
   - Use the high-confidence set for undeclared-usage checks, and keep the full candidate set only as supporting context in the report.
   - Exclude obvious C language keywords and generic prose/common stop words when scanning documentation.
   - Normalize to a comparable canonical format (case-insensitive with separator normalization).

4. Compare and detect violations:
   - **Missing in code**: identifiers defined in ARXML but not found in C code.
   - **Missing in docs**: identifiers defined in ARXML but not found in documentation.
   - **Undeclared usage**: identifiers that look like AUTOSAR interface references in C/docs but are not present in ARXML.
   - Record enough context (identifier + representative file/path evidence) to make findings actionable.

5. Produce the job summary:
   - Include total counts per violation type.
   - Include concise tables/lists of findings.
   - Include explicit pass/fail conclusion.

6. When triggered by a pull request, also post a PR comment using the `add-comment` safe output.
   - The comment must contain the same findings as the job summary.
   - If there are no violations, post a brief comment confirming compliance (`✅ AUTOSAR interface contract compliance check passed – no violations found.`).

7. Set exit status:
   - Exit `0` when no violations are found.
   - Exit non-zero when any violation is found.

## Output format requirements

Use this structure for both the job summary and the PR comment:
- `## AUTOSAR Interface Contract Compliance Report`
- `### Scope` (counts of ARXML, C, and doc files analyzed)
- `### Findings` (grouped by violation type)
- `### Result` (`✅ PASS` or `❌ FAIL`)

If no files are found for a category, add that as a finding and fail the run because validation scope is incomplete.
