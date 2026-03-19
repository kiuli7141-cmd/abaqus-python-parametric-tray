# Tray CAE Automation - Day5 Static Baseline

## 1. What this repo does

此工程目标为托盘模型的最小静力闭环验证：

- 参数化托盘几何构建
- Part-level 接口创建
- 网格生成
- 静力步求解
- 结果后处理

---

## 2. Current Capabilities

已实现功能：

- 托盘几何构建与接口创建
- solid 网格生成与静力步求解
- RP 约束与顶面固定
- 结构化输出与批量汇总

尚未实现的功能：

- 壳单元求解链
- 显式步与接触

---

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
project_root 必须同时包含：

src/

config/

4. How to Run
4.1 Prepare Cases

在 config/ 中准备 JSON 配置文件，例如：

caseA.json

caseB.json

caseC.json

4.2 Enter Abaqus Environment

确保运行环境是 Abaqus 可用环境。

4.3 Execute Runner

执行 run_day5.py 脚本开始仿真：

python run_day5.py
5. Outputs

每个 case 输出到：

runs/<case_id>/day5_static/

包括：

config_used.json

metrics.json

traceback.txt（失败时）

6. PASS / FAIL
6.1 PASS = 1

完成最小静力闭环。

结果可用于回归比较。

6.2 PASS = 0

某一阶段失败：配置、建模、网格、BC、求解或后处理。