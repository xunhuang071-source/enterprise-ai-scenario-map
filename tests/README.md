# 测试

在技能根目录运行：
- `python3 -m unittest discover -s tests -p 'test_*.py' -v`：脚本、字段、评分、文件引用、品牌扫描与资产完整性。
- `python3 tests/demo_iteration.py --output /会话/demo-result.json`：实际运行两轮合成规则替身，保存逐样本结果；不代表真实模型成效。
- `python3 scripts/scenario_tools.py validate tests/fixtures/project.json`：示例底稿完整性。
- 按 [behavior-cases.md](behavior-cases.md) 执行语义回归，保存输出和审查结论；核对年度参数化测试副本。

核心脚本与单元测试用标准库。人工视觉与 Excel 语义复核使用执行环境的浏览器和表格工具，不作为技能运行时依赖。
迁移前后工作簿非预期改动通过原件哈希和 ZIP 项比较；两张导引图内容按批准方案更新，不要求二进制相同。
真实任务需另做真实数据、模型、业务效果和合规验证。测试脚本不替代行业判断或客户确认。

## 流程骨架与内置数据回归（v2.1.0）

统一运行仍用`python3 -m unittest discover -s tests -p 'test_*.py' -v`。新增test_process_backbone.py覆盖企业裁剪、稳定ID、不覆盖、分类/流转区分、客户确认、可选投影、三经营模式、真实查询、相同数量更新的缓存失效、中文路径和无缓存/无SCOR迁移。

可复现示例：`python3 tests/process_backbone_demo.py --output-dir "PROJECT/合成流程演示"`。输出目录须在技能外且不存在；详见[流程示例](../references/examples/process-backbone-example.md)。该示例实际调用本地工具，但使用合成企业假设，不运行真实LLM或证明客户收益。

SCOR受限payload不自动Git同步；相关本地联调缺失时明确skip或验证resource_missing，不能把未测试当通过。APQC规范数据与缓存都在技能内，无缓存不落盘即可查询。Python 3.8语法兼容检查不等于已在每个Python发行版上做运行验证。
