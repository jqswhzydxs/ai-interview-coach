import { ArrowRight, ClipboardList, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

export function HomePage() {
  return (
    <div className="page-stack">
      <section className="hero-panel">
        <p className="eyebrow">Mock-first · 合同驱动</p>
        <h1>把面试准备拆成可执行的练习</h1>
        <p>
          录入简历与职位要求，生成结构化题库，并在每次评价中清楚了解来源质量和降级状态。
        </p>
        <Link className="button-link" to="/prep/new">
          创建准备任务 <ArrowRight aria-hidden="true" size={18} />
        </Link>
      </section>
      <section aria-labelledby="home-capabilities">
        <h2 id="home-capabilities">当前脚手架覆盖</h2>
        <div className="card-grid">
          <article className="info-card">
            <ClipboardList aria-hidden="true" />
            <h3>8/8/9 题库</h3>
            <p>按模块浏览，并保留后端稳定 ID 与顺序。</p>
          </article>
          <article className="info-card">
            <ShieldCheck aria-hidden="true" />
            <h3>可信状态</h3>
            <p>标准、降级与 fallback 状态使用明确文字和恢复动作。</p>
          </article>
        </div>
      </section>
    </div>
  );
}
