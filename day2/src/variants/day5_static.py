# -*- coding: utf-8 -*-
import os
import csv
from abaqus import mdb, session
from abaqusConstants import *
import regionToolset
import interaction
import step
import mesh
from odbAccess import openOdb
from src.core.naming import SURF_TOP, SET_FIX_PADS
from src.core.qa import log_count, assert_min, assert_key_exists

# 复用你 Day4 已经闭合的几何+接口
from src.variants.tray_v1 import build_and_tag_tray_v1


def _write_rf_u_csv(path, u_list, rf_list):    #记录u_list 位移，rf_list 反力  装车（存储）
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["U3", "RF3"])
        for u, rf in zip(u_list, rf_list):
            w.writerow([u, rf])

                                               #中间还缺了一段清洗abqus数据的代码应该在后文中，不在则报错
def _find_history_region_with_u3_rf3(step):    #寻找位移控制模式下的加载点     寻找（查询）
    """
    不查找硬编码 historyRegions 的 key（不同版本/命名会变）
    直接遍历找同时包含 U3 / RF3 的 region。
    """
    for _, hr in step.historyRegions.items():
        keys = hr.historyOutputs.keys()
        if ("U3" in keys) and ("RF3" in keys):
            return hr
    return None


def run_day5_static(cfg):
    """
    Day5: mesh + Static smoke test (STANDARD)
    输入: cfg(dict) 你的 caseA.json 等
    输出: metrics(dict)
    依赖: tray_v1.build_and_tag_tray_v1(cfg) 必须在 Part 上创建 SURF_TOP / SET_FIX_PADS
    """

    # ----------------------------
    # 0) 读取配置
    # ----------------------------
    cfg = cfg or {}
    case_id = str(cfg.get("case_id", "CASE"))      #get字典里的查找方式，可设定返回值：dict.get（key，reture）
    job_name = "J_%s_static" % case_id
    step_name = "Static"
    stage = "init"
    mesh_size = float(cfg.get("mesh_size", 20.0))
    E = float(cfg.get("E", 70000.0))
    nu = float(cfg.get("nu", 0.33))
    rp_disp_u3 = float(cfg.get("rp_disp_u3", -1.0))

    # tray 几何参数（只用于少数地方的默认值/输出；几何本体由 tray_v1 负责）
    t = float(cfg.get("t", 2.0))
    try:
        # ----------------------------
        # 1) 保证使用 Model-1（与你 tray_v1 写死 mdb.models['Model-1'] 对齐）
        # ----------------------------
    # --- Model-1: robust init (never KeyError) ---
        try:
            del mdb.models["Model-1"]    # 有就删，没有就跳过，用if容易报错
        except KeyError:
            pass

        if "Model-1" not in mdb.models:  # 确保存在
            mdb.Model(name="Model-1")    #这个是实例对象构造方法的使用

        m = mdb.models["Model-1"]      #缩减代码，刷新对象引用一模一样但作用效果不同

        # 清理同名 job
        if job_name in mdb.jobs:
            del mdb.jobs[job_name]
        # ----------------------------
        # 2) 调用 Day4：建几何 + Partition + 创建 Part-level 接口（SURF_TOP / SET_FIX_PADS 等）
        # ----------------------------
        stage = "build_geom"
        metrics_geom = build_and_tag_tray_v1(cfg)

        # tray_v1 会创建 Part: "Tray"
        if "Tray" not in m.parts:
            raise RuntimeError("Part 'Tray' not found. Check tray_v1 build_and_tag_tray_v1.")
        p_tray = m.parts["Tray"] #栈区，刷新对象引用

        # 接口门禁（必须在 Part 上）
        assert_key_exists(p_tray.surfaces, SURF_TOP, hint="SURF_TOP missing on Part")
        assert_key_exists(p_tray.sets, SET_FIX_PADS, hint="SET_FIX_PADS missing on Part")

        # ----------------------------
        # 3) 材料/截面/赋予（几何是 solid 就走 solid；如果你以后做 shell，这里再扩展）
        # ----------------------------
        mat_name = "MAT"
        sec_name = "SEC"

        mat = m.Material(name=mat_name)
        mat.Elastic(table=((E, nu),))

        # 你的 tray_v1 目前是 BaseSolidExtrude + BooleanMerge -> solid
        if len(p_tray.cells) <= 0:   #p_tray.cells零件所有的实体体积
            # 先给明确错误：避免你以为跑的是 solid 但其实是 shell 面体
            raise RuntimeError("Tray has no cells (not a solid). Current Day5_static expects solid geometry.")

        m.HomogeneousSolidSection(name=sec_name, material=mat_name)
        region_solid = regionToolset.Region(cells=p_tray.cells)
        p_tray.SectionAssignment(region=region_solid, sectionName=sec_name)
    # ... (接 Step 2 之后)
        if "Tray" not in m.parts:
            raise RuntimeError("Part 'Tray' not found...")
        p_tray = m.parts["Tray"]

        # ================== 【新增修复代码开始】 ==================
        # 紧急修复：Day4 的函数可能创建了一个 Independent Instance。
        # 它会锁死 Part 的网格功能。必须在画网格前把它删掉！
        a = m.rootAssembly
        # 暴力清理：把 Assembly 里所有现存的 Instance 全删了
        # (反正我们在 Step 5 会重新建一个 dependent=ON 的)
        if len(a.instances) > 0:
            a.deleteFeatures(a.instances.keys())
        # ================== 【新增修复代码结束】 ==================

        # 接口门禁（必须在 Part 上）
    # ----------------------------
        # 4) 网格（改用 SWEEP 扫掠）
        # ----------------------------
        stage = "mesh"
        p_tray.seedPart(size=mesh_size, deviationFactor=0.1, minSizeFactor=0.1)
        
        # 【修改点 1】改用 SWEEP (扫掠)，它能处理带筋的拉伸体
        # algorithm=MEDIAL_AXIS 通常能生成更好的扫掠网格
        p_tray.setMeshControls(regions=p_tray.cells, technique=SWEEP, algorithm=MEDIAL_AXIS)

        # 【修改点 2】显式指定用 Hex (六面体) 单元
        et = mesh.ElemType(elemCode=C3D8R, elemLibrary=STANDARD) #构造函数
        p_tray.setElementType(regions=(p_tray.cells,), elemTypes=(et,))

        p_tray.generateMesh()
        elem_count = len(p_tray.elements)
        node_count = len(p_tray.nodes)
        assert_min("elem_count", elem_count, 1, hint="No elements generated. Check mesh_size/geometry.")

        # ----------------------------
        # 5) 装配：重新创建一个 dependent=ON 的 Tray-1
        #    目的：确保 instance 继承 Part-level sets/surfaces（避免 tray_v1 里 dependent=OFF 的隐患）
        # ----------------------------
        stage = "bc_load"
        a = m.rootAssembly
        a.DatumCsysByDefault(CARTESIAN)

        inst_name = "Tray-1"
        if inst_name in a.instances:
            del a.instances[inst_name]
        inst = a.Instance(name=inst_name, part=p_tray, dependent=ON)

        # ----------------------------
        # 6) Step：最小静力
        # ----------------------------
        m.StaticStep(name=step_name, previous="Initial", nlgeom=OFF)

    # ----------------------------
    # ----------------------------
        # 7) RP：放在顶面上方
        # ----------------------------
        # 1. 获取几何包围盒 (用 p_tray.cells 因为是实体)
        bb = p_tray.cells.getBoundingBox()
        
        # 2. 解包坐标范围
        xlo, ylo, zlo = bb["low"]
        xhi, yhi, zhi = bb["high"]
        
        # 3. 【补回丢失的计算代码】计算中心点
        xmid = (xlo + xhi) / 2.0
        ymid = (ylo + yhi) / 2.0
        
        # 4. 创建 RP
        rp_obj = a.ReferencePoint(point=(xmid, ymid, zhi + 10.0))#创建 RP 特征
        rp = a.referencePoints[rp_obj.id]#特征转几何
        rp_region = regionToolset.Region(referencePoints=(rp,))#把这个 RP 点打包成一个标准的 Region 对象
        #p_tray.cells 那里一样：把这个 RP 点打包成一个标准的 Region 对象。
        # ----------------------------
        # 8) Coupling：RP ↔ SURF_TOP（instance surface）
        # ----------------------------
        if SURF_TOP not in inst.surfaces:
            raise RuntimeError("inst.surfaces missing '%s'. Check SURF_TOP created on Part and instance is dependent=ON." % SURF_TOP)
        top_surf = inst.surfaces[SURF_TOP]

        coupling_api = getattr(m, "Coupling", None)
        if coupling_api is None and hasattr(m, "engineeringFeatures"):
            coupling_api = getattr(m.engineeringFeatures, "Coupling", None)
        if coupling_api is None:
            raise RuntimeError("Coupling API not found on Model or engineeringFeatures.")

        coupling_api(
            name="COUP_TOP",
            controlPoint=rp_region,
            surface=top_surf,
            influenceRadius=WHOLE_SURFACE,
            couplingType=KINEMATIC,
            localCsys=None,
            u1=ON, u2=ON, u3=ON,
            ur1=ON, ur2=ON, ur3=ON
        )

    # ----------------------------
        # 9) 固定：SET_FIX_PADS（instance set）
        # ----------------------------
        if SET_FIX_PADS not in inst.sets:
            raise RuntimeError("inst.sets missing '%s'. Check SET_FIX_PADS created on Part and instance is dependent=ON." % SET_FIX_PADS)
        fix_set = inst.sets[SET_FIX_PADS]

        m.DisplacementBC(
            name="BC_FIX",
            createStepName="Initial",
            region=fix_set,
            u1=0.0, u2=0.0, u3=0.0
        )

        # ----------------------------
        # 10) 加载：RP 位移控制（锁住其余 DOF 防止漂移）
        # ----------------------------
        m.DisplacementBC(
            name="BC_RP",
            createStepName=step_name,
            region=rp_region,
            u1=0.0, u2=0.0, u3=rp_disp_u3,
            ur1=0.0, ur2=0.0, ur3=0.0
        )

        # ----------------------------
        # 11) History：请求 RP 的 U3/RF3
        # ----------------------------
        m.HistoryOutputRequest(
            name="H_RP",
            createStepName=step_name,
            variables=("U3", "RF3"),
            region=rp_region,
            frequency=1
        )

    # ----------------------------
        # 12) Job：提交并等待完成
        # ----------------------------
        job = mdb.Job(
            name=job_name,
            model="Model-1",
            type=ANALYSIS,
            description="Day5 static smoke test",
            numCpus=4,        # 你的 CPU 核数
            numDomains=4      # 【新增】必须等于 numCpus (或者它的倍数)
        )
        # ... (Step 12 Job 部分)
        stage = "job_submit"
        job.submit()
        job.waitForCompletion()

        # ================== 【补回缺失的代码】 ==================
        # 必须先定义 odb_path，下面 Step 13 才能用
        odb_path = os.path.abspath(job_name + ".odb")
        
        # 建议加上这个文件检查，如果 Job 失败没生成 ODB，直接报错提示
        if not os.path.isfile(odb_path):
            raise RuntimeError("ODB file not found: %s. Job may have failed." % odb_path)
        # ======================================================

        # ----------------------------
        # 13) ODB 后处理：抽 RF–U
        # ----------------------------
        stage = "odb_post"
        odb = openOdb(path=odb_path)  # 现在这里就不会报错了
        if step_name not in odb.steps:
            odb.close()
            raise RuntimeError("Step '%s' not found in ODB. Check job run." % step_name)

        step = odb.steps[step_name]
        hr = _find_history_region_with_u3_rf3(step)
        if hr is None:
            odb.close()
            raise RuntimeError("Cannot find history region with U3/RF3. Check HistoryOutputRequest & RP region.")

        u_hist = hr.historyOutputs["U3"].data
        rf_hist = hr.historyOutputs["RF3"].data

        u_list = [v for (_, v) in u_hist]
        rf_list = [v for (_, v) in rf_hist]

        odb.close()

        assert_min("hist_len", len(u_list), 1, hint="No history data in ODB.")

        u_end = u_list[-1]
        rf_end = rf_list[-1]
        if abs(u_end) < 1e-12 or abs(rf_end) < 1e-12:
            raise RuntimeError("U3/RF3 end is ~0. Check coupling/BC/output request.")

        peak_rf_abs = max(abs(x) for x in rf_list) if rf_list else 0.0
        k_rf_over_u = rf_end / abs(u_end)

        # 输出曲线（落在 run_dir）
        _write_rf_u_csv(os.path.abspath("rf_u.csv"), u_list, rf_list)

        # ----------------------------
        # 14) 汇总 metrics（合并 tray_v1 的接口统计 + Day5 仿真统计）
        # ----------------------------
        metrics = {}
        if isinstance(metrics_geom, dict):
            metrics.update(metrics_geom)
        n_top = int(metrics.get("n_top", 0))
        n_fix_faces = int(metrics.get("n_fix_faces", 0))
        n_fix_verts = int(metrics.get("n_fix_verts", 0))
        skip_fix_pads = int(metrics.get("skip_fix_pads", 0))
        pass_phys = (                       
        (n_top >= 1) and
        (n_fix_faces >= 4) and
        (n_fix_verts >= 4) and
        (elem_count > 0) and
        (abs(u_end) > 1e-12) and
        (abs(rf_end) > 1e-12)
    )
        metrics.update({
            "PASS": 1 if pass_phys else 0,       #布尔判据变量 pass_phys（物理口径通过与否），它根据这些条件计算：
            "case_id": case_id,                     #接口计数是否够（n_top / n_fix_faces / n_fix_verts）
            "mesh_size": mesh_size,                  #网格数量是否正常（elem_count > 0）
            "use_shell": 0,                            #响应是否有效（u_end、rf_end 非零）
            "elem_count": int(elem_count),
            "node_count": int(node_count),
            "u3_end": float(u_end),
            "rf3_end": float(rf_end),
            "peak_rf_abs": float(peak_rf_abs),
            "k_rf_over_u": float(k_rf_over_u),
            "odb_path": odb_path,
            "fail_reason": "",
            "fail_stage": "",
            "u3_rp": float(u_end),
            "rf3_rp": float(rf_end),
            "k33_rp": float(k_rf_over_u)
        })

        return metrics
    except Exception as e:
        exc_type_name = type(e).__name__
        enriched_msg = "[stage:%s][exc:%s] %s" % (stage, exc_type_name, str(e))
        raise Exception(enriched_msg)