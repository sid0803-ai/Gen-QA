import type { ExecutionType, ScenarioCategory, Severity, TestingLevel } from './types';

/** Shared label/color vocabulary for the fields common to Test Design scenarios and Test Cases. */

export const CATEGORY_LABELS: Record<ScenarioCategory, string> = {
  positive: 'Positive',
  negative: 'Negative',
  boundary: 'Boundary',
  edge_case: 'Edge Case',
  business_logic: 'Business Logic',
  validation: 'Validation',
  security: 'Security',
  performance: 'Performance',
  regression: 'Regression',
};

export const CATEGORY_COLORS: Record<ScenarioCategory, string> = {
  positive: 'green',
  negative: 'red',
  boundary: 'purple',
  edge_case: 'geekblue',
  business_logic: 'cyan',
  validation: 'blue',
  security: 'magenta',
  performance: 'orange',
  regression: 'gold',
};

export const CATEGORY_OPTIONS = (Object.keys(CATEGORY_LABELS) as ScenarioCategory[]).map((value) => ({
  value,
  label: CATEGORY_LABELS[value],
}));

export const TESTING_LEVEL_LABELS: Record<TestingLevel, string> = {
  functional: 'Functional',
  api: 'API',
  ui: 'UI',
  integration: 'Integration',
  security: 'Security',
  performance: 'Performance',
  regression: 'Regression',
};

export const TESTING_LEVEL_OPTIONS = (Object.keys(TESTING_LEVEL_LABELS) as TestingLevel[]).map(
  (value) => ({ value, label: TESTING_LEVEL_LABELS[value] }),
);

export const SEVERITY_LABELS: Record<Severity, string> = {
  minor: 'Minor',
  major: 'Major',
  critical: 'Critical',
  blocker: 'Blocker',
};

export const SEVERITY_COLORS: Record<Severity, string> = {
  minor: 'blue',
  major: 'gold',
  critical: 'volcano',
  blocker: 'red',
};

export const SEVERITY_OPTIONS = (Object.keys(SEVERITY_LABELS) as Severity[]).map((value) => ({
  value,
  label: SEVERITY_LABELS[value],
}));

export const EXECUTION_TYPE_LABELS: Record<ExecutionType, string> = {
  manual: 'Manual',
  automation: 'Automation',
  hybrid: 'Hybrid',
};

export const EXECUTION_TYPE_OPTIONS = (Object.keys(EXECUTION_TYPE_LABELS) as ExecutionType[]).map(
  (value) => ({ value, label: EXECUTION_TYPE_LABELS[value] }),
);
