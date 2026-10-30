# 企业 AI 场景规划（Enterprise AI Scenario Map）

一套可以直接装进 AI Agent 工作台的技能：帮你把「AI 到底该在企业的哪些环节用」盘清楚。先盘场景、再谈系统，不拍脑袋、不凑数量。

## 它解决什么问题

很多企业的 AI 转型卡在同一处：知道要用 AI，不知道从哪个场景开始。听了汇报、看了演示、买了账号，半年后还在做方案。工具已经足够成熟，缺的是一套把场景找对、排好序、能验收的方法。

这个技能就是这套方法，配套内置行业流程底座和可直接运行的工具。

## 它能做什么

- **内置行业流程底座**：APQC 流程分类框架（PCF）11 个行业数据集、2 万余流程节点，按企业实际裁剪为「企业流程骨架」，不套模板
- **双入口盘点**：材料盘点（自下而上，沿流程追问任务、判断、例外与痛点）与趋势反推（自上而下，从画像与行业趋势推演目标流程）交替使用
- **统一盘点结构**：业务框架 → 大场景 → 近期/中期/远期目标态 → 原子用例；一个场景一个业务动作，不复制、不凑数
- **每个场景可验收**：原子用例配指标定义、样本、对照、阈值、测试方法与失败条件；先做 Demo，同口径测试后再扩围
- **排序不拍脑袋**：统一评分模型（AI 化价值 40%、实现可行性 30%、数据就绪度 30%）
- **标准交付物**：场景地图、三年行动计划、应用场景确认表（附 Excel 模板）

## 快速开始

### 方式一：装进 AI Agent 工作台（推荐）

适用于任何支持 SKILL.md 技能规范的 Agent 工作台（如 aily 工作台、Claude Code 等技能目录型 Agent）：

```bash
git clone https://github.com/xunhuang071-source/enterprise-ai-scenario-map.git
```

把整个 `enterprise-ai-scenario-map` 目录放进你的 Agent 技能目录（例如 `~/.aily/workspace/skills/` 或 `.claude/skills/`），对 Agent 说「帮我盘点我们公司的 AI 场景」「做一张场景地图」即可触发。

### 方式二：当方法论文档库用

不装 Agent 也可以直接读：`SKILL.md` 是方法总纲，`references/core/` 是方法细节，`references/deliverables/` 是交付物写法。

### 自检与工具

```bash
cd enterprise-ai-scenario-map
python3 scripts/process_framework_tools.py doctor --verify   # 检查数据完整性
python3 scripts/process_framework_tools.py catalog           # 列出内置行业数据集
python3 scripts/process_framework_tools.py search --industry 电商 --q 商家结算
```

工具仅依赖 Python 3.8+ 标准库。

## 目录结构

```
SKILL.md                     方法总纲（Agent 技能入口）
references/core/             核心方法：业务与证据、盘点、场景模型、命名、KPI、排序、评审
references/deliverables/     交付物写法：场景地图、三年行动计划、案例模板
references/examples/         场景线索与运行示例
assets/process-frameworks/   行业流程底座数据（APQC PCF 等）
assets/templates/            应用场景确认表 Excel 模板
scripts/                     流程底座查询与评分工具
tests/                       自测用例
```

## 数据来源与许可

- **APQC PCF**：本仓库包含 APQC Process Classification Framework® 的 AI 结构化版本（11 个行业数据集）。PCF 为 APQC 开放标准，原始许可允许在保留原 notice 与归属的前提下使用、复制与再分发；各数据集 `metadata.json` 保留完整原文许可与年份，详见 [assets/process-frameworks/NOTICE.md](assets/process-frameworks/NOTICE.md)。本仓库不代表 APQC 认可其中的裁剪或场景设计。
- **国内电商流程**：193 节点为本地编制 V0.1（非官方版本），来源与适用条件见对应 metadata。
- **SCOR**：不含 SCOR 数据（原始许可限制再分发），相关查询工具在数据缺失时会如实报告不可用。
- **代码与文档**：MIT License，见 [LICENSE](LICENSE)。

## 维护方与咨询合作

本技能由**上海序创信企业管理咨询有限公司**维护。技能面向社区免费开源；如果你希望有咨询顾问带全程——从调研访谈、场景盘点到三年行动计划落地——可以联系我们：

- 联系人：张标
- 微信：Xcx-zbiao2025
- 电话：15801985770

服务范围：企业 AI 场景盘点与场景地图、AI 三年行动计划、部门应用场景确认、已有规划稿评审。
