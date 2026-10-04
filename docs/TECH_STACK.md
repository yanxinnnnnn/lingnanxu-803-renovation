# Technical Stack

The stack is intentionally lightweight: easy to reproduce, easy for Codex to automate, and friendly to a homeowner who does not need to become a full-time CAD specialist.

## Repository & project management

- **GitHub** — canonical project history, Issues, review, documentation
- **Git** — version control for text, code, YAML/CSV, and DXF where practical
- **Google Drive** — persistent storage for large binary reference assets such as videos
- **Markdown** — human-readable specifications, ADRs, notes, reviews
- **YAML** — structured project and floor-plan data
- **CSV** — measurements, budget, procurement, comparison tables when tabular data is appropriate

## Automation

- **Python 3.12+**
- **uv** — Python environment / dependency / command management
- **ezdxf** — DXF generation and inspection
- **PyYAML** — structured floor-plan input
- **Pillow** — reference-image processing when needed
- **Matplotlib / ezdxf drawing utilities** — generated preview images
- **pytest** — automated validation tests

The preferred pattern is:

```text
structured YAML data
       ↓
Python generator
       ↓
DXF
       ↓
validator + preview renderer
       ↓
reviewable artifacts
```

## 2D CAD

### Primary interchange format
- **DXF**

Reasons:
- text-based and script-friendly
- broadly supported
- suitable for generated geometry
- easier to inspect and version than proprietary binary formats

### Human viewing / editing
- **LibreCAD** — preferred lightweight viewer/editor during early phases
- **AutoCAD / ZWCAD / GstarCAD** — optional later, especially when exchanging DWG with professional designers or contractors

### DWG policy
DWG may be exchanged with professionals but is treated as a binary deliverable, not the canonical machine-readable project source.

## 3D and visualization

Planned after the L1 layout baseline:

- **SketchUp** — practical residential 3D modeling
- **D5 Render** — real-time / photorealistic visualization

3D models and renders are downstream artifacts. They must not override verified 2D geometry or measurement data.

## Data model principles

Geometry must distinguish provenance:

- `estimated`
- `official`
- `measured`

Every geometry record that can affect physical design should eventually support:
- unique id
- category
- coordinates / dimensions
- unit
- source
- confidence / provenance
- notes

B0 data is expected to be `estimated` unless explicitly documented otherwise.

## File policy

### Keep in Git
- `.md`
- `.yaml` / `.yml`
- `.csv`
- `.py`
- `.toml`
- generated `.dxf` when reasonably sized

### Keep in external binary storage unless there is a strong reason otherwise
- `.mp4` / `.mov`
- `.dwg`
- `.skp`
- high-resolution renders
- raw photo / video archives
- PSD / other heavy design files

Git keeps the manifest, metadata, checksums, and design history for externally stored canonical assets.

## Reproducibility requirement

A generated CAD artifact is not considered canonical merely because it exists.

For scripted stages, the canonical package is:
1. source data;
2. generator code;
3. dependency definition;
4. validation command;
5. generated artifact.

The project should be able to regenerate the same B0 geometry from a clean checkout.
