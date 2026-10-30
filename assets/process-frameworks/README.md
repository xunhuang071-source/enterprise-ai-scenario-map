# 内置流程框架知识底座

本目录存放真实AI结构化数据，不是外部路径占位。行业底座用于按企业实际裁剪流程骨架，再设计AI目标流程；不是固定AI场景清单。

## 入口

- [建模与调用机制](../../references/core/08-process-backbone.md)
- [合成运行示例](../../references/examples/process-backbone-example.md)
- [来源与分发说明](NOTICE.md)
- [原资料目录](pcf-and-ecommerce/行业目录.md)

## 内容

- pcf-and-ecommerce：11个APQC数据集20,896节点，以及明确非官方的国内电商V0.1编制193节点，共21,089节点。原定义、补充差异、双语映射、流程—指标关联及出处保留。
- scor-intro：本机内置SCOR-DS V14.0 ©2025介绍册AI版，18页、75条参考记录，含7个过程概念与20个一级指标引用。不是完整过程库，Git不自动同步该受限payload。
- registry.json：真实资源与范围描述；不能把已登记等同于实际文件存在。
- manifest.json：可同步的规范数据文件哈希。本地导入记录另验证SCOR副本，且不发布个人原始路径。

SQLite为只读可选缓存，Git忽略；无缓存时工具直接从本目录JSONL构造内存索引，不回读Excel，不写缓存。缓存与规范数据摘要不符时也回退，不能让旧数据库成为第二份真相。

## 使用

从技能目录运行：

```bash
python3 scripts/process_framework_tools.py doctor --verify
python3 scripts/process_framework_tools.py catalog
python3 scripts/process_framework_tools.py search --industry 电商 --q 商家结算
```

命令默认只返回小页面；按next_offset继续。行业数据不改写为客户事实，企业实例不得写本目录。

## 跨机器

复制完整技能目录可带上本机内置资料；受限资料跨主体/外发须先核对授权，不能因技术可复制而视为允许分发。Git同步含方法、工具、APQC归属与允许分发的规范数据，但排除SQLite、个人导入记录和SCOR受限payload。仅Git克隆时SCOR可能缺失，doctor会明确报告，不自动联网或伪造完整模型。

原PDF、Excel继续保留于用户原资料位置，不是日常查询依赖；原工作表/物理页信息作为出处，不伪造新位置。内置源包说明保留其原整理语境，统一调用请以本技能入口为准。
