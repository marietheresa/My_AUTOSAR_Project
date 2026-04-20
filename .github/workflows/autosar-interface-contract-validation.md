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

Write and run a Python script to perform value-level comparison between ARXML definitions and generated C code. Use Python 3.11+ with standard library only (`xml.etree.ElementTree`, `re`, `pathlib`).

**Important**: ARXML files use XML namespace `http://autosar.org/schema/r4.0`. All element lookups must use this namespace prefix.

### Check 1: CAN Configuration Values

Compare parameter values in `MCAL/McalCfg/Can_EcucValues.arxml` against generated C in `MCAL/McalGen/Can_PBcfg.c` and `MCAL/McalGen/Can_Cfg.h`.

**Baud rate check:**
- In the ARXML, find the `ECUC-NUMERICAL-PARAM-VALUE` whose `DEFINITION-REF` ends with `CanControllerBaudRate` and extract its `VALUE`.
- In `Can_PBcfg.c`, extract the integer values assigned to `.CanControllerBaudRate` and `.CanControllerDefaultBaudrate` using regex.
- All three values must be identical. Report a violation if they differ.

**Dev error detection check:**
- In the ARXML, find the `ECUC-NUMERICAL-PARAM-VALUE` whose `DEFINITION-REF` ends with `CanDevErrorDetection` and extract its `VALUE` (`true` or `false`).
- In `Can_Cfg.h`, extract the value of `#define CAN_DEV_ERROR_DETECT` (either `STD_ON` or `STD_OFF`).
- Map: ARXML `true` must correspond to `STD_ON`, ARXML `false` must correspond to `STD_OFF`. Report a violation if they don't match.

### Check 2: DIO Channel Consistency

Compare DIO channel definitions in `MCAL/McalCfg/Dio_EcucValues.arxml` against `MCAL/McalGen/Dio_Cfg.h`.

- In the ARXML, collect all `SHORT-NAME` values from containers whose `DEFINITION-REF` ends with `DioChannel`. These are the contracted channel names (e.g., `LED1`, `LED2`, `D7`, `D8`).
- In `Dio_Cfg.h`, extract all channel names from `#define DioConf_DioChannel_<NAME>` patterns.
- Perform a **set comparison**:
  - **Phantom channels**: names in C code but NOT in ARXML (channels added without updating the contract).
  - **Missing channels**: names in ARXML but NOT in C code (contract channels not implemented).
- Report each discrepancy as a violation.

### Check 3: DIO Channel ID Values

For channels that exist in both ARXML and C code, compare their numeric ID values.

- In the ARXML, extract the `DioChannelId` value for each channel.
- In `Dio_Cfg.h`, extract the numeric value from `#define DioConf_DioChannel_<NAME> <VALUE>`.
- Report a violation if any channel ID values differ.

### Output

1. Write a markdown-formatted compliance report to `$GITHUB_STEP_SUMMARY` with:
   - `## AUTOSAR Interface Contract Compliance Report`
   - `### Scope` — list of files analyzed
   - `### Findings` — each violation with the ARXML value, C code value, and file paths
   - `### Result` — `✅ PASS` or `❌ FAIL`

2. When triggered by a pull request, also post the same report as a PR comment using the `add-comment` safe output.
   - If there are no violations, post: `✅ AUTOSAR interface contract compliance check passed – no violations found.`

3. Exit `0` when no violations are found. Exit non-zero when any violation is found.

## Output format requirements

Use this structure for both the job summary and the PR comment:
- `## AUTOSAR Interface Contract Compliance Report`
- `### Scope` (list of files analyzed)
- `### Findings` (each violation with ARXML expected value, C actual value, and file paths)
- `### Result` (`✅ PASS` or `❌ FAIL`)
