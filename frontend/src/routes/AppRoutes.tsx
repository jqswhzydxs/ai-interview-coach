import { Route, Routes } from "react-router-dom";

import { AgentRunPage } from "@/pages/AgentRunPage";
import { EvaluationPage } from "@/pages/EvaluationPage";
import { HistoryPage } from "@/pages/HistoryPage";
import { HomePage } from "@/pages/HomePage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { PracticePage } from "@/pages/PracticePage";
import { PrepNewPage } from "@/pages/PrepNewPage";
import { ProcessingPage } from "@/pages/ProcessingPage";
import { QuestionsPage } from "@/pages/QuestionsPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/prep/new" element={<PrepNewPage />} />
      <Route path="/prep/:prepPackageId/processing" element={<ProcessingPage />} />
      <Route path="/prep/:prepPackageId/questions" element={<QuestionsPage />} />
      <Route path="/questions/:questionId/practice" element={<PracticePage />} />
      <Route path="/evaluations/:evaluationId" element={<EvaluationPage />} />
      <Route path="/history" element={<HistoryPage />} />
      <Route path="/agent-runs/:agentRunId" element={<AgentRunPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
