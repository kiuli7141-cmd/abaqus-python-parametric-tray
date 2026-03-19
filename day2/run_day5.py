# -*- coding: utf-8 -*-
import os, sys, json, csv, traceback, importlib, shutil

def _has_markers(p):          #判断“项目根目录”的唯一物理契约
    return (os.path.isdir(os.path.join(p, "src"))
            and os.path.isdir(os.path.join(p, "config"))) #给定的路径 p 下，是否同时存在 src 和 config 文件夹

def _find_root_upwards(start_dir, max_up=6): #向上寻路路径
    p = os.path.abspath(start_dir)  
    for _ in range(max_up + 1):
        if _has_markers(p):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return None

def resolve_root():   #环境变量，脚本物理，系统启动参数，工作目录。4 种寻找起点。确保把系统挂载到正确的 ROOT
    # 1) 显式指定：最稳（GUI/noGUI 都适用）
    env_root = os.environ.get("TRAY_ROOT", "").strip()
    if env_root:
        r = _find_root_upwards(env_root)
        if r:
            return r

    # 2) 标准 python/noGUI：__file__ 可能存在
    try:
        f = __file__
    except NameError:
        f = None
    if f:
        r = _find_root_upwards(os.path.dirname(os.path.abspath(f)))
        if r:
            return r

    # 3) Abaqus GUI Run Script：sys.argv[0] 通常是脚本路径
    a0 = sys.argv[0] if (hasattr(sys, "argv") and sys.argv) else ""
    if a0:
        a0 = os.path.abspath(a0)
        base = os.path.dirname(a0) if os.path.isfile(a0) else a0
        r = _find_root_upwards(base)
        if r:
            return r

    # 4) 兜底：当前工作目录（不保证对，但比直接死更好）
    # 3b) noGUI may pass script path in argv token (e.g. noGUI=day2/run_day5.py)
    if hasattr(sys, 'argv') and sys.argv:
        for tok in sys.argv:
            if not tok:
                continue
            cand = tok.split('=', 1)[1] if tok.startswith('noGUI=') else tok
            if cand.lower().endswith('.py'):
                base = os.path.dirname(os.path.abspath(cand))
                r = _find_root_upwards(base)
                if r:
                    return r

    # 3c) Abaqus execfile context: __file__ may be missing, but stack has script path
    try:
        import inspect
        for fr in inspect.stack():
            if hasattr(fr, "filename"):
                fn = fr.filename
            elif isinstance(fr, tuple) and len(fr) > 1:
                fn = fr[1]
            else:
                fn = ""
            if not fn or fn.startswith("<"):
                continue
            base = os.path.dirname(os.path.abspath(fn))
            r = _find_root_upwards(base)
            if r:
                return r
    except Exception:
        pass

    r = _find_root_upwards(os.getcwd())
    if r:
        return r

    raise RuntimeError(
        "Cannot locate project ROOT (need folders: src/ and config/). "
        "Set env TRAY_ROOT to project root, or run script from within project tree."
    )
#♥♥上述函数是基于项目标记（Marker Folders，如 src 和 config）的向上溯源寻址机制
ROOT = resolve_root()
CONFIG_DIR = os.path.join(ROOT, "config")
LOG = os.path.join(ROOT, "_import_traceback.txt")
CSV_OUT = os.path.join(ROOT, "summary_day5.csv")
RUNS_DIR = os.path.join(ROOT, "runs")  # runs/<case_id>/day5_static/   #路径解析与工作空间定义

# 关键：让 import src.xxx 生效（你的 runner 依赖这个） :contentReference[oaicite:6]{index=6}
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)   #把根目录插入模块搜索路径   .insert()列表方法

os.chdir(ROOT)   #变更当前工作目录为指定路径=强制指定路径，强行切断与外部杂乱环境的联系


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
#   硬盘 → 内存

def dump_json(path, d):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
#	 内存 → 硬盘
def build_case_paths(case_id): #统一文件路径，路径的命名表
    run_dir = os.path.join(RUNS_DIR, str(case_id), "day5_static")
    return {
        "run_dir": run_dir,
        "config_used_json": os.path.join(run_dir, "config_used.json"),
        "metrics_json": os.path.join(run_dir, "metrics.json"),
        "traceback_txt": os.path.join(run_dir, "traceback.txt"),

        # Step4 先占坑，后续真正接入时再写内容
        "stdout_log": os.path.join(run_dir, "stdout.log"),
        "job_inp": os.path.join(run_dir, "job.inp"),
    }
def dump_text(path, text):#纯文本统一函数
    with open(path, "w", encoding="utf-8") as f:
        f.write(text if text is not None else "")
def write_case_preamble(paths, cfg):  #写启动时固定产物
    os.makedirs(paths["run_dir"], exist_ok=True)
    dump_json(paths["config_used_json"], cfg)
def write_case_result(paths, metrics, traceback_text=None):#写启动时固定产物
    dump_json(paths["metrics_json"], metrics)
    append_csv(to_summary_row(metrics))

    if traceback_text:
        dump_text(paths["traceback_txt"], traceback_text)
def append_csv(row_dict, path=CSV_OUT):#表头
    header = [          
        "case_id",
        "mesh_size",
        "use_shell",

        # 接口/网格规模
        "n_top",
        "n_fix_faces",
        "n_fix_verts",
        "elem_count",
        "node_count",

        # 响应/派生指标
        "u3_end",
        "rf3_end",
        "peak_rf_abs",
        "k_rf_over_u",

        # 判据/错误
        "PASS",
        "fail_stage",
        "fail_reason",
    ]
    file_exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)    #用f里的文件，header里的排版写入
        if not file_exists:    #新建的文件（探测结果为 False），就先在第一行写上列名（写表头）。
                                #如果不加这个判断，你每跑一个 Case 就会在数据中间插入一行表头。
            w.writeheader()
        w.writerow({k: row_dict.get(k, "") for k in header})
def to_summary_row(metrics):
    """
    数据清洗解耦，分离数据层与物理层只做字段映射（metrics -> CSV row），不做任何物理计算计算。
    缺字段允许为空字符串，保证 CSV 汇总稳定。
    """
    metrics = metrics or {}

    row = {
        # ---- 旧列（保持兼容）----
        "case_id": metrics.get("case_id", ""),
        "mesh_size": metrics.get("mesh_size", ""),
        "use_shell": metrics.get("use_shell", ""),
        "elem_count": metrics.get("elem_count", ""),
        "u3_end": metrics.get("u3_end", ""),
        "rf3_end": metrics.get("rf3_end", ""),
        "peak_rf_abs": metrics.get("peak_rf_abs", ""),
        "k_rf_over_u": metrics.get("k_rf_over_u", ""),
        "PASS": metrics.get("PASS", 0),
        "fail_reason": metrics.get("fail_reason", ""),

        # ---- Day6 扩展列（如果你的 append_csv header 已扩列，就会写进去）----
        "node_count": metrics.get("node_count", ""),
        "n_top": metrics.get("n_top", ""),
        "n_fix_faces": metrics.get("n_fix_faces", ""),
        "n_fix_verts": metrics.get("n_fix_verts", ""),
        "fail_stage": metrics.get("fail_stage", ""),
    }

    return row


def make_fail_metrics(case_id, exc, fail_stage="runtime"):
    # 先做最小失败协议，对齐成功数据数据模式（Day6-Step1）       ***************************
    return {
        "case_id": str(case_id),
        "mesh_size": "",
        "use_shell": "",
        "elem_count": "",
        "u3_end": "",
        "rf3_end": "",
        "peak_rf_abs": "",
        "k_rf_over_u": "",
        "fail_stage": fail_stage,
        "PASS": 0,
        "fail_reason": str(exc)
    }

def validate_cfg_basic(cfg):
    # Day6-Step2: 输入配置数据是否合规校验,判断错误数据，平铺判断（不做 schema 重构）
    def _num(name):
        if name not in cfg:
            raise ValueError("missing key: %s" % name)
        try:
            return float(cfg[name])
        except Exception:
            raise ValueError("key %s must be numeric, got %r" % (name, cfg[name]))

    # 必要字段（当前你 day5_static.py 是平铺读取）
    t = _num("t")
    mesh_size = _num("mesh_size")
    E = _num("E")
    nu = _num("nu")
    rp_disp_u3 = _num("rp_disp_u3")
    pad = _num("pad")
    eps = _num("eps")
    search_box = _num("search_box")
    search_eps = _num("search_eps")

    if t <= 0: raise ValueError("t must > 0")
    if mesh_size <= 0: raise ValueError("mesh_size must > 0")
    if E <= 0: raise ValueError("E must > 0")
    if not (0.0 < nu < 0.5): raise ValueError("nu must be in (0, 0.5)")
    if abs(rp_disp_u3) <= 1e-12: raise ValueError("rp_disp_u3 must != 0")
    if pad <= 0: raise ValueError("pad must > 0")
    if eps <= 0 or search_box <= 0 or search_eps <= 0:
        raise ValueError("eps/search_box/search_eps must all > 0")
def finalize_metrics_for_output(metrics, case_id):
    """
    Step3: runner层输出协议补齐器（第一次收口）
    只做：
    - 保证 metrics 是 dict
    - 补齐缺省字段（成功/失败统一口径）
    - 保留已有字段值（不重算物理量）
    - 加输出协议版本锚点
    不做：
    - 物理计算
    - PASS 门禁判据计算
    """

    # 1) 兜底：确保是 dict
    if not isinstance(metrics, dict):
        metrics = {
            "PASS": 0,
            "fail_reason": "metrics is not dict: %r" % (type(metrics),)
        }
    else:
        metrics = dict(metrics)

    # 2) case_id：缺失或空时补 runner 的 case_id
    if ("case_id" not in metrics) or (metrics.get("case_id") is None) or (str(metrics.get("case_id")).strip() == ""):
        metrics["case_id"] = str(case_id)

    # 3) 输出协议版本锚点
    if ("output_protocol_ver" not in metrics) or (metrics.get("output_protocol_ver") is None):
        metrics["output_protocol_ver"] = "day6_step3_v1"

    # 4) 统一补齐顶层字段（仅补缺失/None，不覆盖已有值）
    defaults = {
        # --- 失败/状态类 ---
        "PASS": 0,
        "fail_reason": "",
        "fail_stage": "",

        # --- case / 配置回显类 ---
        "mesh_size": "",
        "use_shell": "",

        # --- 接口/网格规模类 ---
        "n_top": "",
        "n_fix_faces": "",
        "n_fix_verts": "",
        "elem_count": "",
        "node_count": "",

        # --- 响应类 ---
        "u3_end": "",
        "rf3_end": "",
        "peak_rf_abs": "",
        "k_rf_over_u": "",
    }

    for k, v in defaults.items():
        if (k not in metrics) or (metrics.get(k) is None):
            metrics[k] = v

    # 5) PASS 只做类型收口，不改业务含义
    try:
        metrics["PASS"] = int(metrics.get("PASS", 0))
    except Exception:
        metrics["PASS"] = 0

    return metrics
def run_one(case_path):
    cfg = load_json(case_path)
    case_id = str(cfg.get("case_id", "CASE"))
    paths = build_case_paths(case_id)
    os.makedirs(paths["run_dir"], exist_ok=True)
    validate_cfg_basic(cfg)
    # 关键：进入 run_dir 跑 job，保证 odb/msg/sta 都落在该目录
    cwd0 = os.getcwd()
    try:
        write_case_preamble(paths, cfg)
        os.chdir(paths["run_dir"])

        mod = importlib.import_module("src.variants.day5_static")
        importlib.reload(mod)

        metrics = mod.run_day5_static(cfg)
        metrics = finalize_metrics_for_output(metrics, case_id)
        # === 给 Abaqus/CAE Job Manager 的 Results 按钮准备一份 ROOT 侧 ODB 镜像 ===
        odb_src = metrics.get("odb_path", "")
        if odb_src and os.path.isfile(odb_src):
            odb_gui = os.path.join(ROOT, os.path.basename(odb_src))
            if os.path.abspath(odb_src) != os.path.abspath(odb_gui):
                shutil.copy2(odb_src, odb_gui)
        write_case_result(paths, metrics)

        print("OK:", case_id, "->", paths["run_dir"])
        return metrics 
    except Exception as e:#成功时回传数据位移什么的，pass=1#原来的路径是保证能跑，出错了要复位。现在是能跑，出错了捕获异常，然后再复位
        tb_text = traceback.format_exc()

        err_text = str(e)
        if ("missing key" in err_text
                or "must be numeric" in err_text
                or "must > 0" in err_text
                or "must all > 0" in err_text
                or "must be in (0, 0.5)" in err_text
                or "must != 0" in err_text):
            fail_stage = "cfg_validate"
        else:
            if err_text.startswith("[stage:"):
                p1 = err_text.find("[stage:")
                p2 = err_text.find("]", p1)
                if p1 != -1 and p2 != -1:
                    fail_stage = err_text[p1 + len("[stage:"):p2].strip() or "variant_run"
                else:
                    fail_stage = "variant_run"
            else:
                fail_stage = "variant_run"

        metrics = make_fail_metrics(case_id, e, fail_stage=fail_stage)
        metrics = finalize_metrics_for_output(metrics, case_id)

        write_case_result(paths, metrics, traceback_text=tb_text)

        print("FAIL:", case_id, "[%s]" % fail_stage, "->", paths["run_dir"])
        return metrics #失败时回传失败原因，pass=0
    finally:
        os.chdir(cwd0)


DEFAULT_CASES = ["caseA.json", "caseB.json", "caseC.json"]

def resolve_case_paths(case_names=None): #实现调度引擎与任务队列的解耦，不需要改批跑主逻辑，主循环只负责纯粹的执行与容错流转
    names = case_names or DEFAULT_CASES
    return [os.path.join(CONFIG_DIR, name) for name in names]
def reset_batch_outputs():#删历史summary，后续批跑阶段要修改成不删
    if os.path.exists(CSV_OUT):
        os.remove(CSV_OUT)
    if os.path.exists(LOG):
        os.remove(LOG)
def summarize_batch(results):#Batch（批次）级的聚合监控层，做到全局观测调度器运行
                            # 结束后，将所有单例的 metrics 聚合成一个高维度的概要对象。为后续接入飞书机器人报警提供了直接的结构化数据接口
    results = results or []

    total = len(results)
    n_pass = 0
    n_fail = 0
    fail_items = []

    for r in results:
        try:
            passed = int(r.get("PASS", 0)) == 1
        except Exception:
            passed = False

        if passed:
            n_pass += 1
        else:
            n_fail += 1
            fail_items.append({
                "case_id": r.get("case_id", ""),
                "fail_stage": r.get("fail_stage", ""),
                "fail_reason": r.get("fail_reason", ""),
            })

    return {
        "total": total,
        "n_pass": n_pass,
        "n_fail": n_fail,
        "fail_items": fail_items,
    }

#batch后续程序/系统”读取的机器摘要文件
def run_batch(case_names=None):#次级结果对象，summary不再是唯一的汇总
    reset_batch_outputs()

    case_paths = resolve_case_paths(case_names)
    results = []

    for case_path in case_paths:
        metrics = run_one(case_path)
        results.append(metrics)

    summary = summarize_batch(results)
    dump_json(os.path.join(RUNS_DIR, "_batch_summary.json"), summary)
    return results, summary
def main():
    results, summary = run_batch(DEFAULT_CASES)
    print("OK: Day5 static regression finished. pass=%d fail=%d total=%d"
          % (summary["n_pass"], summary["n_fail"], summary["total"]))

if __name__ == "__main__":
    main()












def run_day8_preview(cfg):
    model_name = cfg.get("model_name", "Model-1")
    if model_name in mdb.models:
        del mdb.models[model_name]
    model = mdb.Model(name=model_name)

    # 1) 先建托盘（你已有的 Day1-Day4 地基）
    out = build_and_tag_tray_v1(model, cfg)  # 你按自己函数签名调整
    a = model.rootAssembly

    # 2) 建压头并定位
    tray_dims = dict(L=cfg["tray"]["L"], W=cfg["tray"]["W"])
    z_top = cfg["tray"]["t"]
    platen_metrics = build_platen_v0(model, a, cfg, tray_dims=tray_dims, z_top=z_top)

    return dict(**out, **platen_metrics)