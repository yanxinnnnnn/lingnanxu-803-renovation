# Measurements

这里保存 803 的现场量房记录、官方尺寸索引与量房工作表。

## 当前来源与边界

| Provenance | 含义 | 当前使用 |
| --- | --- | --- |
| onsite_measured / official | 803 的现场证据或适用的官方文件 | B1 待建立 |
| third_party_reference | 相似户型的第三方数据 | B0.2 provisional，仅参考 |
| estimated | 营销图像素追踪/视觉估算 | B0.1 canonical geometry |

来源层级不代表可自动转化。原有 `measured` 泛称不能用于标注第三方数据为 803 实测。
**B0.1 和 B0.2 均不可施工，B1 需要独立的 803 证据与验收。**

`references/source-manifest.yaml` 中的 `measurement-ref-001` 登记 Google Drive 原图路径、
checksum、范围、provenance、confidence 与 observed totals。脚本直接消费该登记，
不下载/更改原始图、不 OCR。Issue #3 已提供清晰可读值，十个面积都没有可靠房间位置，
所以用 `ref_area_01` 至 `ref_area_10` 表示清单条目，`mapping_status: unresolved`、`room_id: null`。
这些 ID 不表示房间或图中空间顺序；没有额外录入模糊数值。`linear_dimensions: []`
是明确的资料缺口，待现场收集，不从面积或 B0 像素尺度推导长度。

## 数据与命令

`data/b0_provisional_measurements.yaml` 保留根级 `source_id`、`baseline: B0`、
`provenance: third_party_reference`、`confidence: provisional`、`subject_unit_match: false`，
以及 `construction_ready: false`。每个 reported total、area 或 linear dimension
都有自身的 source/provenance/confidence、单位和 `verification_status: pending_onsite_verification`。
本次 schema 强制未决 mapping；以后若需要映射，须另附证据并经 review 扩展。

`reported_totals.measured_internal_area_sqm` 使用 Issue #3 的原字段名，**只是第三方图报告的
internal/usable area 124.518㎡**，不是 803 实测面积。building area 118.4494㎡ 和 reported
space efficiency 105.12% 也按来源原样记录；不求和未映射 zones，不重新推算或“修正”来源 totals。

从仓库根目录执行：

```bash
uv sync
uv run python scripts/validate_provisional_measurements.py
uv run python scripts/generate_provisional_overlay.py
uv run python scripts/validate_provisional_measurements.py --dxf cad/LN803_REF_B0.2_provisional_20261004.dxf
uv run pytest
```

生成命令一次输出单独 DXF 和 PNG，不修改旧文件；验证命令失败时返回非零状态。
`--help` 列出自定义 `--data`、`--manifest`、`--base-dxf` 与输出选项；例如：

```bash
uv run python scripts/generate_provisional_overlay.py --output artifacts/ref-review.dxf --preview artifacts/ref-review.png
uv run python scripts/validate_provisional_measurements.py --dxf artifacts/ref-review.dxf
```

默认输出：

- `cad/LN803_REF_B0.2_provisional_20261004.dxf`
- `artifacts/LN803_REF_B0.2_provisional_20261004_preview.png`

新图层 `A-REF-PROVISIONAL` 为紫色，独立 XDATA 为 `LN803_REF_PROVISIONAL`，
明确保留 `third_party_reference`、`provisional`、待现场验证和非 subject-unit match 状态。
原 B0 的 `LN803_B0 / estimated` 实体逐一保持不变。PNG 使用原 B0 renderer 的临时输出
呈现平面，旁边用新 DXF 的注记显示参考值。未决数据没有放到任何房间上。
输出路径保护阻止覆盖 canonical B0 artifacts 和输入资料。

## 803 现场工作表与 B1 交接

使用 [onsite-survey-803.md](onsite-survey-803.md)，现场数值一律记录 mm。
表内覆盖整体净高/跨度/过道/可见墙厚、四个卧室、客餐/多功能区、厨房、三个卫生间、
入户/鞋帽/家政/生活阳台，并留出数值、单位、方法/来源、照片/视频、置信度及备注栏。
P0 优先净尺寸、跨度、门窗和关键过渡宽度；P1 补充柜位与可观察点位。

回访后：

1. 保存有日期、单位、测法、起止完成面及照片索引的原始 803 记录。
2. 为实际现场结果创建新的 `onsite_measured` 来源/数据；适用官方文件独立登记为 `official`。
3. 对照参考图记录不同处，复核关键跨度/开口与未观察项，不按数值相近自动对应房间。
4. 用新证据重建 B1；经 review 和 Product Owner 验收后，再替代布局使用的 provisional / estimated 值。
5. 保留 B0.1、B0.2、第三方原始资料与原 provenance；不把第三方记录直接改为现场实测。
