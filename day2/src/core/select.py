# -*- coding: utf-8 -*-

def _get_xyz_from_obj(obj):
    """
    [底层辅助] 获取对象的空间坐标。
    功能：兼容 Vertex（点）、Face（面）、Edge（边）。
    逻辑：优先尝试获取 pointOn 属性，如果失败（如某些面）则尝试计算质心 getCentroid。
    """
    try:
        p = obj.pointOn
        if p and len(p) > 0:
            return p[0]
    except Exception:
        pass
    # 兜底：有些 face 可能有 getCentroid()
    try:
        c = obj.getCentroid()
        return c
    except Exception:
        return None

def _dist2(a, b):
    """
    [底层辅助] 计算两点间欧几里得距离的平方。
    功能：用于快速比较距离远近（不开方以提升计算速度）。
    """
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return dx*dx + dy*dy + dz*dz

def verts_by_bbox(obj, bbox):
    """
    [选择器] 通过 Bounding Box 获取顶点。
    参数：obj (可以是 Part 或 Instance), bbox (包含 xMin/xMax 等的字典)
    返回：Abaqus VertexArray
    """
    return obj.vertices.getByBoundingBox(**bbox)

def faces_by_bbox(obj, bbox):
    """
    [选择器] 通过 Bounding Box 获取面。
    参数：obj (可以是 Part 或 Instance), bbox (字典)
    返回：Abaqus FaceArray
    """
    return obj.faces.getByBoundingBox(**bbox)

def edges_by_bbox(obj, bbox):
    """
    [选择器] 通过 Bounding Box 获取边。
    参数：obj (可以是 Part 或 Instance), bbox (字典)
    返回：Abaqus EdgeArray
    """
    return obj.edges.getByBoundingBox(**bbox)


def pick_closest(cands, target_xyz):
    """
    [计算器] 从候选集合中选出离目标点最近的一个对象。
    核心逻辑：
    1. 计算距离平方，越小越好。
    2. [确定性保障] Tie-break 机制：
       如果距离相同，优先比较 .index (几何索引)；
       如果没有 index，则比较 .label (网格编号)。
       这保证了在 Part(几何) 和 Mesh(网格) 模式下都能稳定运行。
    """
    best = None
    best_key = None
    
    for obj in cands:
        xyz = _get_xyz_from_obj(obj)
        if xyz is None:
            continue
            
        d2 = _dist2(xyz, target_xyz)
        
        # === 核心修改 ===
        # 几何对象用 .index，网格用 .label
        # 先试 index，没有再试 label，都没用就填 0
        idx = getattr(obj, "index", getattr(obj, "label", 0))
        
        # 排序键：(距离越小越好, 索引越小越好)
        key = (d2, idx)
        
        if (best_key is None) or (key < best_key):
            best_key = key
            best = obj
    return best

def pick_closest_vertex(cands, target_xyz):
    """
    [别名] pick_closest 的语义化别名，专门用于选点场景。
    """
    return pick_closest(cands, target_xyz)

def unique_by_label(objs):
    """
    [辅助] 简单的列表去重工具。
    依据：对象的 label 属性（主要用于网格节点/单元去重）。
    """
    seen = set()
    out = []
    for o in objs:
        lab = getattr(o, "label", None)
        if lab is None:
            out.append(o)
            continue
        if lab in seen:
            continue
        seen.add(lab)
        out.append(o)
    return out

def _dedup_keep_order(int_labels):
    """
    [底层辅助] 整数列表去重并保持原有顺序。
    作用：确保生成的序列顺序稳定，方便回归测试。
    """
    seen = set()
    out = []
    for x in int_labels:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out

# === 2. to_vertex_array (连续区间合并版) ===
def to_vertex_array(obj, verts):
    """
    [转换器] 高性能将列表转换为 Abaqus VertexArray。
    输入：obj (Part/Instance), verts (Vertex对象列表 或 索引列表)
    
    核心优化：
    Abaqus 的序列拼接 (seq1 + seq2) 非常耗时。
    此函数检测连续的索引（如 1,2,3,4），将其合并为一个切片操作 (seq[1:5])。
    极大减少了 '+' 运算的次数，显著提升大数量级下的运行速度。
    """
    if verts is None:
        return obj.vertices[0:0]
    if hasattr(verts, "getMask"):  # 如果已经是 VertexArray，直接返回
        return verts

    clean = [v for v in verts if v is not None]
    if not clean:
        return obj.vertices[0:0]

    # 提取索引：支持直接传 int 列表，也支持传 Vertex 对象列表
    if isinstance(clean[0], int):
        idxs = clean
    else:
        idxs = [v.index for v in clean]
    
    idxs = _dedup_keep_order(idxs) # 去重
    seq = obj.vertices
    out = seq[0:0] # 初始化空序列
    
    if not idxs:
        return out 
        
    # === 连续区间合并算法 ===
    s = p = idxs[0]
    for i in idxs[1:]:
        if i == p + 1: # 如果当前索引是前一个索引+1（连续）
            p = i      # 延伸当前区间
        else:
            # 不连续了，把之前攒的一段切片加进去
            out = out + seq[s:p+1]
            s = p = i  # 开启新区间
    # 把最后一段加进去
    out = out + seq[s:p+1]
    return out

# === 3. to_face_array (连续区间合并版) ===
def to_face_array(obj, faces):
    """
    [转换器] 高性能将列表转换为 Abaqus FaceArray。
    逻辑：同 to_vertex_array，只是操作对象变成了 obj.faces。
    """
    if faces is None:
        return obj.faces[0:0]
    if hasattr(faces, "getMask"):  # 已是 FaceArray
        return faces
    clean = [f for f in faces if f is not None]
    if not clean:
        return obj.faces[0:0]

    if isinstance(clean[0], int):
        idxs = clean
    else:
        idxs = [f.index for f in clean]
        
    idxs = _dedup_keep_order(idxs)
    seq = obj.faces
    out = seq[0:0]
    
    if not idxs:
        return out
        
    s = p = idxs[0]
    for i in idxs[1:]:
        if i == p + 1:
            p = i
        else:
            out = out + seq[s:p+1]
            s = p = i
    out = out + seq[s:p+1]
    return out