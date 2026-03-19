# -*- coding: utf-8 -*-
import os, sys, json, csv, traceback, importlib

def _has_markers(p):
    return (os.path.isdir(os.path.join(p, "src"))
            and os.path.isdir(os.path.join(p, "config")))

def _find_root_upwards(start_dir, max_up=6):
    p = os.path.abspath(start_dir)
    for _ in range(max_up + 1):
        if _has_markers(p):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return None

def resolve_root():
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
    r = _find_root_upwards(os.getcwd())
    if r:
        return r

    raise RuntimeError(
        "Cannot locate project ROOT (need folders: src/ and config/). "
        "Set env TRAY_ROOT to project root, or run script from within project tree."
    )

ROOT = resolve_root()
CONFIG_DIR = os.path.join(ROOT, "config")
LOG = os.path.join(ROOT, "_import_traceback.txt")
CSV_OUT = os.path.join(ROOT, "summary_day2.csv")
RUNS_DIR = os.path.join(ROOT, "runs")  # runs/<case_id>/day5_static/

# 关键：让 import src.xxx 生效（你的 runner 依赖这个） :contentReference[oaicite:6]{index=6}
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 关键：相对路径落盘稳定（config / runs 都相对 ROOT）
os.chdir(ROOT)

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def append_csv(row_dict, path=CSV_OUT):
    header = ["case_id","t","rib_off","rib_w","n_top","n_rib_bottom","n_fix_faces", "n_fix_verts","skip_fix_pads"]
    file_exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if not file_exists:
            w.writeheader()
        w.writerow({k: row_dict.get(k, "") for k in header})
def run_one(case_path):
    p = load_json(case_path)

    mod = importlib.import_module("src.variants.tray_v1")
    importlib.reload(mod)

    metrics = mod.build_and_tag_tray_v1(p)
    print("[SUMMARY]", metrics)
    append_csv(metrics)

if os.path.exists(LOG):
    os.remove(LOG)

try:
    cases = ["caseA.json", "caseB.json", "caseC.json"]
    for c in cases:
        run_one(os.path.join(CONFIG_DIR, c))
    print("OK: Day2 Block5 regression finished. CSV -> summary_day2.csv")
except Exception:
    with open(LOG, "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
    print("ERROR: failed. See _import_traceback.txt")
