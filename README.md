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
