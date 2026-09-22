// Types mirroring the backend API contract exactly (see project spec).
// Do not add fields the backend doesn't send; do not rename fields.

export type Role = 'admin' | 'member' | 'viewer';

export interface User {
  id: string;
  email: string;
  full_name: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}

/** Shape returned by GET /projects — includes the current user's role. */
export interface ProjectWithRole extends Project {
  role: Role;
}

export interface ProjectCreateInput {
  name: string;
  description?: string;
}

export interface ProjectUpdateInput {
  name?: string;
  description?: string;
}

export interface ProjectMember {
  user_id: string;
  email: string;
  full_name: string;
  role: Role;
}

export interface AddMemberInput {
  email: string;
  role: Role;
}

export type Priority = 'low' | 'medium' | 'high' | 'critical';

export type AnalysisStatus = 'draft' | 'approved' | 'rejected';

/** Analysis status as surfaced on a requirement list row — includes "none". */
export type LatestAnalysisStatus = 'none' | AnalysisStatus;

export type FeasibilityStatus = 'draft' | 'approved' | 'rejected';
/** Feasibility status as surfaced on a requirement row — includes "none". */
export type LatestFeasibilityStatus = 'none' | FeasibilityStatus;

export type StrategyStatus = 'draft' | 'approved' | 'rejected';
/** Test strategy status as surfaced on a requirement row — includes "none". */
export type LatestStrategyStatus = 'none' | StrategyStatus;

export interface Requirement {
  id: string;
  project_id: string;
  title: string;
  description: string;
  business_objective: string | null;
  acceptance_criteria: string | null;
  priority: Priority;
  created_by: string;
  created_at: string;
  updated_at: string;
  latest_analysis_status: LatestAnalysisStatus;
  latest_feasibility_status: LatestFeasibilityStatus;
  latest_strategy_status: LatestStrategyStatus;
}

/** Shape returned by GET /projects/{id}/requirements (list form, no description). */
export interface RequirementSummary {
  id: string;
  title: string;
  priority: Priority;
  latest_analysis_status: LatestAnalysisStatus;
  latest_feasibility_status: LatestFeasibilityStatus;
  latest_strategy_status: LatestStrategyStatus;
  created_at: string;
}

export interface RequirementCreateInput {
  title: string;
  description: string;
  business_objective?: string;
  acceptance_criteria?: string;
  priority?: Priority;
}

export interface RequirementUpdateInput {
  title?: string;
  description?: string;
  business_objective?: string;
  acceptance_criteria?: string;
  priority?: Priority;
}

export interface RationaleItem {
  statement: string;
  rationale: string;
}

export interface RiskItem {
  statement: string;
  rationale: string;
  severity: 'low' | 'medium' | 'high';
}

export interface AmbiguityItem {
  statement: string;
  clarifying_question: string;
}

export interface RequirementAnalysisPayload {
  summary: string;
  business_rules: RationaleItem[];
  functional_conditions: RationaleItem[];
  risks: RiskItem[];
  ambiguities: AmbiguityItem[];
  missing_information: string[];
  edge_cases: RationaleItem[];
  automation_candidates: RationaleItem[];
  manual_candidates: RationaleItem[];
}

/** Shape returned by the analyses list endpoint — omits `payload`. */
export interface Analysis {
  id: string;
  requirement_id: string;
  status: AnalysisStatus;
  created_by: string;
  created_at: string;
  approved_by: string | null;
  approved_at: string | null;
  updated_at: string;
}

/** Shape returned by create/get-one/patch/approve/reject — includes `payload`. */
export interface AnalysisDetail extends Analysis {
  payload: RequirementAnalysisPayload;
}

export type FeasibilityRecommendation = 'automate' | 'manual' | 'hybrid' | 'needs_review';

export interface FeasibilityScenario {
  title: string;
  description: string;
  recommendation: FeasibilityRecommendation;
  reason: string;
  overridden_recommendation: FeasibilityRecommendation | null;
}

export interface FeasibilityStudyPayload {
  summary: string;
  scenarios: FeasibilityScenario[];
}

/** Shape returned by the feasibility list endpoint — omits `payload`. */
export interface Feasibility {
  id: string;
  requirement_id: string;
  status: FeasibilityStatus;
  created_by: string;
  created_at: string;
  approved_by: string | null;
  approved_at: string | null;
  updated_at: string;
}

/** Shape returned by create/get-one/patch/approve/reject — includes `payload`. */
export interface FeasibilityDetail extends Feasibility {
  payload: FeasibilityStudyPayload;
}

export type TestingLevel =
  | 'functional'
  | 'api'
  | 'ui'
  | 'integration'
  | 'security'
  | 'performance'
  | 'regression';

export interface TestingLevelScope {
  level: TestingLevel;
  applicable: boolean;
  estimated_scenario_count: number;
  notes: string;
}

export interface TestStrategyPayload {
  summary: string;
  levels: TestingLevelScope[];
  environments: string[];
  test_data_requirements: string[];
  dependencies: string[];
  automation_scope_notes: string;
  manual_scope_notes: string;
}

/** Shape returned by the test strategy list endpoint — omits `payload`. */
export interface Strategy {
  id: string;
  requirement_id: string;
  status: StrategyStatus;
  created_by: string;
  created_at: string;
  approved_by: string | null;
  approved_at: string | null;
  updated_at: string;
}

/** Shape returned by create/get-one/patch/approve/reject — includes `payload`. */
export interface StrategyDetail extends Strategy {
  payload: TestStrategyPayload;
}
