// Shared status color/icon mapping for reporting charts (dashboard trend +
// breakdown bars). Colors come from the dataviz skill's fixed, never-themed
// status palette (references/palette.md): good/warning/serious/critical.
// Execution statuses map onto those four roles one-to-one except `skipped`,
// which isn't a pass/fail outcome at all — it's given the neutral/muted ink
// so it reads as "opted out", not as another severity level. Per the skill's
// status-color rule, these are never used as color alone: every legend/axis
// entry pairs the swatch with an icon + text label.
import type { ExecutionStatus } from '../api/types';

export type ChartableStatus = Extract<
  ExecutionStatus,
  'passed' | 'failed' | 'blocked' | 'skipped' | 'error'
>;

export const CHARTABLE_STATUSES: ChartableStatus[] = [
  'passed',
  'failed',
  'blocked',
  'skipped',
  'error',
];

export const STATUS_COLOR: Record<ChartableStatus, string> = {
  passed: '#0ca30c', // status: good
  failed: '#d03b3b', // status: critical
  blocked: '#fab219', // status: warning
  error: '#ec835a', // status: serious
  skipped: '#898781', // muted ink — not a severity, an opt-out
};

export const STATUS_LABEL: Record<ChartableStatus, string> = {
  passed: 'Passed',
  failed: 'Failed',
  blocked: 'Blocked',
  skipped: 'Skipped',
  error: 'Error',
};

// Chart chrome tokens, light mode only (the app has no dark-mode toggle yet).
export const CHART_CHROME = {
  surface: '#fcfcfb',
  textPrimary: '#0b0b0b',
  textSecondary: '#52514e',
  textMuted: '#898781',
  gridline: '#e1e0d9',
  baseline: '#c3c2b7',
};
