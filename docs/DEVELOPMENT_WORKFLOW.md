# Development Workflow

## Implementation lifecycle

1. Product Owner and Design Lead agree on the goal.
2. Design Lead writes a GitHub Issue as the implementation specification.
3. Codex implements on a branch.
4. Codex runs required checks and records results.
5. ChatGPT reviews the diff and generated artifacts.
6. Product Owner accepts or requests changes.
7. Accepted work is merged.

## Issue contract

Implementation Issues should contain:
- context
- objective
- in scope / out of scope
- source-of-truth inputs
- required files
- constraints
- acceptance criteria
- validation commands
- expected artifacts

If code and Issue text disagree, clarify the Issue before treating the implementation as complete.

## Commit guidance

Prefer small, descriptive commits such as:

```text
Add B0 floorplan data model
Generate B0 DXF from structured data
Add geometry validation checks
Render B0 preview from generated DXF
```

Avoid commit messages like `update`, `fix stuff`, or `final`.

## Generated files

Generated files must clearly state their source baseline and precision level.

For B0:
- no fabricated measured dimensions;
- no construction-ready claims;
- estimated geometry must remain identifiable as estimated.

## Review checklist

Before accepting implementation work:
- does it satisfy the Issue?
- can it be regenerated from a clean checkout?
- are assumptions explicit?
- are source files preserved?
- are units consistent?
- are generated artifacts visually sane?
- are B0/B1 precision boundaries respected?
