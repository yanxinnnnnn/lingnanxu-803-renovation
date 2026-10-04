# CAD

**B0 ESTIMATED PLAN — NOT FOR CONSTRUCTION。** B0 仅用于空间研究与方案讨论。
不得用于拆墙、砌墙定位、水电定位、门窗或柜体下单、施工放线。
现场实测或官方 verified dimensions 建立 B1 后，B1 将替代 B0 几何。

## Source of truth 与输出

- `data/b0_floorplan.yaml`：Issue #1 提供的 17 个房间、简化周界和 8 条玻璃线段。
- `cad/LN803_BASE_B0_v0.1_20261004.dxf`：由 YAML 生成并提交的 R2010 DXF。
- `artifacts/LN803_BASE_B0_v0.1_20261004_preview.png`：从该 DXF 渲染并提交的 review 预览。

生成的 DXF 不是手工维护的输入；更改必须从结构化数据开始并遵循 baseline review。
当前输入原样保留 trace 中的重叠、空隙及简化边界，不进行空间重设计。

## 生成与验证

从仓库根目录执行：

```bash
uv sync
uv run python scripts/validate_floorplan.py
uv run python scripts/generate_b0_dxf.py
uv run python scripts/render_preview.py
uv run pytest
uv run python scripts/validate_floorplan.py --dxf cad/LN803_BASE_B0_v0.1_20261004.dxf
git status --short
```

在干净 checkout 上重复这些命令不会修改已提交的 DXF 或 PNG，也不会留下测试文件。
`uv.lock` 锁定传递依赖；`.python-version` 与 `pyproject.toml` 限定 Python 3.12。
DXF 固定 ezdxf 的时间戳、GUID、writer metadata 和 class 顺序；输出使用 LF 行尾。
固定时间戳为序列化占位值，图纸版本日期以 YAML metadata 和可见注记为准。

自定义路径示例（目录按需自动创建）：

```bash
uv run python scripts/generate_b0_dxf.py --data data/b0_floorplan.yaml --output artifacts/review.dxf
uv run python scripts/validate_floorplan.py --data data/b0_floorplan.yaml --dxf artifacts/review.dxf
uv run python scripts/render_preview.py --data data/b0_floorplan.yaml --dxf artifacts/review.dxf --output artifacts/review.png
```

默认校验验证 YAML，以及内存生成 DXF 的图层、注记、provenance 和坐标。
`--dxf` 还检查落盘 DXF 的可读性、audit、闭合标记、中文房间名及源坐标一致性。
无效输入或 DXF 返回非零状态；预览也会先验证 DXF 与 YAML 一致。
检查数值是否有限、polygon 点数、segment 点数、唯一 IDs、source 引用及 provenance，
不设置任何暗示现场精度的误差容限。

## 数据约定

根节点包括 `metadata`、`sources`、`trace_coordinate_system`、`perimeter`、`rooms` 和 `glazing`。
每个几何记录有唯一 `id`、`source`、`provenance: estimated`，房间另有中文 `display_name`。
polygon 使用 `polygon_px`，玻璃线段使用恰好两个端点的 `segment_px`。
周界保留 Issue 的重复闭合端点；生成时由 DXF closed flag 闭合。

标定是 perspective-compensated visual trace，**不是 measured architectural scale**：

```text
origin_px = [150, 1400]
x_mm = (x_px - 150) * 15.5
y_mm = (1400 - y_px) * 12.5
```

DXF 存储单位是 mm，但这些值仅为估算的 millimetre-like CAD units。
所有 B0.1 metadata、source、标定与几何 provenance 必须为 `estimated`；本 B0.1 schema
不接受 `official` 或 `measured` source。未来经验证的资料需要单独扩展 schema/baseline。
营销资料/样板间视频的背景索引仍由 `references/source-manifest.yaml` 维护；
本次 geometry 的直接来源为 Issue #1 的 visual trace，没有从视频推导新尺寸。

## 图层与显示

| Layer | 内容 |
| --- | --- |
| A-WALL-EXT | 简化估算周界 |
| A-WALL-INT | 估算房间边界；不表达墙厚或结构属性 |
| A-GLAZ | 估算玻璃线段 |
| A-DOOR | 保留的语义图层，本阶段为空 |
| A-FURN | 保留的语义图层，本阶段为空 |
| A-ROOM | 中文房间名 |
| A-NOTE | baseline、版本、精度说明 |
| A-UNVERIFIED | 可见 B0 禁止施工警告 |

每个 modelspace entity 的 `LN803_B0` XDATA 存储 baseline、`estimated`、记录 ID 和 source ID。
预览使用 matplotlib Agg 后端，显示英文 room IDs，使用内置 DejaVu Sans 字体，
无需系统中文字体或 CAD GUI；中文名称保留在 YAML 和 DXF TEXT 中。

精度层级：B0 为视觉追踪/估算；B1 为官方图纸或现场量房验证；L1+ 基于 B1 设计。

## B0.2 独立参考 overlay

`LN803_REF_B0.2_provisional_20261004.dxf` 从 canonical B0.1 DXF 加入独立
`A-REF-PROVISIONAL` 紫色注记层；原有几何、中文标签与 B0 警告不改动。
第三方 `measurement-ref-001` 不属于 803，所有参考项均待现场验证，不能用于施工。
未决面积只显示在平面旁的 schedule，不映射到房间、不重新标定 B0。
参考注记使用独立 `LN803_REF_PROVISIONAL` XDATA，不会携带 B0 `estimated` entity 标签。

```bash
uv run python scripts/validate_provisional_measurements.py
uv run python scripts/generate_provisional_overlay.py
uv run python scripts/validate_provisional_measurements.py --dxf cad/LN803_REF_B0.2_provisional_20261004.dxf
```

预览为 `artifacts/LN803_REF_B0.2_provisional_20261004_preview.png`；
overlay / preview 均显示 `THIRD-PARTY PROVISIONAL REFERENCE - VERIFY ON SITE BEFORE B1`。
字段与 B1 交接步骤见 [Measurements](../measurements/README.md)。
