# Scripts

Python 3.12 / uv CLI entry points for Issue #1:

- `validate_floorplan.py`: validate YAML and generated geometry/layers; `--dxf` also verifies a saved DXF.
- `generate_b0_dxf.py`: generate deterministic R2010 DXF from `data/b0_floorplan.yaml`.
- `render_preview.py`: render the validated DXF to a PNG review preview with matplotlib Agg.
- `floorplan.py`: shared data contract, paths and estimated coordinate transform.

Run `uv sync`, then `uv run python scripts/<entry_point>.py`; `--help` lists path options.
Run `uv run pytest` for acceptance tests. See [CAD instructions](../cad/README.md)
for the full generation and validation cycle.

All B0 geometry is estimated. No generated output is construction-ready.
B1 verified dimensions will supersede B0.

Issue #3 adds separate entry points without changing the B0.1 pipeline:

- `validate_provisional_measurements.py`: validate B0.2 reference provenance and registered source; `--dxf` also checks the saved overlay, warning and unchanged B0 entities.
- `generate_provisional_overlay.py`: generate a separate DXF/PNG with purple `A-REF-PROVISIONAL` annotations. Original B0 files and inputs cannot be used as output paths.
- `provisional_measurements.py`: small reference model, annotation schedule and overlay validation.

See [Measurements](../measurements/README.md) for commands and the onsite worksheet.
The new layer uses `third_party_reference / provisional`, pending onsite verification.

Issue #5 adds independent B0.3 entry points:

- `validate_layout_input.py`: enforce the exact Issue-authorized semantic associations, area-only constraints, unresolved states and record provenance; `--dxf` verifies the saved overlay.
- `generate_layout_input.py`: generate separate B0.3 DXF/PNG with high/medium/unresolved styling and no new geometric/dimension entities.
- `layout_input.py`: the small semantic model and review annotation contract. B0.2 transcription stays unchanged.

See [B0.3 summary](../docs/B0.3_LAYOUT_INPUT.md) for commands, conceptual use and onsite questions.

Issue #9 adds a separate concept pipeline over the unchanged B0 trace:

- `layout_concepts.py`: room-role and strategy contract, source-checked requirement labels, TEXT-only DXF validation.
- `generate_layout_concepts.py`: separate deterministic Layout A/B/C DXFs and PNG review sheets; `--concept` selects one and `--output-dir` selects an isolated root.
- `validate_layout_concepts.py`: validates all concepts; `--artifacts` also checks saved DXFs and PNGs.

See [Layout comparison](../docs/LAYOUT_CONCEPTS_v0.1.md) for regeneration commands,
strategies, assumptions and B1 blockers. Prior baselines and unrelated existing output
files are protected. Concept labels are uses only; no geometry, dimensions or exact
furniture-fit claims are added. B1/L1 remain pending; Product Owner selects after review.
