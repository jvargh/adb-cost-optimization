import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { WorkflowNextStep } from '@/components';

describe('workflow next step', () => {
  it('shows the next action and runs it', () => {
    const onAction = vi.fn();
    render(
      <WorkflowNextStep
        title="Review the assessment results"
        detail="Open the dashboards and findings."
        actionLabel="Visualize results"
        onAction={onAction}
      />,
    );

    expect(screen.getByText('Next step')).toBeInTheDocument();
    expect(screen.getByText('Review the assessment results')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Visualize results' }));
    expect(onAction).toHaveBeenCalledOnce();
  });
});
