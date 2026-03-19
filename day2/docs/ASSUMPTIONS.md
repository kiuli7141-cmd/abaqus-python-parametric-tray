# Assumptions

## 1. Geometry Assumptions

- 目前仅支持 solid geometry。
- `SURF_FIX_PADS` 依赖顶面 partition，partition 后才能稳定生成。

## 2. Material Assumptions

- 只支持线弹性材料（`E` 和 `nu`）。
- 当前统一使用 `HomogeneousSolidSection`。

## 3. Mesh Assumptions

- 网格使用最小可跑策略：`seedPart(size=mesh_size)`，单元类型 `C3D8R`，使用 `SWEEP` 和 `MEDIAL_AXIS`。

## 4. Boundary Condition Assumptions

- 固定边界作用在 `SET_FIX_PADS` 上，所有自由度都设为零。
- 载荷通过 RP 引入，RP 位移控制。

## 5. Step Assumptions

- 当前静力步使用 `StaticStep(nlgeom=OFF)`，不考虑几何非线性。
- 目标是构建最小静力闭环，而非最终工程结论。

## 6. Output Assumptions

- 输出包括 `u3_end`, `rf3_end`, `peak_rf_abs`, `k_rf_over_u` 等用于验证闭环的关键指标。
