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

export type TestDesignStatus = 'draft' | 'approved' | 'rejected';
/** Test design status as surfaced on a requirement row — includes "none". */
export type LatestTestDesignStatus = 'none' | TestDesignStatus;

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
  latest_test_design_status: LatestTestDesignStatus;
}

/** Shape returned by GET /projects/{id}/requirements (list form, no description). */
export interface RequirementSummary {
  id: string;
  title: string;
  priority: Priority;
  latest_analysis_status: LatestAnalysisStatus;
  latest_feasibility_status: LatestFeasibilityStatus;
  latest_strategy_status: LatestStrategyStatus;
  latest_test_design_status: LatestTestDesignStatus;
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

export type ScenarioCategory =
  | 'positive'
  | 'negative'
  | 'boundary'
  | 'edge_case'
  | 'business_logic'
  | 'validation'
  | 'security'
  | 'performance'
  | 'regression';

export type Severity = 'minor' | 'major' | 'critical' | 'blocker';

export type TestDesignScope = 'api' | 'ui' | 'both';

export interface TestDesignScenario {
  title: string;
  category: ScenarioCategory;
  testing_level: TestingLevel;
  priority: Priority;
  severity: Severity;
  preconditions: string;
  test_data: string;
  steps: string[];
  expected_result: string;
  business_rule: string;
  automation_candidate: boolean;
  /** Whether this scenario should be promoted into a real Test Case on approve. */
  include: boolean;
}

export interface TestDesignPayload {
  summary: string;
  scope: TestDesignScope;
  scenarios: TestDesignScenario[];
}

/** Shape returned by the test design list endpoint — omits `payload`. */
export interface TestDesign {
  id: string;
  requirement_id: string;
  status: TestDesignStatus;
  created_by: string;
  created_at: string;
  approved_by: string | null;
  approved_at: string | null;
  updated_at: string;
}

/** Shape returned by create/get-one/patch/approve/reject — includes `payload`. */
export interface TestDesignDetail extends TestDesign {
  payload: TestDesignPayload;
  /**
   * The approve endpoint promotes included scenarios into real Test Cases
   * server-side. The contract says the response "may include a count/list
   * of created test case ids" without committing to an exact shape — both
   * are optional here and neither is depended on beyond a friendly success
   * message (see `handleTestDesignApproveSuccess` in RequirementDetailPage).
   */
  created_test_case_ids?: string[];
  created_test_case_count?: number;
}

export type TestCaseStatus = 'draft' | 'approved';
export type TestCaseSource = 'ai' | 'human';
export type ExecutionType = 'manual' | 'automation' | 'hybrid';

/** Shape returned by GET /projects/{id}/test-cases (list form). */
export interface TestCaseSummary {
  id: string;
  code: string;
  title: string;
  testing_level: TestingLevel;
  category: ScenarioCategory;
  priority: Priority;
  severity: Severity;
  status: TestCaseStatus;
  source: TestCaseSource;
  automation_candidate: boolean;
  execution_type: ExecutionType;
  requirement_id: string;
  requirement_title: string;
  tags: string[];
  created_at: string;
}

/** Shape returned by get-one/patch/approve — full detail. */
export interface TestCase extends TestCaseSummary {
  preconditions: string;
  test_data: string;
  steps: string[];
  expected_result: string;
  business_rule: string;
  created_by: string;
  updated_at: string;
}

export interface TestCaseCreateInput {
  requirement_id: string;
  title: string;
  category: ScenarioCategory;
  testing_level: TestingLevel;
  priority: Priority;
  severity: Severity;
  preconditions: string;
  test_data: string;
  steps: string[];
  expected_result: string;
  business_rule: string;
  automation_candidate: boolean;
  execution_type: ExecutionType;
  tags: string[];
}

export type TestCaseUpdateInput = Partial<TestCaseCreateInput>;

export interface TestCaseListParams {
  requirement_id?: string;
  testing_level?: TestingLevel;
  category?: ScenarioCategory;
  priority?: Priority;
  status?: TestCaseStatus;
  automation_candidate?: boolean;
  search?: string;
}

export interface TestCaseVersion {
  version_number: number;
  /** Field values as of this version. Shape mirrors `TestCase` but is kept loose since the contract doesn't pin it down further. */
  snapshot: Partial<TestCase>;
  edited_by: string;
  edited_at: string;
}

// --- Environments ---

export interface Environment {
  id: string;
  project_id: string;
  name: string;
  base_url: string;
  variables: Record<string, string>;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface EnvironmentCreateInput {
  name: string;
  base_url: string;
  variables?: Record<string, string>;
}

export type EnvironmentUpdateInput = Partial<EnvironmentCreateInput>;

// --- Automation Script ---

export type AutomationScriptStatus = 'draft' | 'approved';
export type ScriptSource = 'ai' | 'human';

export interface ScriptVersion {
  version_number: number;
  code: string;
  source: ScriptSource;
  created_by: string;
  created_at: string;
}

/** Shape returned by GET /automation-script/versions — summary only, no `code`. */
export interface ScriptVersionSummary {
  version_number: number;
  source: ScriptSource;
  created_by: string;
  created_at: string;
}

export interface AutomationScript {
  id: string;
  test_case_id: string;
  status: AutomationScriptStatus;
  current_version: ScriptVersion;
  created_at: string;
  updated_at: string;
}

export interface AutomationScriptGenerateInput {
  environment_id?: string;
}

export interface AutomationScriptUpdateInput {
  code: string;
}

// --- Executions ---

/** Distinguishes how an execution was run — separate concept from a test case's own `execution_type` field. */
export type ExecutionRunType = 'manual' | 'automated';

export type ExecutionStatus =
  | 'pending'
  | 'running'
  | 'passed'
  | 'failed'
  | 'blocked'
  | 'skipped'
  | 'error';

export const TERMINAL_EXECUTION_STATUSES: ExecutionStatus[] = [
  'passed',
  'failed',
  'blocked',
  'skipped',
  'error',
];

export type ManualExecutionResultStatus = 'passed' | 'failed' | 'blocked' | 'skipped';

export interface Execution {
  id: string;
  project_id: string;
  test_case_id: string;
  environment_id: string;
  type: ExecutionRunType;
  status: ExecutionStatus;
  triggered_by: string;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  actual_result: string | null;
  comments: string | null;
  logs: string | null;
  error_message: string | null;
  created_at: string;
}

export type ExecutionCreateInput =
  | {
      test_case_id: string;
      environment_id: string;
      type: 'manual';
      status: ManualExecutionResultStatus;
      actual_result?: string;
      comments?: string;
    }
  | {
      test_case_id: string;
      environment_id: string;
      type: 'automated';
    };

export interface ExecutionListParams {
  test_case_id?: string;
  status?: ExecutionStatus;
  type?: ExecutionRunType;
  environment_id?: string;
}
