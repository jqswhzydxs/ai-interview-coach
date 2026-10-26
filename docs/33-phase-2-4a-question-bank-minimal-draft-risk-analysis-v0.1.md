# Phase 2.4A：QuestionBank 最小草稿协议风险分析 v0.1

## 1. 伪“单次调用”风险

风险：表面上使用 Draft，内部却按三个模块调用 provider 三次，或在 assembler 外新增重试。

控制：候选只调用一次 `run_with_fallback`，一个 request 同时包含三组草稿；transform 在该 attempt 内同步执行。BaseAgent 仍是唯一重试循环，测试断言成功 calls=1、失败 calls=2。

## 2. 基线被候选污染风险

风险：通过修改 `QuestionBankAgent.prompt_version` 或全局 factory 做 A/B，导致同进程结果互相污染。

控制：独立候选类、独立 prompt 文件、构造函数注入 factory；默认运行时继续实例化基线。测试在同一进程交错构建请求并检查各自 prompt/schema。

## 3. 最终 Schema 被隐式放宽风险

风险：因为模型只返回文本，最终字段缺失或用默认空值绕过业务约束。

控制：Draft Schema 只是内部输入；assembler 必须填充所有字段，并调用原 `QuestionBank.model_validate()`。Harness 仍以最终 QuestionBank Schema 做第二道验证。

## 4. assembler 职责过重风险

风险：把问题内容本身也规则化，候选退化为 Phase 2.3 fallback，无法评估最小草稿协议。

控制：模型保留 `question_text` 的完整生成权；assembler 只验证内容边界并生成可确定字段，不改写问题文本。mock 路径明确是 fallback；fake-provider 成功路径必须保留 fake 输出文本。

## 5. 元数据过度通用风险

风险：确定性评分锚点、追问和建议不够贴合每道题。

控制：2.4A 先复用已验证的 Phase 2.3 安全模板，确保不编造和可验证；真实验收时单独评价问题质量。若需要按题型细化 assembler，作为后续单变量迭代，不在本阶段混入。

## 6. 技术边界误判风险

风险：技术别名、大小写或普通词误触发串栈门禁，例如 Go 与英文动词混淆。

控制：使用带边界的已知技术别名表和 NFKC/casefold 规范化；只检查明确的技术词。未知词不自动升级为事实，仍由最终人工验收覆盖。

## 7. “实质不同”判定风险

风险：精确去重抓不到换序或少量改写，过强相似度门禁又可能拒绝合理的同主题追问。

控制：先去除编号、标点和空白做规范化唯一性，再用保守的高相似度阈值拦截近复制。离线回归覆盖编号复制和小改写；真实质量仍需后续人工评分。

## 8. 失败分类风险

风险：provider 返回合法 Draft，但 assembler 拒绝后被误记为 provider error。

控制：增加专用 output-transform validation error，并在 Phase 2.1 分类器中映射为 schema failure；保留原 call trace、token usage 和重试计数。

## 9. 真实效果未知风险

本阶段不调用真实 provider，因此只能证明协议更小、调用边界正确、失败安全，不能证明真实成功率、token、延迟或问题质量改善。是否进入下一阶段必须由后续同模型、同参数、同样例的真实 A/B 决定。
