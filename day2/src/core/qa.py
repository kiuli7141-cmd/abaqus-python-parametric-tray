# -*- coding: utf-8 -*-

def _name(name):
    return str(name) if name is not None else "<unnamed>"

def log_count(name, seq):
    """
    打印数量并返回 n
    seq: vertices/edges/faces/cells 或 list/tuple
    """
    try:
        n = len(seq)
    except Exception:
        # 有些 Abaqus 对象不支持 len，极少见；兜底
        n = 0
        try:
            for _ in seq:
                n += 1
        except Exception:
            n = -1
    print("[COUNT] %-20s = %s" % (_name(name), n))
    return n

def assert_min(name, n, min_n, hint=""):
    """
    若 n < min_n 直接抛错；hint 用于告诉未来的你该先查 bbox/eps/pad 哪个
    """
    if n < min_n:
        msg = "[QA FAIL] %s: n=%s < min=%s. %s" % (_name(name), n, min_n, hint)
        raise RuntimeError(msg)

def assert_between(name, n, min_n=None, max_n=None, hint=""):
    """
    可选上下限门禁
    """
    if (min_n is not None) and (n < min_n):
        msg = "[QA FAIL] %s: n=%s < min=%s. %s" % (_name(name), n, min_n, hint)
        raise RuntimeError(msg)
    if (max_n is not None) and (n > max_n):
        msg = "[QA FAIL] %s: n=%s > max=%s. %s" % (_name(name), n, max_n, hint)
        raise RuntimeError(msg)
def assert_key_exists(container, key, hint=""):
    #container: a.sets / a.surfaces / m.parts[...] 等 dict-like
    
    if key not in container.keys():
        raise RuntimeError("[QA FAIL] missing key '%s'. %s" % (key, hint))

def log_keys(title, container, max_show=20):
    keys = list(container.keys())
    if len(keys) > max_show:
        keys = keys[:max_show] + ["...(%d more)" % (len(container.keys())-max_show)]
    print("[KEYS] %s: %s" % (title, keys))