# Team Mode

For larger tasks requiring quality gates.

## Default role order

1. Program Manager
2. Architect
3. Developer
4. Tester
5. Code Reviewer

## Gate rules

- No role may skip required handoff schema sections
- Developer must stay within architect-approved file scope
- Tester must run command-based validation before reviewer starts

If review finds high/medium issues, loop:

`Developer -> Tester -> Code Reviewer`

until no high/medium findings remain.
