Abaqus-Python parametric tray modeling and static simulation pipeline with reusable interfaces and standardized outputs.
## 1. What This Repo Does
本项目用于托盘模型的最小静力闭环验证，覆盖以下流程：
- 参数化托盘几何构建
- Part-level 接口创建
- 网格生成
- 静力步求解
- ODB 后处理
- 批量汇总输出

## 2. Current Capabilities

### Implemented

- 托盘几何构建与接口创建
- Solid 网格生成与静力分析
- RP 耦合加载与固定边界
- ODB 历史输出读取（`U3` / `RF3`）
- 结构化输出与批量汇总

### Not Implemented Yet

- 壳单元求解链
- 显式步与接触分析

## 3. Project Layout

```text
<project_root>/
├─ config/
│  ├─ caseA.json
│  ├─ caseB.json
│  └─ caseC.json
├─ src/
│  ├─ core/
│  └─ variants/
├─ runs/
├─ run_day5.py
└─ README.md
```

`project_root` 必须同时包含：

- `src/`
- `config/`

## 4. Requirements

- Abaqus/CAE available
- Abaqus Python environment available
- 从项目根目录运行，或显式设置 `TRAY_ROOT=<project_root>`

## 5. Case Configuration

默认批跑以下配置文件：

- `config/caseA.json`
- `config/caseB.json`
- `config/caseC.json`
  
当前 `run_day5.py` 会校验这些关键字段：
- `t`
- `mesh_size`
- `E`
- `nu`
- `rp_disp_u3`
- `pad`
- `eps`
- `search_box`
- `search_eps`

## 6. How To Run

### Option A: Abaqus noGUI

```bash
abaqus cae noGUI=run_day5.py
```

### Option B: Abaqus Python-Capable Environment

确保当前解释器可以访问 Abaqus API 后再执行：

```bash
python run_day5.py
```

## 7. Outputs

### Batch-Level Outputs

运行完成后，在项目根目录生成：

- `summary_day5.csv`
- `runs/_batch_summary.json`

### Per-Case Outputs

每个 case 输出到：

```text
runs/<case_id>/day5_static/
```

其中通常包括：

- `config_used.json`
- `metrics.json`
- `rf_u.csv`
- `traceback.txt`（仅失败时）
- Abaqus job files such as `.odb`, `.msg`, `.sta`, `.log`, `.inp`

## 8. PASS / FAIL

### PASS = 1

表示最小静力闭环通过，可用于回归比较。

### PASS = 0

表示某一阶段失败，可能包括：

- 配置校验
- 几何 / 接口创建
- 网格生成
- 边界条件或加载
- Job 提交 / 求解
- ODB 后处理

失败信息会写入：

- `metrics.json`
- `traceback.txt`（如有）

## 9. Notes

- 当前 Day5 基线面向 solid static 流程
- 输出协议已标准化，便于后续做回归测试和批处理扩展
- 若项目根目录无法识别，可设置环境变量 `TRAY_ROOT` 指向仓库根目录
