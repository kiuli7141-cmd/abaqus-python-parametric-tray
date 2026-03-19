# Interface Specification

## 1. 命名常量（唯一真源）

- `SURF_TOP`
- `SURF_RIB_BOTTOM`
- `SURF_FIX_PADS`
- `SET_FIX_PADS`

> 常量定义见 `src/core/naming.py`

---

## 2. 接口总表（契约）

| Name               | Type     | Scope       | Physical meaning        | Producer                      | Selection rule                       | Consumer               | QA gate (fail fast)       |
|--------------------|----------|-------------|-------------------------|------------------------------|--------------------------------------|------------------------|---------------------------|
| `SURF_TOP`         | Surface  | Part("Tray")| 托盘顶面 (z=t)           | `tray_v1.build_and_tag_tray_v1`| faces.getByBoundingBox(zMin=t-eps, zMax=t+eps) | day5_static: RP coupling | n_top>=1，否则直接报错   |
| `SURF_RIB_BOTTOM`  | Surface  | Part("Tray")| 两条筋底面 (y带状 + z=-rib_h) | `tray_v1.build_and_tag_tray_v1`| bbox: y≈±rib_off, z≈-rib_h | (后续接触/约束预留)  | n_rib>=2                   |
| `SURF_FIX_PADS`    | Surface  | Part("Tray")| 顶面四角 pad×pad 小面（依赖 partition） | `tray_v1.partition_top_for_fix_pads + build_and_tag_tray_v1` | 每角 bbox 贴边窗口 + z≈t | (后续接触/加载预留)   | n_fix_faces>=4           |
| `SET_FIX_PADS`     | Set(vertices) | Part("Tray") | 顶面四角“定位点”集合 | `tray_v1.build_and_tag_tray_v1` | 每角 bbox 候选点 -> pick_closest_vertex(目标点) -> 按 index 去重 | day5_static: 固定 BC | n_fix_verts>=4            |

---

## 3. 关键约束（必须遵守）

1. 接口必须落在 Part 上（不是 instance），否则 dependent=ON 的实例无法稳定继承。
2. `SURF_FIX_PADS` 必须在 partition 后才能抓到。
3. 选点必须是“确定性”：bbox 候选 + 最近点 + tie-break。

---

## 4. 失败排查优先级

- `missing key / n=0`：查 `eps/pad/search_box/search_eps`
- `partition 后 n_fix_faces 仍不足`：查 `pad 是否过大、cut 平面是否越界`
- `instance 上缺 SURF_TOP/SET_FIX_PADS`：确认实例是 `dependent=ON` 