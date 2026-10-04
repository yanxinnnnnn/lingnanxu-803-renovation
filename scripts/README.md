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
