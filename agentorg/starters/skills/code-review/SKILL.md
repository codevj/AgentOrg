---
name: code-review
description: Review code for correctness, security, and maintainability. Use when reviewing diffs, PRs, or implementation handoffs.
license: Apache-2.0
metadata:
  author: agentorg
  version: "1.0"
---

# Code Review

## When to use this skill

Use when reviewing code changes, pull requests, diffs, or when a developer hands off implementation for review.

## Process

1. Read the full diff before commenting on any specific line
2. Check correctness first — does the code do what it claims to do?
3. Check for security issues — injection, auth bypass, data exposure, OWASP top 10
4. Check for edge cases — null/empty inputs, concurrency, error paths
5. Check maintainability — naming, structure, unnecessary complexity
6. Check scope — does the change stay within what was approved?

## Severity classification

- **high**: Correctness bug, security vulnerability, data loss risk. Must fix before merge.
- **medium**: Logic that will cause problems under specific conditions. Must fix before merge.
- **low**: Style, naming, minor simplification. Non-blocking.

## What to skip

- Do not nitpick formatting if a linter/formatter is configured
- Do not suggest refactors outside the scope of the change
- Do not re-litigate architectural decisions made in prior steps
