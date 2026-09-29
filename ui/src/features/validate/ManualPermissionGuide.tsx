import { useState } from 'react';
import { Callout } from '@/components';
import type { AssessmentConfig } from '@/types';
import type { PermissionSetup } from '@/api/backend';
import { manualPermissionCommands, VERIFY_PIPELINE_SQL } from './manualPermissionCommands';

function CommandBlock({ label, command }: { label: string; command: string }) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="stack-sm">
      <div className="row">
        <strong>{label}</strong>
        <button type="button" className="btn btn-sm" onClick={async () => {
          setCopied(false);
          setError(null);
          try {
            if (!navigator.clipboard?.writeText) throw new Error('Clipboard access is unavailable.');
            await navigator.clipboard.writeText(command);
            setCopied(true);
          } catch (cause) {
            setError(`${cause instanceof Error ? cause.message : 'Clipboard copy failed.'} Select and copy the displayed command manually.`);
          }
        }}>Copy {label}</button>
        {copied && <span role="status">Copied {label}. Nothing was executed.</span>}
      </div>
      {error && <span role="alert">{error}</span>}
      <pre aria-label={label} className="break-anywhere" style={{ whiteSpace: 'pre-wrap', maxHeight: '28rem', overflow: 'auto' }}>{command}</pre>
    </div>
  );
}

export function ManualPermissionGuide({ job, account, blocked }: {
  job: PermissionSetup | null;
  account: AssessmentConfig['databricks'];
  blocked: boolean;
}) {
  const knownAccess = job?.accessVerified || job?.status === 'awaiting_confirmation'
    || /PERMISSION_DENIED|INSUFFICIENT_PERMISSIONS|does not have MANAGE/i.test(`${job?.error ?? ''} ${job?.accessCheckError ?? ''}`);
  const commands = job?.principal && !blocked && job.status !== 'unknown' && knownAccess
    ? manualPermissionCommands(job, account) : null;
  return (
    <details>
      <summary>Manual permission repair commands</summary>
      <div className="stack">
        <p>Copy commands to run yourself, or send the SQL grants to an authorized administrator. Opening this guide and copying commands never execute SQL, change roles, or start validation.</p>
        {!commands ? <Callout tone="info" title="Verify the selected target first">
          {blocked || job?.status === 'unknown'
            ? 'Wait for active work to finish or resolve the unknown setup outcome before running manual changes.'
            : 'Use Check access and preview grants for the current workspace and warehouse to populate commands with its verified identity. Resolve missing-table, timeout, and other non-permission errors before considering grants.'}
        </Callout> : 'error' in commands ? <Callout tone="danger" title="Commands unavailable">{commands.error}</Callout> : job && <>
          <p className="break-anywhere">Target: {job.workspaceName} ({job.workspaceUrl}). Grant recipient: {job.principal}.</p>
          {job.accessVerified && <Callout tone="info" title="Reference only - access already works">No permission changes are needed for this target. These commands remain available for reference; do not run the administrator-assignment step just because it is shown.</Callout>}
          <h4>1. Choose an authorized administrator</h4>
          <p>Prefer an existing administrator with authority over system. Running SQL as the same unprivileged user, being an Azure Owner, or being a workspace admin does not add grant authority.</p>
          <details>
            <summary>Optional: resolve missing MANAGE with an Account Admin</summary>
            <Callout tone="warn" title="Broad, persistent administrator assignment">
              Use this only when an authorized Account Admin must establish a metastore administrator.
              It assigns the verified assessment identity, not a group, and affects every catalog and
              workspace attached to that metastore. The role remains assigned; there is no automatic
              rollback. Prefer your organization&apos;s designated administrator group through the account
              console for ongoing administration. Do not replace an existing administrator.
            </Callout>
            <p>Run in PowerShell 7 with Azure CLI installed and signed into the verified account using az login.
              The script reads the selected workspace&apos;s current metastore and account role, displays the owner,
              and requires you to type the metastore ID before its single PUT request. Tokens stay in memory.
              If a request fails after submission, inspect the account console before retrying.</p>
            {commands.powershell
              ? <CommandBlock label="administrator PowerShell" command={commands.powershell} />
              : <Callout tone="warn" title="Account settings required">{commands.adminIssue}</Callout>}
          </details>
          <h4>2. Apply only the required read grants</h4>
          <p>Run in the selected workspace&apos;s Databricks SQL Editor as the authorized administrator, granting access
            to the recipient below. Run each statement once; if one fails, stop and inspect the result.
            Grants can affect other workspaces sharing this metastore. Do not grant MANAGE or ALL PRIVILEGES to collect evidence.</p>
          <CommandBlock label="SQL grants" command={commands.sql} />
          <h4>3. Verify as the assessment identity</h4>
          <p>Switch back to the assessment identity and run this in the selected workspace. Warehouse queries can incur DBU charges.
            A successful SELECT returning zero rows still proves access. An administrator&apos;s successful query does not prove the recipient&apos;s access.</p>
          <CommandBlock label="verification SQL" command={VERIFY_PIPELINE_SQL} />
          <p>Return here and select Check access and preview grants. After a permission change, explicitly re-run full validation, then Continue to run.
            Historical setup failures are not rewritten when you repair permissions outside the app.</p>
          <a href="https://learn.microsoft.com/en-us/azure/databricks/data-governance/unity-catalog/manage-privileges/admin-privileges#assign-a-metastore-admin" target="_blank" rel="noreferrer">Microsoft guidance: assign a metastore administrator</a>
        </>}
      </div>
    </details>
  );
}
