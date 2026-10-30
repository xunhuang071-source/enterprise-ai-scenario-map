# 统一场景模型与最小字段契约

## 结构

企业业务框架 → 大场景 → 近期／中期／远期目标态 → 原子用例。
不新增“规划条目”中间层；报告章节、重点条目只是表达视图。
业务框架内包含按本企业实际裁剪后的流程骨架。流程分层不新增场景层级；每个用例定位到本企业任务/判断，说明AI嵌入或重组何处。行业编号不是企业流程归属，详细机制见[流程骨架](08-process-backbone.md)。

大场景：业务边界、现状／痛点、未来模式、三期状态、各期用例、业务 KPI、重点标记。
原子用例：能独立测试的业务任务／任务模块，输出与使用方式独立才拆分。任务内的读取、分析、生成步骤不机械拆成三个用例。
同一用例可跨期升级，不为每期复制 ID；每个目标态必须有支撑用例或明确的待补验证项，正式计划不能用空框架冒充已落实任务。

## 一份底稿，多种视图

保留稳定 ID，显示序号可重排。底稿保存大场景、用例、证据、KPI、确认状态和映射；主文、副表、报告和图均由底稿派生。
正式规划的场景内容以客户最新确认工作簿为准，内部机读投影不能反向覆盖客户手工修改。
不要求客户再填 JSON 或重复台账；需要脚本校验时导出以下可选投影。

## JSON 投影（脚本接口）

顶层：`mode`（opportunity 或 action_plan）、`big_scenarios`、`use_cases`。

大场景：
- `id`、`name`、`focus`（main 或 appendix）、`scope`、`current_state`、`future_mode`。
- `kpis`：对象数组，每项含 `metric`、`definition`、`unit`、`baseline_method`。
- `states`：三项，`phase` 为近期／中期／远期，`goal` 描述可观察状态，`use_case_ids` 引用用例。年度可另填，未确认留空。

原子用例：
- `id`、`parent_id`、`name`、`form`（assistant／digital_employee／agent）。
- `business_task`、`input`、`ai_work`、`human_work`、`handoff`、`output`、`user`。
- `source_line`：pain／trend／both；`evidence` 数组记录来源定位与性质。
- `confirmation`：hypothesis／supported／confirmed／excluded；`build_status`：existing／in_progress／proposed，两者互不替代。
- `test`：`kpi`、`definition`、`unit`、`sample`、`baseline`（value 可空、method 必填）、`threshold`（value 可空、status 标 confirmed／hypothesis／pending）、`test_method`、`failure`、`iterations`。
- `assessment`：value／feasibility／data 的 1 至 5 分或 null、各项 basis；`readiness`：compliance／owner／data_access／dependencies 的 true／false／null。

unknown 不填 0；null 不能解释成已完成。用例的各期能力增量可在目标态与测试迭代中记录，不再生成新身份。
排除项留处置记录，不计入当前场景；脚本严格校验当前视图不引用 excluded 项。真实文稿只在目标态设计时可标待验证，正式建设任务引用的用例必须 confirmed。

## 主场景和副表

将主要分析精力投向核心业务价值和示范模式，主场景完整展开三期、关键用例与测试；其余轻写进副表。
不是按用例数量硬切 20%，也不要求固定重点个数。
允许副表用 ID 引用主场景用例，但不逐行复述；父子、共用能力和跨部门调用不是重复建设。统计分别报告大场景数、原子用例数，不把父子相加。
同一用例一个主责归属，跨业务支撑用引用表示。名称改变须保留 ID 并同步所有视图。

## 企业流程挂接（可选机读扩展）

业务内容必须能说明实际流程位置；JSON仍是可选投影。
- 顶层可嵌入`process_architecture`：schema_version=1.0、company、version、status、processes、relations、evidence及tailoring_history。详见流程骨架模块的工具生成示例。
- 大场景可填`business_process_refs`；原子用例在该投影中须用同字段引用活跃企业流程ID，例如BP-0001。一个用例可引用多个过程，主责仍只归一个大场景。不能直接用APQC/ECOM/SCOR编号顶替。
- 节点分current/target/both，关系分current/target；target_design说明AI工作、人工作业、交接和反馈。行业节点导入初稿不等于客户现状，新增目标任务不等于已经运行。
- 客户已有底稿可直接使用，或导出此契约后校验，不强制先运行init-project。原旧投影无此扩展继续兼容；新提供流程引用时必须附架构，不能假装已核对。
- evidence可增加`kind=framework_reference`，含dataset_id、version、source_type、is_official、locator、purpose（architecture/task_scope/metric_hint）、proves_customer_fact=false。只说明建模出处，不能自动支持或确认客户事实。

脚本检查ID、类型、引用和来源声明，不证明流程语义正确、AI必要或客户确认真实。覆盖空白应转为调研、无需AI或范围决策，不强制补用例。
