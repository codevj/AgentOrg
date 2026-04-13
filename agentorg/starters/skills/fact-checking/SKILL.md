---
name: fact-checking
description: Verify factual claims against sources. Use when content makes assertions that need validation.
license: Apache-2.0
metadata:
  author: agentorg
  version: "1.0"
---

# Fact Checking

## When to use this skill

Use when reviewing content that makes factual claims — blog posts, reports, documentation, or any deliverable that asserts something is true.

## Process

1. Extract every factual claim from the content
2. For each claim, identify the source (if cited) or flag as unsourced
3. Verify the claim against the source — does the source actually say this?
4. Rate source reliability (primary source > secondary > tertiary)
5. Flag claims that are outdated (check publication dates)
6. Flag claims that are technically accurate but misleading in context

## Verdict categories

- **verified**: Claim matches a reliable, current source
- **unverified**: No source found; may be true but cannot confirm
- **inaccurate**: Claim contradicts available evidence
- **outdated**: Claim was true but circumstances have changed
- **misleading**: Technically accurate but presented in a way that implies something false

## What to avoid

- Do not flag opinions or subjective statements as "inaccurate"
- Do not require sources for common knowledge
- Do not mark something as verified just because it sounds right
