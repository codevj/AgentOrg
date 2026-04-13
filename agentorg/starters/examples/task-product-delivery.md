# Task: Add Rate Limiting to the Public API

## Problem

Our public API has no rate limiting. A single client can send unlimited requests, which risks service degradation for other users and increases infrastructure costs. Last week a misconfigured bot sent 50K requests in an hour.

## Appetite

Medium — full team execution. This touches auth middleware, API gateway config, and needs testing under load.

## Solution

Add token-bucket rate limiting at the API gateway level with per-client limits based on API key tier. Return 429 with Retry-After header when limits are exceeded. Log rate limit events for monitoring.

## Rabbit Holes

- Do not build a custom rate limiter — use the existing gateway middleware
- Do not change the API key issuance flow — just consume existing tiers
- Avoid per-endpoint rate limits for now — start with a global per-client limit

## No-gos

- No changes to billing or pricing tiers
- No retroactive enforcement on existing clients
- No rate limiting on internal service-to-service calls

## Acceptance Criteria

- [ ] Rate limiting enforced per API key
- [ ] 429 response with Retry-After header when limit exceeded
- [ ] Rate limit events logged with client ID and endpoint
- [ ] Existing tests pass
- [ ] Load test confirms limits are enforced under concurrent requests

## Validation Commands

```bash
npm test
npm run test:integration
npm run lint
```
