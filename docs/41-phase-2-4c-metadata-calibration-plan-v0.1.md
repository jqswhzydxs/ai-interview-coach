# Phase 2.4C Plan

1. 在 run2 外保存最终决策；记录 AI evaluator 类型、失败门禁和 baseline 数量异常。
2. 对 run2 与既有 agents、Prompt、Schema、配置、迁移建立 SHA-256 保护清单。
3. 从报告定位 Candidate，只读关联正文、metadata 和既有评分，统计 case、模块、
   位置、分值分布和字段退化；不改分、不把它当作新版本验收分。
4. 先冻结独立 authored holdout，再实现独立纯确定性 metadata assembler。
   按问句意图和主题生成，按字段级证据检索；没有证据就明确说明局限。
5. 使用无网络客户端实例在离线 replay 中比较 v1/v2。冻结 replay corpus；
   schema、严格数量、重复、证据引用、完整 metadata 边界和重复运行相等逐项验证。
6. 输出带版本的工程比较报告和单独匿名盲评目录。映射只放 audit，不进入包。
7. 运行专项与全量离线、迁移、compileall、git diff --check，复核保护哈希。
8. 交付 Spec/Plan/Tasks/Risk、误差分析、离线报告和盲评材料后停止，等待独立
   metadata 盲评。不接入生产，不调整模型输出链路，也不安排真实 A/B。
