# Phase 2.4C Candidate Integration Plan

日期：2026-10-21。

1. 核对 AI evaluator、两项冻结 metadata 门禁和 Phase 2.4B Token 状态。新增独立最终决策，不回写历史结论。
2. 对开始工作时已有的 app/tests/scripts/docs/alembic、所有实验报告及项目配置建立 SHA-256 基线。保留已有未提交改动。
3. 新增独立 Candidate 类，版本必填，精确绑定 assembler；保留原生产/Draft/v1/v2 文件及共同 Provider/retry/fallback 实现。
4. 增加独立实验记录，哈希覆盖组装、规则、Prompt、Schema、基础执行与 client 文件；将 fallback 与实际应用 metadata 的运行明确区分。
5. 新增只能处理冻结语料的离线验证器，使用只读与 socket guard。在新目录记录 15 replay + 4 holdout 的 v1/v2 两次执行与哈希，比较完整冻结结果。
6. 增加专项测试：版本显式选择、生产路径、未知版本、注入失败、串用拒绝、调用次数与请求相同、fallback、绑定漂移、确定性、记录资产和只读/socket 防护。
7. 依次完成专项、全量离线、迁移、compileall、git diff --check；核对完整保护文件基线，形成集成验证报告。
8. 固定可复现 metadata 基线后停止。后续只等待 Phase 2.4D Token 单变量优化设计，不在本阶段试验 Token。

复现命令：

```powershell
.\.venv\Scripts\python.exe scripts/validate_question_bank_candidate_integration.py --output-dir <新的空实验目录>
.\.venv\Scripts\python.exe -m pytest tests/unit/test_question_bank_candidate_agent.py tests/integration/test_question_bank_candidate_integration.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest -m "not real_llm" -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest tests/integration/test_migrations.py -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m compileall -q app tests scripts
git -c safe.directory=D:/桌面/ai-interview-coach diff --check
```

git 使用命令级 safe.directory，仅绕过共享工作区的所有者差异，不修改全局配置。复现不能复用 run2、既有 metadata 报告目录或已有集成输出文件。
