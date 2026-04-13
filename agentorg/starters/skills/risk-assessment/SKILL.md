---
name: risk-assessment
description: Identify risks, failure modes, and mitigations. Use when evaluating plans, designs, or decisions for potential problems.
license: Apache-2.0
metadata:
  author: agentorg
  version: "1.0"
---

# Risk Assessment

## When to use this skill

Use when evaluating a plan, design, strategy, or decision for potential failure modes and risks.

## Process

1. List assumptions the plan depends on — what must be true for this to work?
2. For each assumption, ask: what happens if this is wrong?
3. Identify external risks — dependencies, market changes, regulatory shifts
4. Identify execution risks — team capability, timeline, technical complexity
5. Rate each risk: likelihood (high/medium/low) x impact (high/medium/low)
6. Propose mitigations for high-likelihood or high-impact risks

## Risk categories

- **Correctness**: Will this produce the wrong result?
- **Safety/Security**: Could this cause harm or exposure?
- **Scope creep**: Will this grow beyond what was approved?
- **Dependency**: Does this rely on something outside our control?
- **Reversibility**: Can we undo this if it goes wrong?

## What to avoid

- Do not list every conceivable risk — focus on the ones that matter
- Do not propose mitigations more expensive than the risk they address
- Do not use risk assessment to block action — the goal is informed action, not paralysis
