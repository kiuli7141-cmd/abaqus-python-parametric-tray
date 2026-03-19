from abaqusConstants import *
import regionToolset
from src.core.naming import PART_PLATEN, INST_PLATEN, SURF_PLATEN, SET_RP_PLATEN, RB_PLATEN
from src.core.qa import assert_min, assert_between, log_count

def _safe_del(mapping, key):
    """删除字典中的key，避免异常"""
    try:
        if key in mapping:
            del mapping[key]
    except Exception:
        pass

def ensure_platen_part(model, Lp, Wp):
    """创建一个离散刚体面（矩形压头）"""
    if PART_PLATEN in model.parts:
        return model.parts[PART_PLATEN]

    sheet = max(Lp, Wp) * 2.0
    sk = model.ConstrainedSketch(name="__sk_platen__", sheetSize=sheet)
    sk.rectangle(point1=(-Lp/2.0, -Wp/2.0), point2=(Lp/2.0, Wp/2.0))

    p = model.Part(name=PART_PLATEN, dimensionality=THREE_D, type=DISCRETE_RIGID_SURFACE)
    p.BaseShell(sketch=sk)
    _safe_del(model.sketches, "__sk_platen__")

    # 接触面接口（后续可供接触定义）
    p.Surface(name=SURF_PLATEN, side1Faces=p.faces[:])

    return p

def ensure_platen_instance(model, a, p_platen, center_xyz):
    """创建压头的实例并定位"""
    _safe_del(a.instances, INST_PLATEN)
    inst = a.Instance(name=INST_PLATEN, part=p_platen, dependent=ON)
    a.translate(instanceList=(INST_PLATEN,), vector=center_xyz)
    return inst

def ensure_rp_and_rigidbody(model, a, platen_inst, rp_xyz):
    """创建参考点与刚体约束"""
    _safe_del(a.sets, SET_RP_PLATEN)
    _safe_del(model.constraints, RB_PLATEN)

    rp = a.ReferencePoint(point=rp_xyz)
    rp_obj = a.referencePoints[rp.id]
    a.Set(name=SET_RP_PLATEN, referencePoints=(rp_obj,))

    ref_region = regionToolset.Region(referencePoints=(rp_obj,))
    body_region = regionToolset.Region(faces=platen_inst.faces[:])

    model.RigidBody(name=RB_PLATEN, refPointRegion=ref_region, bodyRegion=body_region)

    return rp_obj

def build_platen_v0(model, a, cfg, tray_dims, z_top):
    """
    创建压头并定位，检查约束条件
    """
    Lp = float(cfg["platen"]["L"])
    Wp = float(cfg["platen"]["W"])
    gap = float(cfg["platen"]["gap"])

    # 检查 gap 合法性
    assert_between("platen.gap", gap, 0.0, 1.0e9, hint="gap<0 会初始穿透")

    # 检查压头是否能覆盖托盘
    L = float(tray_dims["L"]); W = float(tray_dims["W"])
    assert_min("platen.L_vs_tray.L", Lp, L, hint="压头比托盘小，接触时边缘滑出风险很高")
    assert_min("platen.W_vs_tray.W", Wp, W, hint="同上")

    p_platen = ensure_platen_part(model, Lp, Wp)

    # 定位：托盘的中心点
    cx, cy = L/2.0, W/2.0
    cz = float(z_top) + gap

    platen_inst = ensure_platen_instance(model, a, p_platen, center_xyz=(cx, cy, cz))
    rp_obj = ensure_rp_and_rigidbody(model, a, platen_inst, rp_xyz=(cx, cy, cz))

    # 确认压头创建成功
    n_faces = len(platen_inst.faces)
    log_count("platen_faces", platen_inst.faces)
    assert_min("platen_faces", n_faces, 1, hint="压头几何创建失败，面数为零")

    return dict(cx=cx, cy=cy, cz=cz, gap=gap)