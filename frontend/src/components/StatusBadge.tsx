import { Tag } from 'antd';

/**
 * Small status/role badge, wrapping antd's Tag with a shared color+label
 * vocabulary. Today it's only used for project member roles (admin/member/
 * viewer), but the pattern is meant to be reused for AI-approval-style
 * statuses (draft/pending/approved/rejected/...) in later sprints — extend
 * the maps below rather than introducing a second badge component.
 */
const STATUS_COLORS: Record<string, string> = {
  // roles
  admin: 'purple',
  member: 'blue',
  viewer: 'default',
  // generic review/approval statuses (future sprints)
  none: 'default',
  draft: 'default',
  pending: 'gold',
  in_review: 'gold',
  approved: 'green',
  rejected: 'red',
  passed: 'green',
  failed: 'red',
  blocked: 'orange',
  skipped: 'default',
  running: 'blue',
  error: 'red',
  // requirement priority
  low: 'blue',
  medium: 'gold',
  high: 'orange',
  critical: 'red',
};

const STATUS_LABELS: Record<string, string> = {
  admin: 'Admin',
  member: 'Member',
  viewer: 'Viewer',
  none: 'No analysis',
  draft: 'Draft',
  pending: 'Pending',
  in_review: 'In review',
  approved: 'Approved',
  rejected: 'Rejected',
  passed: 'Passed',
  failed: 'Failed',
  blocked: 'Blocked',
  skipped: 'Skipped',
  running: 'Running',
  error: 'Error',
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
};

export interface StatusBadgeProps {
  status: string;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const key = status.toLowerCase();
  const color = STATUS_COLORS[key] ?? 'default';
  const label = STATUS_LABELS[key] ?? status;
  return <Tag color={color}>{label}</Tag>;
}
