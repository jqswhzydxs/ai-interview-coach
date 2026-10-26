import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listEvaluations } from "@/api/client";
import { EmptyState, Skeleton } from "@/components/Feedback";

export function HistoryPage() {
  const query = useQuery({
    queryKey: ["evaluation-history"],
    queryFn: ({ signal }) => listEvaluations(signal),
  });
  if (query.isPending) return <Skeleton label="正在加载练习历史" />;
  if (query.isError || query.data.items.length === 0) {
    return (
      <EmptyState
        title="还没有练习记录"
        description="完成一道题的练习后，评价会显示在这里。"
        action={<Link className="button-link" to="/prep/new">创建准备任务</Link>}
      />
    );
  }
  return (
    <div className="page-stack">
      <h1>练习历史</h1>
      <ul>
        {query.data.items.map((item) => (
          <li key={item.answer_evaluation_id}>
            <Link to={`/evaluations/${item.answer_evaluation_id}`}>查看评价</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
