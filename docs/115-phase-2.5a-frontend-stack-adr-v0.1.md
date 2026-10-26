# ADR: Phase 2.5A Frontend Stack Selection v0.1

状态：`proposed_awaiting_user_confirmation`。本 ADR 不授权安装依赖或创建 `package.json`。

## 决策背景

产品是登录后使用的长流程 SaaS 工具，核心是表单、上传、异步 Agent 状态、题库筛选和评价历史。FastAPI 独立部署，当前没有服务端渲染、公开内容 SEO 或静态营销站需求。

评分为 1–5，5 表示更适合当前约束。“SSR/SEO 必要性”一项表示在不需要 SSR 时是否避免了额外复杂度。

| 维度 | React + TS + Vite | Next.js + TS | Vue + TS + Vite |
|---|---:|---:|---:|
| FastAPI 分离部署 | 5 | 3 | 5 |
| SPA 工作流 | 5 | 4 | 5 |
| OpenAPI 类型生成兼容 | 5 | 5 | 4 |
| Mock 工具生态 | 5 | 5 | 4 |
| 测试生态 | 5 | 5 | 4 |
| 表单/异步状态管理 | 5 | 5 | 5 |
| 无障碍支持 | 5 | 5 | 5 |
| 构建与部署复杂度 | 5 | 3 | 5 |
| 团队学习成本（当前未知） | 3 | 3 | 3 |
| 当前无需 SSR/SEO | 5 | 2 | 5 |
| **总分 / 50** | **48** | **40** | **45** |

## 推荐：React + TypeScript + Vite

推荐理由：

- 直接形成独立 SPA，与 FastAPI 分离部署和 Mock-first 工作方式匹配。
- OpenAPI 类型生成、Mock Service Worker、表单、异步缓存与无障碍测试生态成熟。
- 没有 SSR runtime 和 server/client component 边界，降低当前任务的部署与状态管理复杂度。
- 后续如果公开营销页产生 SEO 需求，可以独立建设，不必让面试准备应用承担 SSR 成本。

Phase 2.5B 的候选工具类别可包括 OpenAPI 类型生成器、路由、请求缓存、表单、Mock worker 和无障碍测试；具体包与版本必须在获得授权后再选择和安装。

## 备选一：Vue + TypeScript + Vite

适合希望使用模板语法和渐进式状态管理的团队，SPA 部署同样简单。当前排名第二，主要差异是本项目后续 OpenAPI/Mock/组件测试样例预计在 React 生态中更容易形成统一参考；如果团队 Vue 熟练度显著更高，应重新评估学习成本并可改选。

## 备选二：Next.js + TypeScript

只有在出现明确 SSR、SEO、服务端 BFF、流式服务端页面或同域部署需求时优先。当前业务均在登录后，且后端独立为 FastAPI；引入 Next.js 会增加部署与数据边界复杂度，而没有已证明的 SSR 收益。

## 决策门

推荐不等于选定。进入 Phase 2.5B 前，用户必须明确确认 React/Vite、Vue/Vite 或 Next.js 之一；在此之前不创建正式脚手架，不安装 npm 依赖。

