# Handoff Schema

Each role must output:

1. `input_digest`
2. `decision`
3. `rationale`
4. `artifacts`
5. `risks`
6. `exit_status` (`pass` or `blocked`)

## Severity scale for findings

- `high`: release-blocking, correctness or safety risk
- `medium`: must-fix before merge
- `low`: non-blocking improvement

## Enforcement rules

- Team mode cannot advance if `exit_status` is `blocked`
- Reviewer `high` or `medium` findings must be resolved before final pass
- Tester must provide command evidence for failed checks

## Final run summary

1. `mode`
2. `team`
3. `changed_files`
4. `validation_results`
5. `review_findings`
6. `residual_risks`
7. `next_actions`
