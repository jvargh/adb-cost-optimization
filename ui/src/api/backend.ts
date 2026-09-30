import type {
  AssessmentConfig,
  AssessmentResults,
  RunSummary,
  SubscriptionOption,
  ValidationReport,
  ValidationProgress,
  RunPhase,
  CollectionSource,
  WorkspaceSelection,
} from '@/types';

/**
 * The single seam between the UI and the assessment backend.
 *
 * Phase 1 (mock) implements this with fixtures. Phase 2 implements it with a
 * thin local HTTP shim that shells out to `assessment/Invoke-Assessment.ps1`.
 * The UI never reimplements assessment logic — it only orchestrates and
 * visualizes.
 */
export interface AssessmentBackend {
  capabilityOperation<T>(runId: string | null, action: string, input: object): Promise<T>;
  readonly id: string;
  readonly isMock: boolean;

  /** Discover subscriptions/resource groups/workspaces for the Configure pickers. */
  discoverEstate(): Promise<SubscriptionOption[]>;

  /** Launch the local Azure CLI browser sign-in flow. */
  signIn(tenantId: string): Promise<void>;

  /** Load the default scope config (local -> workshop -> example precedence). */
  loadDefaultConfig(): Promise<AssessmentConfig>;

  previewPermissionSetup(workspace: WorkspaceSelection, approved: boolean): Promise<PermissionSetup>;
  getPermissionSetup(setupId: string): Promise<PermissionSetup>;
  applyPermissionSetup(setupId: string, principal: string, approved: boolean): Promise<PermissionSetup>;

  /** Runs read-only source readiness and reports actual completed checks. */
  validate(
    config: AssessmentConfig,
    approvals: RunApprovals,
    onProgress?: (progress: ValidationProgress) => void,
  ): Promise<ValidationReport>;

  /** Equivalent to `-Action Run`. Returns a handle that streams progress. */
  startRun(config: AssessmentConfig, approvals: RunApprovals): Promise<RunHandle>;

  /** List persisted runs under the output root. */
  listRuns(): Promise<RunSummary[]>;

  /** Permanently remove only the explicitly confirmed saved run directories. */
  deleteSnapshots(runIds: string[]): Promise<SnapshotDeletion>;

  /** Load every artifact the Visualize Results area binds to. */
  loadResults(runId: string): Promise<AssessmentResults>;

  /** Persist review decisions without regenerating the run's reports. */
  saveReview(runId: string, entries: AssessmentResults['review']): Promise<void>;

  /** Resolve the bytes of an export artifact for download. */
  readArtifact(runId: string, relativePath: string): Promise<ArtifactPayload>;
}

export interface SnapshotDeletion {
  deletedRunIds: string[];
  failures: { runId: string; message: string }[];
}

export interface PermissionSetup {
  setupId: string;
  status: 'verifying' | 'awaiting_confirmation' | 'applying' | 'completed' | 'failed' | 'unknown';
  workspaceId: string;
  workspaceName: string;
  workspaceUrl: string;
  warehouseId: string;
  principal: string | null;
  grants: { statement: string; status: 'not_attempted' | 'submitted' | 'applied' | 'failed' }[];
  error: string | null;
  accessVerified: boolean;
  accessCheckError?: string | null;
  expiresAtUtc: string | null;
  createdAtUtc: string;
}

export class BackendRequestError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
    this.name = 'BackendRequestError';
  }
}

export interface RunApprovals {
  /** Maps to `-ApproveSqlWarehouseAutoStart`. */
  approveSqlWarehouseAutoStart: boolean;
  /** Maps to `-ContinueOnCollectorError` (default) vs `-FailOnCollectorError`. */
  continueOnCollectorError: boolean;
  /** Retained for adapter compatibility; read-only behavior is intrinsic and does not require approval. */
  acknowledgedReadOnly: boolean;
}

export interface ArtifactPayload {
  encoding?: 'base64';
  relativePath: string;
  mimeType: string;
  content: string;
}

export type RunEvent =
  | { type: 'phase'; phase: RunPhase; message: string; atUtc: string }
  | { type: 'log'; level: 'info' | 'warn' | 'error'; message: string; atUtc: string }
  | { type: 'source'; source: CollectionSource; atUtc: string }
  | { type: 'completed'; runId: string; atUtc: string }
  | { type: 'failed'; message: string; atUtc: string }
  | { type: 'canceled'; atUtc: string };

export interface RunHandle {
  runId: string;
  /** Async iterable of progress events. Consumed by the Monitor view. */
  subscribe(listener: (event: RunEvent) => void): () => void;
  /**
   * Requests cancellation. Note: the current backend has no whole-run
   * cancellation checkpoint, so Phase 2 must terminate the child process and
   * mark the partial run explicitly rather than claiming a clean stop.
   */
  cancel(): Promise<void>;
}
