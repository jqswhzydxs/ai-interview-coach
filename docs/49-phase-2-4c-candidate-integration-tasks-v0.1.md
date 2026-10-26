# Phase 2.4C Candidate Integration Tasks

日期：2026-10-21。最终执行结果与证据见文档 51。

- [x] 新增最终决策：两个 metadata 冻结门禁通过、AI evaluator、仅 Candidate 集成资格、Token 门禁仍未解决。
- [x] 建立现有 297 个文件的保护哈希，包含用户已有改动和所有旧实验报告。
- [x] 新增独立 Candidate Agent，强制显式 v1/v2，初始化失败及版本不符安全终止。
- [x] 保留生产默认、原 Draft Agent、assembler v1/v2、Prompt、Schema、client 和 retry/fallback 文件。
- [x] 新增版本、资产/输入/输出哈希实验记录，区分 mock/fallback 未应用 metadata 的情况。
- [x] 新增冻结 replay/holdout 验证器，核对完整冻结题库、正文、ID、模块和顺序。
- [x] 新增版本选择、调用次数、注入失败、绑定漂移、fallback、安全 guard 和实验记录测试。
- [x] 专项测试通过：新增 23 项；包含既有安全回归的专项集合 104 项。
- [x] 全量离线测试通过：319 passed，1 项 real_llm 测试 deselected，包括 degraded evaluation 与长期记忆安全回归。
- [x] 迁移测试通过：3 passed。
- [x] compileall、git diff --check、socket guard 和保护文件哈希检查通过；297/297 既有保护文件不变。
- [x] 完成集成验证报告并停止，等待 Phase 2.4D 设计。
