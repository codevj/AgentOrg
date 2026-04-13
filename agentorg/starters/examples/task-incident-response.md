# Task: Investigate and Resolve API Latency Spike

## Problem

Starting at 14:00 UTC today, API response times jumped from p95 of 200ms to p95 of 2.5s. Customer-facing impact confirmed — support tickets increasing. The latency spike correlates with a deployment at 13:45 UTC but the change was a minor config update.

## Appetite

Small — fast turnaround needed. Use the incident response team but prioritize speed over exhaustive analysis.

## Solution

Triage the incident, identify root cause, draft a resolution plan with rollback option, and get review sign-off before implementing.

## Rabbit Holes

- Do not refactor the monitoring system as part of this fix
- Do not investigate historical latency patterns — focus on what changed today
- Avoid premature optimization — find the cause, fix it, move on

## No-gos

- No changes to unrelated services
- No database migrations as part of the fix
- No disabling monitoring or alerting to "fix" the symptoms

## Acceptance Criteria

- [ ] Severity and blast radius documented
- [ ] Root cause identified with evidence
- [ ] Fix targets root cause, not symptoms
- [ ] Rollback plan exists
- [ ] Prevention measure identified
- [ ] Latency returns to baseline after fix

## Validation Commands

```bash
curl -w "%{time_total}" https://api.example.com/health
npm run test:integration
```
