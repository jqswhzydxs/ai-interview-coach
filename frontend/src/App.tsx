import { AppShell } from "@/components/AppShell";
import { ErrorBoundary } from "@/components/Feedback";
import { AppRoutes } from "@/routes/AppRoutes";

export function App() {
  return (
    <ErrorBoundary>
      <AppShell>
        <AppRoutes />
      </AppShell>
    </ErrorBoundary>
  );
}
