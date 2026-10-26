import { Link } from "react-router-dom";

import { EmptyState } from "@/components/Feedback";

export function NotFoundPage() {
  return (
    <EmptyState
      title="页面不存在"
      description="链接可能已失效，或资源地址输入有误。"
      action={<Link className="button-link" to="/">返回首页</Link>}
    />
  );
}
