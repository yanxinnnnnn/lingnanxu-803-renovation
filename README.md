# Lingnanxu 803 Renovation

> An AI-assisted, reproducible home-renovation workflow for a real 118㎡ apartment in Guangzhou — from structured floor-plan data and DXF automation to layout design, 3D visualization, budgeting, and construction baselines.

广州岭南序 6 栋 803（约 118㎡）装修设计与落地管理项目。本仓库公开记录一套真实住宅如何通过 **Homeowner + ChatGPT + Codex + CAD/3D tools** 协作，把需求、户型数据、设计决策和施工前成果做成可追踪、可复现、可审查的工程化工作流。

## 当前阶段

**Baseline: B0 — Marketing / showroom reference**

当前设计依据：
- 开发商营销户型图
- 交付样板间视频
- 尚无官方轴网/建筑尺寸或现场实测尺寸

因此，当前 CAD / DXF 仅用于空间研究和方案讨论，**不得直接用于拆改、施工、水电定位、门窗或定制下单**。

## 工作流

```text
原始资料
  ↓
B0 参考底图
  ↓
现场量房 / 官方图纸
  ↓
B1 精确基础 CAD
  ↓
A/B/C 平面方案
  ↓
L1 平面方案冻结
  ↓
3D 建模
  ↓
效果图 / 材料方案
  ↓
D1 设计冻结
  ↓
施工图
  ↓
C1 施工图冻结
  ↓
施工 / 竣工
```

## Baseline

| Baseline | 含义 | 状态 |
| --- | --- | --- |
| B0 | 营销图 + 样板间视频推导 | Active |
| B1 | 官方图纸 / 现场量房后的精确底图 | Pending |
| L1 | 平面布局冻结 | Pending |
| D1 | 设计冻结 | Pending |
| C1 | 施工图冻结 | Pending |
| H1 | 竣工 / 交付基线 | Pending |

## 目录

- `cad/`：可版本管理的 DXF、CAD 说明
- `measurements/`：量房数据、尺寸记录
- `decisions/`：重要设计决策记录（ADR）
- `budget/`：预算与报价结构化数据
- `references/`：外部原始资料索引；大文件本体不建议直接放 Git
- `scripts/`：后续用于 CAD、预算、数据转换的辅助脚本
- `data/`：B0 可复现底图的结构化来源
- `artifacts/`：用于 review 的生成预览
- `tests/`：数据、DXF、provenance 与可复现性检查

## B0.1 可复现底图

**B0 ESTIMATED PLAN — NOT FOR CONSTRUCTION。** 所有几何与标定均为视觉估算，
没有现场实测或官方建筑尺寸。B1 获得 verified dimensions 后将替代 B0 几何。

在仓库根目录执行（Python 3.12，由 uv 管理；依赖锁定在 `uv.lock`）：

```bash
uv sync
uv run python scripts/validate_floorplan.py
uv run python scripts/generate_b0_dxf.py
uv run python scripts/render_preview.py
uv run pytest
uv run python scripts/validate_floorplan.py --dxf cad/LN803_BASE_B0_v0.1_20261004.dxf
git status --short
```

完整流程生成并检查：

```text
data/b0_floorplan.yaml
  → cad/LN803_BASE_B0_v0.1_20261004.dxf
  → artifacts/LN803_BASE_B0_v0.1_20261004_preview.png
```

YAML 是几何来源；不要手工修改生成的 DXF 作为新的 source of truth。
脚本默认路径相对于仓库定位，不依赖机器的绝对路径；也支持 `--data`、`--output`，
预览脚本支持 `--dxf`。详细 schema、图层和命令见 [CAD](cad/README.md)。
首次校验检查输入及内存中生成的图层；`--dxf` 同时检查已保存的 DXF 与 YAML 一致。
无效输入返回非零状态。测试输出使用临时目录。

在已提交的干净 checkout 上，完整流程应保持 `git status --short` 无输出。
DXF 使用固定元数据与 LF 行尾；预览使用 matplotlib 自带字体和固定 PNG 元数据。
预览显示英文 room IDs，YAML 与 DXF 保留中文房间名。

Issue #1 的像素坐标原样保留，包括重叠与空隙。房间边界只是示意线，
不代表实际墙厚、承重属性或施工尺寸；本阶段不补画门扇或家具。

## B0.2 临时第三方参考与现场量房

`measurement-ref-001` 是异地相似 118–121㎡ 样板间的第三方测量图，**不是 6 栋 803**。
本层使用 `third_party_reference / provisional`，所有值均为 `pending_onsite_verification`，
`subject_unit_match: false`，不可用于施工；不改变 B0.1 几何或像素标定。

`data/b0_provisional_measurements.yaml` 消费已登记的 source manifest，并保留 Issue #3
明确提供的三项 reported totals 与十个可读面积。房间对应全部未决；线性尺寸集合为空。
不 OCR 模糊数值、不按面积猜房间、不用异地面积重新缩放 B0。

在 `uv sync` 后执行：

```bash
uv run python scripts/validate_provisional_measurements.py
uv run python scripts/generate_provisional_overlay.py
uv run python scripts/validate_provisional_measurements.py --dxf cad/LN803_REF_B0.2_provisional_20261004.dxf
uv run pytest
git status --short
```

新生成文件为 `cad/LN803_REF_B0.2_provisional_20261004.dxf` 与
`artifacts/LN803_REF_B0.2_provisional_20261004_preview.png`。
原图实体保持不变；紫色 `A-REF-PROVISIONAL` 图层在平面旁列出参考值，不给未决面积定位。
DXF 与 PNG 同时显示第三方 provisional 警告及原 B0 禁止施工警告。
原有 B0.1 命令继续有效，完整生成/测试周期保持已提交 artifacts 不变。

下次量房使用 [803 现场工作表](measurements/onsite-survey-803.md)，优先记录整体跨度、净高、
每个空间净尺寸、门窗与过渡开口，再记录柜位及可观察设备位置，现场尺寸统一为 mm。
有 803 日期/方法/照片证据的实测结果另建 `onsite_measured` 记录；官方资料另记 `official`。
不要改写第三方记录的 provenance。经复核与验收后的 B1 才替代 provisional / estimated 值；
B0.1、B0.2 和第三方原始来源持续保留。详见 [Measurements](measurements/README.md)。

## 版本规范

```text
LN803_<stage>_<content>_v<major>.<minor>_<YYYYMMDD>.<ext>
```

例如：

```text
LN803_BASE_B0_v0.1_20261004.dxf
LN803_BASE_B1_v1.0_20270118.dxf
LN803_LAYOUT_A_v0.2_20270122.dxf
LN803_LAYOUT_selected_v1.0_20270128.dxf
```

- `v0.x`：探索阶段
- `v1.0`：阶段内确认版本
- `v1.x`：小改
- `v2.0`：结构性大改

## 原则

1. 原始资料不覆盖。
2. 推测尺寸与实测尺寸必须明确区分。
3. 重大方案确认形成 baseline。
4. 重要设计取舍写 ADR，保留原因而不仅是结果。
5. 效果图服从空间与施工逻辑，不以视觉表现替代可落地性。


## Project governance

本项目固定采用以下协作角色：

- **Homeowner / Product Owner**：最终生活方式、预算、设计与验收决策
- **ChatGPT**：Design Lead / PM / Reviewer
- **Codex**：Implementation Engineer，负责代码、数据、CAD 自动化和可复现输出
- **现场专业人员**：对实测尺寸、结构与施工可行性提供现实世界验证

详细规则：

- [Team & Governance](docs/TEAM_AND_GOVERNANCE.md)
- [Technical Stack](docs/TECH_STACK.md)
- [Development Workflow](docs/DEVELOPMENT_WORKFLOW.md)

从 B0 自动化工具链建立完成后，默认采用 **Issue → Codex implementation → ChatGPT review → Homeowner acceptance → merge** 的流程。
