# LOADCASE_AND_CRITERIA (Static v1)

## 1) 工况定义（Day5 Static Smoke Test）
- Model: Model-1
- Step: Static (nlgeom=OFF)
- Boundary:
  - BC_FIX: SET_FIX_PADS, u1=u2=u3=0 (Initial)
  - BC_RP: RP, u3 = rp_disp_u3 (Static), 其余 DOF=0
- Coupling:
  - COUP_TOP: RP ↔ SURF_TOP, KINEMATIC, WHOLE_SURFACE

## 2) 必采输出（最小闭环证据）
- ODB 必须存在
- History: U3@RP, RF3@RP
- 导出曲线: rf_u.csv（U3, RF3）

## 3) 派生指标（KPI）
- u3_end：末步 U3
- rf3_end：末步 RF3
- peak_rf_abs：|RF3| 峰值
- k_rf_over_u：rf3_end / |u3_end|（等效刚度口径）

## 4) PASS/FAIL 判据（v1）
PASS=1 需要同时满足：
- n_top >= 1
- n_fix_faces >= 4
- n_fix_verts >= 4
- elem_count > 0
- |u3_end| > 1e-12 且 |rf3_end| > 1e-12

否则 PASS=0，并写 fail_stage / fail_reason

## 5) 失败分层（runner 口径）# Loadcase and Criteria

## 1. Loadcase Definition

### 1.1 Loadcase name

`Day5 Static Smoke Test`

### 1.2 Purpose

验证最小静力闭环：

- 几何构建
- Part-level 接口创建
- 网格生成
- BC 和载荷定义
- Job 提交
- ODB 存在
- History 可抽取

### 1.3 Step Definition

- `StaticStep(nlgeom=OFF)`

---

## 2. Output Requests

- `U3` 和 `RF3` 为主要历史输出。
- ODB 后处理从 history region 中提取 `U3` 和 `RF3`。

---

## 3. Criteria

### 3.1 Build-time Gates

- `Tray` Part 存在。
- `SURF_TOP` 和 `SET_FIX_PADS` 存在于 Part。

### 3.2 Interface Gates

- `n_top >= 1`
- `n_fix_faces >= 4`
- `n_fix_verts >= 4`

### 3.3 Solve Gates

- Job 完成并生成 ODB。
- `U3` 和 `RF3` 存在于 history region 中。

### 3.4 PASS Criteria

PASS 的含义仅为：

- 完成最小静力闭环。
- 结果可用于回归比较。
- cfg_validate：配置缺 key / 数值非法（如 nu 不在 (0,0.5)）
- variant_run：建模/网格/提交/后处理阶段异常（stage 会被抬到异常消息里）