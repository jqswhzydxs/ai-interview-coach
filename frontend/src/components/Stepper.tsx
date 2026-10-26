import { Check } from "lucide-react";

export interface StepDefinition {
  id: string;
  label: string;
  description?: string;
}

export function Stepper({
  steps,
  currentStepId,
  completedIds = [],
  onStepSelect,
}: {
  steps: StepDefinition[];
  currentStepId: string;
  completedIds?: string[];
  onStepSelect?: (stepId: string) => void;
}) {
  return (
    <nav aria-label="创建进度" className="stepper">
      <ol>
        {steps.map((step, index) => {
          const active = step.id === currentStepId;
          const complete = completedIds.includes(step.id);
          return (
            <li key={step.id} className={active ? "is-active" : complete ? "is-complete" : ""}>
              <button
                type="button"
                aria-current={active ? "step" : undefined}
                disabled={!onStepSelect || (!complete && !active)}
                onClick={() => onStepSelect?.(step.id)}
              >
                <span className="step-number" aria-hidden="true">
                  {complete ? <Check size={16} /> : index + 1}
                </span>
                <span>
                  <strong>{step.label}</strong>
                  {step.description ? <small>{step.description}</small> : null}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
