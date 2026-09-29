import { useConfigStore, useRunStore } from '@/state';
import { usePermissionStore } from '@/state/permissionStore';

export function ValidationActions({ onRun }: { onRun?: () => void }) {
  const { validation, validating, validationError, validate, loading, signingIn } = useConfigStore();
  const { busy, requesting } = usePermissionStore();
  const phase = useRunStore((state) => state.phase);
  const disabled = validating || loading || signingIn || busy || requesting
    || !['idle', 'completed', 'failed', 'canceled'].includes(phase);
  return (
    <div className="row-between">
      <button type="button" className="btn" disabled={disabled} onClick={() => {
        if (validation && !window.confirm(
          'Re-run all validation checks from the beginning?\n\n' +
          'This replaces the current validation results and can take several minutes. ' +
          'Approved SQL queries may incur charges. Your configuration and saved snapshots are kept.\n\n' +
          'Choose Cancel to keep these results, then Continue to run to start the assessment instead.',
        )) return;
        void validate().catch(() => undefined);
      }}>
        {validating ? 'Validation running...' : validation ? 'Re-run validation' : validationError ? 'Retry validation' : 'Run validation'}
      </button>
      {onRun && <button type="button" className="btn btn-primary" onClick={onRun}
        disabled={disabled || !validation?.canRun || Boolean(validationError)}
        title={validation?.canRun && !validationError ? undefined : 'Complete full validation and resolve every blocker first.'}>
        Continue to run
      </button>}
    </div>
  );
}
