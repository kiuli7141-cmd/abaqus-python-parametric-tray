# -*- coding: utf-8 -*-
from part import *
from assembly import *
from abaqusConstants import *
# tray_v1.py
from abaqus import mdb, session
from abaqusConstants import *
from src.core.qa import log_count, assert_min, assert_between, assert_key_exists
from src.core.naming import SURF_TOP, SURF_RIB_BOTTOM, SURF_FIX_PADS, SET_FIX_PADS
from src.core.select import faces_by_bbox, verts_by_bbox, pick_closest_vertex, unique_by_label, to_face_array, to_vertex_array

def partition_top_for_fix_pads(p_tray, pad, z_top, eps=1.0):
    """
    在 Part 上做顶面 3×3 分块所需的 partition：
    - 用 x = xlo+pad, xhi-pad 两个平面
    - 用 y = ylo+pad, yhi-pad 两个平面
    注意：必须在任何 getByBoundingBox 选面/建 Surface 之前调用。
    """
    bb =  p_tray.vertices.getBoundingBox()
    xlo, ylo, _ = bb["low"]
    xhi, yhi, _ = bb["high"]

    x_cut_lo = xlo + pad
    x_cut_hi = xhi - pad
    y_cut_lo = ylo + pad
    y_cut_hi = yhi - pad

    if (x_cut_lo >= x_cut_hi) or (y_cut_lo >= y_cut_hi):
        raise RuntimeError(
            "pad too large: xlo+pad >= xhi-pad or ylo+pad >= yhi-pad. "
            "Decrease pad."
        )
#架刀具（创建基准面 Datum Plane）
    dp1 = p_tray.DatumPlaneByPrincipalPlane(principalPlane=YZPLANE, offset=x_cut_lo)
    dp2 = p_tray.DatumPlaneByPrincipalPlane(principalPlane=YZPLANE, offset=x_cut_hi)
    dp3 = p_tray.DatumPlaneByPrincipalPlane(principalPlane=XZPLANE, offset=y_cut_lo)
    dp4 = p_tray.DatumPlaneByPrincipalPlane(principalPlane=XZPLANE, offset=y_cut_hi)

    # Solid: PartitionCellByDatumPlane；Shell: PartitionFaceByDatumPlane  实体：按基准面分割单元格；壳体：按基准面分割面
    if len(p_tray.cells) > 0:
        cells = p_tray.cells
        p_tray.PartitionCellByDatumPlane(cells=cells, datumPlane=p_tray.datums[dp1.id])
        p_tray.PartitionCellByDatumPlane(cells=cells, datumPlane=p_tray.datums[dp2.id])
        p_tray.PartitionCellByDatumPlane(cells=cells, datumPlane=p_tray.datums[dp3.id])
        p_tray.PartitionCellByDatumPlane(cells=cells, datumPlane=p_tray.datums[dp4.id])
    else:
        faces_all = p_tray.faces
        p_tray.PartitionFaceByDatumPlane(faces=faces_all, datumPlane=p_tray.datums[dp1.id])
        p_tray.PartitionFaceByDatumPlane(faces=faces_all, datumPlane=p_tray.datums[dp2.id])
        p_tray.PartitionFaceByDatumPlane(faces=faces_all, datumPlane=p_tray.datums[dp3.id])
        p_tray.PartitionFaceByDatumPlane(faces=faces_all, datumPlane=p_tray.datums[dp4.id])
#你可能会问：“为什么不直接写 datumPlane=dp1？”
#原理： dp1 只是你刚才创建时的一个临时回执单。而在 Abaqus 的仓库里，所有的基准面都按照 ID 号 锁在 datums 这个大柜子里。

    # 验收打印：顶面分块后 face 数应 > 1（通常为 9 或更多）
    faces_top_after = p_tray.faces.getByBoundingBox(zMin=z_top - eps, zMax=z_top + eps)
    print("[PARTITION] top faces after partition =", len(faces_top_after))

def build_and_tag_tray_v1(p=None):
    # ====== 把你 Day1 代码从 “参数控制台” 开始到最后粘贴到这里 ======
# === 参数控制台 ===
    p = p or {}  # 兜底机制：如果 p 是 None，就变成空字典 {}，防止报错
    L = p.get("L", 800.0)           # 长
    W = p.get("W", 500.0)           # 宽
    t = p.get("t", 2.0)             # 板厚
    rib_w = p.get("rib_w", 40.0)    # 筋宽
    rib_h = p.get("rib_h", 30.0)    # 筋高
    rib_off = p.get("rib_off", 120.0) # 筋偏移量
    eps = p.get("eps", 1.0)         # 容差窗口
    corner_box = p.get("corner_box", 2.0)  # 角点选取盒半宽
    pad = p.get("pad", 60.0)        # 角区小面尺寸（40~60都行）；用于 SURF_FIX_PADS
    search_box = p.get("search_box", 5.0)
    search_eps = p.get("search_eps", 1.0)
    # 额外增加一个 ID 字段，方便后续 Block 5 打印日志
    case_id = p.get("case_id", "NA")
    corners = [(L/2, W/2), (L/2, -W/2), (-L/2, W/2), (-L/2, -W/2)]
    m=mdb.models['Model-1']
    a=m.rootAssembly

    # 1) 清理旧实例（如果存在）
    for iname in list(a.instances.keys()):
        if iname in ('Part-Plate-1', 'Rib-1', 'Rib-2', 'Tray-1'):
            del a.instances[iname]

    # 2) 清理旧 Part（关键：否则 m.Part(name='Part-Plate') 会直接报已存在）
    for pname in ('Part-Plate', 'Part-Rib', 'Tray'):
        if pname in m.parts.keys():
            del m.parts[pname]

    m.ConstrainedSketch(name='__profile__', sheetSize=1000.0)
    m.sketches['__profile__'].rectangle(point1=(-L/2, -W/2)
        , point2=(L/2.0, W/2))
    m.Part(dimensionality=THREE_D, name='Part-Plate', type=
        DEFORMABLE_BODY)
    m.parts['Part-Plate'].BaseSolidExtrude(depth=t, sketch=
        m.sketches['__profile__'])
    del m.sketches['__profile__']
    m.ConstrainedSketch(name='__profile__', sheetSize=1000.0)
    m.sketches['__profile__'].rectangle(point1=(-L/2, -rib_w/2), 
        point2=(L/2.0, rib_w/2))
    m.Part(dimensionality=THREE_D, name='Part-Rib', type=
        DEFORMABLE_BODY)
    m.parts['Part-Rib'].BaseSolidExtrude(depth=rib_h, sketch=
        m.sketches['__profile__'])
    del m.sketches['__profile__']
    a.DatumCsysByDefault(CARTESIAN)
    a.Instance(dependent=OFF, name='Part-Plate-1', 
        part=m.parts['Part-Plate'])
    a.Instance(dependent=OFF, name='Rib-1', part=
        m.parts['Part-Rib'])
    a.Instance(dependent=OFF, name='Rib-2', part=
        m.parts['Part-Rib'])
    a.translate(instanceList=('Rib-2', ), vector=(
        0.0, 0.0, -rib_h))
    a.translate(instanceList=('Rib-2', ), vector=(
        0.0, rib_off, 0.0))
    a.translate(instanceList=('Rib-1', ), vector=(
        0.0, 0.0, -rib_h))
    a.translate(instanceList=('Rib-1', ), vector=(
        0.0, -rib_off, 0.0))
    a.InstanceFromBooleanMerge(domain=GEOMETRY,  #布尔运算生成新零件
        instances=(a.instances['Part-Plate-1'], 
        a.instances['Rib-1'], 
        a.instances['Rib-2']), name='Tray', 
        originalInstances=DELETE)
# === 2. [Day 3 核心] 拿到 Part 对象 ===
# 以前我们是找 a.instances['Tray-1'] (找复印件)     inst = a.instances['Tray-1']
# 现在我们要找 m.parts['Tray'] (找原稿图纸)
    p_tray = m.parts['Tray']

    z_top = t  # 你建模坐标系下，板顶面在 z=t（防止底面加高导致高度变化，而t一直不变）
    partition_top_for_fix_pads(p_tray, pad=pad, z_top=z_top, eps=eps)       #本文第一个def函数，创建partion必须在抓面bbox之前
 
    # === 可选但强烈建议：创建 Tray-1 实例方便你在 CAE 里看到 ===
    if 'Tray-1' in a.instances.keys():
        del a.instances['Tray-1']
    a.Instance(dependent=OFF, name='Tray-1', part=p_tray)
    # === 同名清理：重复运行不崩 ===
    for sname in (SURF_TOP, SURF_RIB_BOTTOM, SURF_FIX_PADS):
        if sname in p_tray.surfaces.keys():
            del p_tray.surfaces[sname]
    if SET_FIX_PADS in p_tray.sets.keys():
        del p_tray.sets[SET_FIX_PADS]

    faces_top = p_tray.faces.getByBoundingBox(zMin=z_top - eps, zMax=z_top + eps)
    n_top = log_count(SURF_TOP, faces_top)
    assert_min(SURF_TOP, n_top, 1, hint="top face not found: check z_top/eps or partition")
    faces_top = to_face_array(p_tray, faces_top)
    if SURF_TOP in p_tray.surfaces:
        del p_tray.surfaces[SURF_TOP]
    p_tray.Surface(name=SURF_TOP, side1Faces=faces_top)
     # === SURF_RIB_BOTTOM：两条筋底面（y 带状 + z=-rib_h）===
    y_half = rib_w/2.0
    faces_rib1 = p_tray.faces.getByBoundingBox(
        yMin=(-rib_off - y_half - eps), yMax=(-rib_off + y_half + eps),
        zMin=(-rib_h - eps),zMax=(-rib_h + eps))
    faces_rib2 = p_tray.faces.getByBoundingBox(
        yMin=( rib_off - y_half - eps), yMax=( rib_off + y_half + eps),
        zMin=(-rib_h - eps),zMax=(-rib_h + eps))
    faces_rib_bottom = faces_rib1 + faces_rib2
    n_rib = log_count(SURF_RIB_BOTTOM, faces_rib_bottom)
    assert_min(SURF_RIB_BOTTOM, n_rib, 2, hint="check rib_off/rib_w/y band or z=-rib_h band")
    faces_rib_bottom = to_face_array(p_tray, faces_rib_bottom)
    p_tray.Surface(name=SURF_RIB_BOTTOM, side1Faces=faces_rib_bottom)
     # ==============================================================================
     # ==============================================================================
    # [已修改] SURF_FIX_PADS：四角角区小面（面集合）
    # ==============================================================================
    # 原因：当前几何体未切分（Partition），顶面是一个 800x500 的整体。
    #       角区的小 bounding box 无法包住整个大面，导致抓取数量为 0，触发 QA 报错。
    # 措施：在 Day 2 阶段跳过此步骤，仅保留点集合（SET）。
    # ==============================================================================
    # faces_fix = None
    # for (cx, cy) in corners:
    #     ...
    # a.Surface(name=SURF# === SURF_FIX_PADS：四角角区小面（依赖 Day4 partition）===
    bb =  p_tray.vertices.getBoundingBox()
    xlo, ylo, _ = bb["low"]
    xhi, yhi, _ = bb["high"]

    corners_xy = [(xhi, yhi), (xhi, ylo), (xlo, yhi), (xlo, ylo)]
    faces_fix = None

    for i, (cx, cy) in enumerate(corners_xy):
        # 每个角：取一个 pad×pad 的角区窗口（贴边留 eps）
        if cx == xhi:
            xMin, xMax = xhi - pad - eps, xhi + eps
        else:
            xMin, xMax = xlo - eps, xlo + pad + eps

        if cy == yhi:
            yMin, yMax = yhi - pad - eps, yhi + eps
        else:
            yMin, yMax = ylo - eps, ylo + pad + eps

        faces_corner = p_tray.faces.getByBoundingBox(
            xMin=xMin, xMax=xMax,
            yMin=yMin, yMax=yMax,
            zMin=z_top - eps, zMax=z_top + eps
        )

        tag = "%s_corner_%d" % (SURF_FIX_PADS, i)
        n_c = log_count(tag, faces_corner)
        assert_min(tag, n_c, 1, hint="corner face not found: check partition/pad/eps/z_top")

        faces_fix = faces_corner if faces_fix is None else (faces_fix + faces_corner)

    n_fix_faces = log_count(SURF_FIX_PADS, faces_fix)
    assert_min(SURF_FIX_PADS, n_fix_faces, 4, hint="expect >=4 corner faces after partition")

    faces_fix = to_face_array(p_tray, faces_fix)

    if SURF_FIX_PADS in p_tray.surfaces:
        del p_tray.surfaces[SURF_FIX_PADS]
    p_tray.Surface(name=SURF_FIX_PADS, side1Faces=faces_fix)

    # ==============================================================================
    # === 修正版抓点逻辑 ===
    # 1. 确保变量指向正确
    # === SET_FIX_PADS：四角顶面角点 ===
    # === 苦力版：一个点一个点地抓 ===
    # 1. 准备工作
    v = p_tray.vertices
    if 'SET_FIX_PADS' in p_tray.sets:
        del p_tray.sets['SET_FIX_PADS']

    # verts_seq = None  # 关键：用 VertexArray 累加，不用 Python list

    # for (cx, cy) in corners:
    #     vs = v.getByBoundingBox(
    #         xMin=cx-search_box, xMax=cx+search_box,
    #         yMin=cy-search_box, yMax=cy+search_box,
    #         zMin=t-search_eps,  zMax=t+search_eps
    #     )
    #     if len(vs) < 1:
    #         raise ValueError('Corner vertex not found at (%.1f, %.1f)' % (cx, cy))

    #     # 只取一个（保持 4 个点），并保证仍是 VertexArray（切片返回 VertexArray）
    #     vs1 = vs[0:1]
    #     n_vs = log_count(SET_FIX_PADS + "_corner", vs) # 或者用更具体的 tag
    #     assert_min(SET_FIX_PADS + "_corner", n_vs, 1,
    #                         hint="check corner bbox/search_box/search_eps")
    #     if verts_seq is None:
    #         verts_seq = vs1
    #     else:
    #         verts_seq = verts_seq + vs1

    # print('SET_FIX_PADS vertices =', len(verts_seq), [vv.index for vv in verts_seq])
    # n_fix = log_count(SET_FIX_PADS, verts_seq)
    # assert_min(SET_FIX_PADS, n_fix, 4, hint="expected 4 corners; check corner bbox or z band")

    # a.Set(name=SET_FIX_PADS, vertices=verts_seq)
    '''上述为抓取第一个点的写法，准确度低。如果实例发生破坏（拓扑扰动），点容易变化变的不准确，以下抓取方式为精确抓取'''
    # === [变化点]：改用 Python 列表装点，不再用 verts_seq 累加。
   # === SET_FIX_PADS (deterministic) ===
    # === SET_FIX_PADS (deterministic + label -> VertexArray) ===
    picked_list = []

    for (cx, cy) in corners:
        bbox = dict(
            xMin=cx-search_box, xMax=cx+search_box,
            yMin=cy-search_box, yMax=cy+search_box,
            zMin=t-search_eps,  zMax=t+search_eps
        )

        # 候选点（Part/Instance 通用）
        cands = verts_by_bbox(p_tray, bbox)

        # 目标点：四角顶面 (cx, cy, t)
        target_pt = (cx, cy, t)
        best_v = pick_closest_vertex(cands, target_pt)

        # 每个角至少抓到 1 个点，否则直接门禁失败
        assert_min(SET_FIX_PADS + "_corner", 0 if best_v is None else 1, 1,
                hint="increase search_box/search_eps or check z band")

        picked_list.append(best_v)

    # === 去重（按 index，不要 label）===
    picked_idxs = []
    seen = set()
    for v in picked_list:
        if v is None:
            continue
        i = v.index
        if i in seen:
            continue
        seen.add(i)
        picked_idxs.append(i)

    # 统一转 VertexArray（to_vertex_array 支持 list[int(index)]）
    picked_verts = to_vertex_array(p_tray, picked_idxs)

    print("SET_FIX_PADS vertex indices =", [v.index for v in picked_verts])
    n_fix = log_count(SET_FIX_PADS, picked_verts)
    assert_min(SET_FIX_PADS, n_fix, 4, hint="Expected 4 corners. Check search_box/search_eps")


    # 同名清理（重复运行不崩）
    if SET_FIX_PADS in p_tray.sets.keys():
        del p_tray.sets[SET_FIX_PADS]
    p_tray.Set(name=SET_FIX_PADS, vertices=picked_verts)
    # === Day3 门禁：确认接口落在 Part 上 ===
    assert_key_exists(p_tray.surfaces, SURF_TOP, hint="SURF_TOP not on Part")
    assert_key_exists(p_tray.surfaces, SURF_RIB_BOTTOM, hint="SURF_RIB_BOTTOM not on Part")
    assert_key_exists(p_tray.sets, SET_FIX_PADS, hint="SET_FIX_PADS not on Part")


    return {
        "case_id": case_id,
        "t": t,
        "rib_off": rib_off,
        "rib_w": rib_w,
        "n_top": n_top,
        "n_rib_bottom": n_rib,
        "n_fix_verts": n_fix,
        "n_fix_faces": n_fix_faces,
        "skip_fix_pads": 0
    }
#返回输入参数方便参考
