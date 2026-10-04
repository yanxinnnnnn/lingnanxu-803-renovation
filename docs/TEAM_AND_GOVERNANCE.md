# Team & Governance

This repository treats the renovation as a small engineering/design project with explicit ownership and review boundaries.

## Roles

### Homeowner / Product Owner — Yanxin

Final authority for:
- family needs and lifestyle priorities
- budget and scope
- layout selection
- aesthetic direction
- acceptance of each baseline
- approval of irreversible real-world work

The Product Owner decides **what should be built** and accepts or rejects the result.

### Design Lead / PM / Reviewer — ChatGPT

Responsible for:
- requirement discovery
- space-planning proposals
- design rationale and trade-off analysis
- milestone / sprint planning
- GitHub issue specifications
- review of Codex implementation
- baseline management
- identifying unknowns, assumptions, risks, and required measurements
- reviewing contractor / designer outputs later in the project

ChatGPT should not present estimated geometry as measured fact and should not replace licensed / on-site professionals for structural or construction-safety decisions.

### Implementation Engineer — Codex

Responsible for:
- repository implementation work
- Python tooling
- structured floor-plan data
- DXF generation
- preview / validation scripts
- automated checks
- tests and reproducible outputs
- documentation changes required by implementation
- preparing reviewable commits / pull requests

Codex implements a written specification. It does **not** independently make family, aesthetic, budget, structural, or irreversible construction decisions.

### Field Validation Authority — On-site professionals

Later in the project this role may include:
- survey / measurement personnel
- interior designer
- contractor
- structural / MEP professionals
- cabinet / door / window vendors

They are the authority for real-world dimensions and construction feasibility where on-site verification is required.

## Decision hierarchy

```text
Homeowner / Product Owner
        │
        │ goals, constraints, acceptance
        ▼
ChatGPT — Design Lead / PM
        │
        │ implementation specification
        ▼
Codex — Implementation Engineer
        │
        │ reproducible artifacts
        ▼
ChatGPT — Review
        │
        ▼
Homeowner — Acceptance
        │
        ▼
Field professional validation when physical work is involved
```

## Source-of-truth hierarchy

When sources disagree, use the highest available authority:

1. verified on-site measurement / approved construction documentation
2. official developer / architectural documentation
3. structured project data derived from verified sources
4. marketing plan / showroom video
5. visual estimation

Every dimension or geometry assumption should carry enough provenance to know which level it came from.

## Change governance

- GitHub Issues define implementation scope for Codex.
- Major design choices are recorded as ADRs in `decisions/`.
- Major project states are frozen as baselines: B0, B1, L1, D1, C1, H1.
- Do not silently overwrite raw source material.
- Do not silently upgrade an estimated value to a measured value.
- Any change that affects a frozen baseline must record why the baseline changed.

## Git workflow

During bootstrap, direct commits to `main` are acceptable.

After the reproducible B0 toolchain is established:
1. implementation work should normally use a dedicated branch;
2. Codex prepares the change and validation evidence;
3. ChatGPT reviews against the Issue specification;
4. the Product Owner performs final acceptance;
5. merge to `main` only after acceptance.

For changes that are documentation-only and trivial, direct updates may still be used when explicitly requested by the Product Owner.

## Safety boundary

No generated B0 artifact may be used as authority for:
- structural demolition
- wall setting-out
- electrical / plumbing positioning
- gas work
- door / window fabrication
- cabinetry fabrication
- other irreversible construction work

Those require B1-or-later verified dimensions plus appropriate field validation.
