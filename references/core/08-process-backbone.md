# 企业流程骨架、AI目标流程与调用机制

## 1. 三个对象，一条主线

**行业流程底座 → 按企业实际裁剪 → 企业流程骨架 → 沿流程调研/模式推演 → AI目标流程 → 大场景、三期与原子用例。**

- 行业底座内置在技能assets/process-frameworks中，不只是外部引用或路径。资料的权威性/完整性与流程骨架的方法地位是两回事。
- 企业骨架是行业框架经企业实际裁剪修改后的业务架构；客户已有确认架构优先。企业名称不是足够的裁剪依据，初稿可标假设后逐步核实。
- AI目标流程设计任务、决策、数据、系统动作、人机分工和反馈如何变化，不只给原节点贴“智能”标签。痛点、战略和趋势共同参与。
- 业务域、端到端流程、子流程/任务属于“业务框架”内部，不新增场景盘点层级。一个大场景可贯通多过程，一个用例可支撑多流程；一个节点不强制造一个AI。

## 2. 先选行业底座，再建立企业实例

内置资源：

| 资源 | 建模作用 | 适配要求 |
|---|---|---|
| 11份APQC行业/通用结构化数据 | 业务域、过程范围、定义、指标 | 分类树不是执行流；显示真实年份及版本，行业数据须按企业实际裁剪 |
| 国内电商V0.1，193节点 | 按自营、第三方平台、代运营裁剪职责、任务与输入输出 | 非官方归纳，三级活动为分析展开；经营模式不清先问，B2B/B2C不足以区分责任 |
| SCOR-DS V14.0 2025介绍册 | 供应链主要过程概念和绩效线索 | 仅18页介绍册，75条记录不是75个流程；可初始化七概念骨架，不冒称完整Level 2/3目录 |

- 一个主骨架保持同层分类轴一致；第二框架用于深化对应过程，不把不同框架的根节点直接拼盘。
- 内置中文跨行业是V7.0.5；未内置工程/EPC专版、RIBA和PM²。不改用相近行业后冒称专版。
- 原始PDF/Excel不是日常查询依赖。Excel文件/工作表行号是原件出处，未随技能打包时不能把它当成可打开的本地文件。

## 3. 裁剪的是企业骨架，不是通用库

依据经营模式、业务对象、实际职责、合同和真实工作，做保留、排除、合并、拆分、新增、改名、调整分类及业务顺序。

每次关键修改留依据；重要选择给用户确认。企业实例写项目目录，保留稳定企业流程ID；行业编号只保存在source_refs。行业底座只读，不随项目修改。

骨架至少表达：对象与目标、起止/衔接、主责和协作、输入输出、数据知识、任务与判断、例外、系统、人机交接。未知处可空并列问题，不从行业模板推断客户已有系统、岗位或流程现状。

- 分类用parent_id；实际业务流用relations。分类树不成环，业务关系允许有理由的反馈/迭代。
- 节点perspective：current/target/both；关系perspective：current/target。confirmation单独记录hypothesis/supported/confirmed/excluded，防止“目标设计”冒充现状。
- 初稿导入的角色等标industry_suggestion_not_customer_fact。confirmed需客户确认记录定位；脚本只查结构，不证明确认真实存在。
- 合并、拆分保留退出节点与来源，企业ID不复用；拆分共享原参考不等于原库明示这些新节点；改名不改ID。涉及实际流转关系时须显式更新，不按编号自动连线。

## 4. 沿流程设计AI目标态

围绕企业骨架追问：何时触发、谁处理什么、依据何在、哪里需要模型判断、例外怎样处置、结果谁用、错误怎样发现。

同时问未来模式：交付方式、岗位协同、服务边界和判断时点能否改变？哪些工作应前移、重组、形成闭环？不要求每个机会都先有痛点，也不把既有流程当成不能改变的终点。

目标流程写入target_design或明确标target的新增任务/关系，说明：AI工作、人工作业、授权、接管、输出使用、反馈及失败处理，再组织大场景、三期状态、原子用例和测试。

用例用business_process_refs引用本企业BP等稳定ID。外部APQC/ECOM/SCOR编号不能代替企业归属。挂接结构有效不代表AI必要、职责合理、客户已确认或收益已证明。

未挂用例的过程可以是待调研、无需AI、已有能力或本轮范围外；不按覆盖率配额补场景。纯规则/系统优化明确归类，不包装成AI。

## 5. AI执行入口与调用顺序

以下命令以技能目录为工作目录；实际调用可使用脚本绝对路径。PROJECT是明确的项目目录，不是技能目录。数据默认从脚本相对位置解析，不依赖Downloads、工作目录或固定用户名。

### A. 识别可用底座，只取小索引

```bash
python3 scripts/process_framework_tools.py doctor --verify
python3 scripts/process_framework_tools.py catalog --industry 电商
python3 scripts/process_framework_tools.py outline --industry 电商 --depth 1
python3 scripts/process_framework_tools.py get --industry 电商 --id 10.3
python3 scripts/process_framework_tools.py get --framework scor --code RS.1.1
```

默认20条/12,000字符；按next_offset翻页。单条超预算按hint提高预算，不循环请求同一空页。不全量读取JSONL、SQLite或所有行业到模型上下文；关键词/别名是检索，不是语义搜索。

APQC可查询outline/search/get/children/subtree/metrics/compare；compare按PCF ID辅助并列，不证明跨行业等价。SCOR只查实际概念、记录、指标引用或原页，children/subtree返回不支持。

### B. 生成项目初稿，再按企业事实裁剪

```bash
python3 scripts/process_framework_tools.py init-project --industry 电商 --model marketplace --company-name "本项目企业" --depth 2 --output "PROJECT/企业流程骨架_v1.json"
python3 scripts/process_framework_tools.py tailor --project "PROJECT/企业流程骨架_v1.json" --operations "PROJECT/裁剪操作.json" --output "PROJECT/企业流程骨架_v2.json"
```

可用--dataset精确选版本、--root-id限定分支；SCOR用--framework scor初始化七概念骨架。初稿不是客户事实，也不自动产生AI场景。混合经营可不传model，依据每节点industry_applicability逐项裁剪；客户已有底稿直接复用/导出契约，不强制从行业模板重建。

operations是对象数组，每项有op、reason，可附evidence。接口：

- keep/drop/rename/reparent/update：id定位；drop有活跃子项时须cascade:true；update用changes更新业务字段，包括order和target_design。
- add：node含新企业id、name、parent_id及业务字段，目标任务显式perspective:target；不允许塞入伪造官方来源或确认状态。
- merge：ids、new_id、name，可指定parent_id；保留原来源并将直接子项归入新节点。跨父级须显式父级。
- split：id、items；有子项时children_map逐项指定新归属，不猜测。
- relate：relation含id/type/from/to/perspective，可有condition；type取sequence/decision/handoff/feedback/data_dependency。remove_relation按id移除。
- attach_reference：id定位企业节点，给resource_id、dataset_id、reference_key及purpose；工具从实际库核对并补齐来源/归属，不接受手写官方身份。第二框架用于深化对应过程，不拼接根节点。
- update_company：changes修订名称/经营模式，保留依据并重置活跃节点确认；不得靠换名复用另一客户事实。
- confirm_node/confirm_architecture：必须有kind=customer_confirmation及locator。整体确认必须为本批最后一步；后续改动重新成为draft。

写入必须显式指定output，拒绝覆盖文件、拒绝写回技能目录。裁剪失败不写半成品。JSON是内部可选投影，不要求客户额外填台账。

### C. 后续调研和场景设计查企业骨架，不退回行业模板

```bash
python3 scripts/process_framework_tools.py project-outline --project "PROJECT/企业流程骨架_v2.json"
python3 scripts/process_framework_tools.py project-get --project "PROJECT/企业流程骨架_v2.json" --id BP-0001
python3 scripts/process_framework_tools.py coverage --project "PROJECT/企业流程骨架_v2.json" --scenarios "PROJECT/场景投影.json"
python3 scripts/process_framework_tools.py validate --project "PROJECT/企业流程骨架_v2.json"
```

coverage检查企业流程归属与未评估部分，不要求所有节点有AI。场景投影可嵌入process_architecture，由scenario_tools.py validate联合检查；旧投影仍兼容，但新任务内容仍应说明实际流程位置。

## 6. 来源、指标与运行边界

- source_refs保存建模出处；企业流程挂接保存业务归属，两者分开。
- 用例evidence可用framework_reference，字段见场景模型。它证明构思/建模依据，不能证明客户事实或自动升级confirmation。
- 从业务目标到流程绩效再到AI测试。SCOR没有公式就不补公式；APQC有原定义也先核对口径。客户基线、阈值、收益仍须取样、Demo及业务复核。
- 内置结构化数据可在本地完整调用。APQC许可和原归属随包保留；SCOR含NC/ND及额外复制限制，其本地payload被Git忽略，不能通过同步/发布绕过授权。
- 企业底稿/流程图摘录到报告或单独导出时，按适用原许可保留source_notices及指定归属，不因只导图而丢失；SCOR资料不自动外发。
- Git克隆可能缺少受限SCOR；doctor明确报告，不能声称库齐全。无资料时仍从客户材料建立骨架并说明缺口；无本地工具时明确尚未读取库。
- SQLite是只读可选缓存。缺失时从技能内JSONL构造内存索引，不写缓存、不回读Excel、不新增服务、不调用外部模型。
- 仅显式--library或ENTERPRISE_AI_FRAMEWORK_HOME可改变资料根；不递归搜全盘、不自动改用其他行业或版本。

只读查询和项目写入均遵守运行环境权限；Explore不允许写项目时只建计划。脚本被权限阻止时说明并请求批准，不修改全局权限、不用其他工具绕过。
