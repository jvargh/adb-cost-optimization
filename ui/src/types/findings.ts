/**
 * Finding and evidence contract. Mirrors `optimization-candidates.json`
 * produced by `assessment/detectors/catalog.py`.
 *
 * Invariants the UI must never break:
 *  - `humanValidationRequired` is always true.
 *  - `estimatedSavings` is null unless the backend supplied a value; the UI
 *    renders "Not estimated" and never infers a number.
 *  - `insufficient_evidence` is a first-class outcome, not a hidden failure.
 */

export type ConfidenceLevel = 'high' | 'medium' | 'low';

export type FindingStatus = 'candidate' | 'insufficient_evidence';

/** Category values emitted by `assessment/detectors/catalog.py`. */
export type FindingCategory =
  | 'choose-optimal-resources'
  | 'dynamically-allocate-resources'
  | 'monitor-and-control-cost'
  | 'design-cost-effective-workloads';

export const FINDING_CATEGORY_LABELS: Record<FindingCategory, string> = {
  'choose-optimal-resources': 'Choose optimal resources',
  'dynamically-allocate-resources': 'Dynamically allocate resources',
  'monitor-and-control-cost': 'Monitor and control cost',
  'design-cost-effective-workloads': 'Design cost-effective workloads',
};

/** Detector identifiers implemented in the backend catalog. */
export const DETECTOR_IDS = [
  'OPT-INTERACTIVE-AUTOTERMINATION',
  'OPT-JOB-COMPUTE',
  'DYN-AUTOSCALING',
  'MON-UNOWNED-COST',
  'MON-MISSING-BUDGET',
  'WRK-JOB-COMPUTE',
  'WRK-DRIVER-ON-SPOT',
] as const;

export type DetectorId = (typeof DETECTOR_IDS)[number];

export interface QualityMetrics {
  completeness: number;
  coverage: number;
  sourceAuthority: number;
  freshness?: number;
  consistency?: number;
  sampleAdequacy?: number;
  attributionQuality?: number;
  collectionSuccess?: number;
}

export interface Confidence {
  level: ConfidenceLevel;
  score: number;
  metrics: QualityMetrics;
  missingRequiredMetrics: string[];
}

/** Free-form evidence record emitted by a detector. */
export type EvidenceRecord = Record<string, string | number | boolean | null>;

export interface Finding {
  schemaVersion: string;
  detectorId: string;
  title: string;
  category: FindingCategory;
  status: FindingStatus;
  explanation: string;
  recommendedAction: string;
  confidence: Confidence;
  evidence: EvidenceRecord[];
  limitations: string[];
  humanValidationRequired: true;
  estimatedSavings: number | null;
  savingsCurrency: string | null;
  /** UI-only attribution so findings can be filtered by estate dimension. */
  scope: FindingScope;
  /** Relative paths into the run directory that back this finding. */
  evidenceFiles: string[];
}

export interface FindingScope {
  subscriptionId: string | null;
  resourceGroup: string | null;
  workspaceName: string | null;
  workload: string | null;
}

export interface OptimizationCandidates {
  schemaVersion: string;
  analysisWindow: { startUtc: string; endUtc: string; timeZone: string };
  candidateCount: number;
  insufficientEvidenceCount: number;
  findings: Finding[];
}

/** Human sign-off register backing the Review screen and the CSV export. */
export type ReviewDecision = 'pending' | 'accepted' | 'rejected' | 'deferred';

export interface ReviewEntry {
  findingId: string;
  finding: string;
  evidenceLinks: string[];
  reviewer: string;
  role: string;
  reviewedAtUtc: string | null;
  decision: ReviewDecision;
  businessSlaContext: string;
  performanceReliabilityRisk: string;
  securityGovernanceImpact: string;
  validationExperiment: string;
  ownerApprover: string;
  rationale: string;
}
