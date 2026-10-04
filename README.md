# Lingnanxu 803 Renovation

广州岭南序 6 栋 803（约 118㎡）装修设计与落地管理项目。

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
