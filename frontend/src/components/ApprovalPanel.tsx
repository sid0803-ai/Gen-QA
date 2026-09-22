import type { ReactNode } from 'react';
import { Button, Space, Typography } from 'antd';
import { StatusBadge } from './StatusBadge';

export interface ApprovalPanelProps {
  /** Generic draft/approved/rejected (or any StatusBadge-known key). */
  status: string;
  createdAt: string;
  createdByLabel?: string;
  approvedAt?: string | null;
  approvedByLabel?: string | null;
  /** Current viewer may edit the payload (member/admin, and status is still draft). */
  canEdit: boolean;
  /** Current viewer may approve/reject (member/admin, and status is still draft). */
  canReview: boolean;
  isDirty?: boolean;
  saving?: boolean;
  approving?: boolean;
  rejecting?: boolean;
  onSave?: () => void;
  onApprove?: () => void;
  onReject?: () => void;
  /** The rendered payload body — editable or read-only, supplied by the caller. */
  children: ReactNode;
}

/**
 * Generic "AI suggests -> human reviews -> approves" chrome: status badge,
 * who/when metadata, and Save/Approve/Reject actions while a draft is still
 * pending review. Deliberately payload-agnostic (the structured content is
 * passed as `children`) so later sprints (feasibility, strategy, scenarios)
 * can reuse it for their own draft/approve/reject payloads.
 */
export function ApprovalPanel({
  status,
  createdAt,
  createdByLabel,
  approvedAt,
  approvedByLabel,
  canEdit,
  canReview,
  isDirty,
  saving,
  approving,
  rejecting,
  onSave,
  onApprove,
  onReject,
  children,
}: ApprovalPanelProps) {
  const isDraft = status === 'draft';

  return (
    <div>
      <Space
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 16,
        }}
        wrap
      >
        <Space direction="vertical" size={2}>
          <StatusBadge status={status} />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            Created {new Date(createdAt).toLocaleString()}
            {createdByLabel ? ` by ${createdByLabel}` : ''}
          </Typography.Text>
          {approvedAt && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {status === 'approved' ? 'Approved' : 'Reviewed'} {new Date(approvedAt).toLocaleString()}
              {approvedByLabel ? ` by ${approvedByLabel}` : ''}
            </Typography.Text>
          )}
        </Space>
        {isDraft && (canEdit || canReview) && (
          <Space>
            {canEdit && (
              <Button onClick={onSave} disabled={!isDirty} loading={saving}>
                Save changes
              </Button>
            )}
            {canReview && (
              <>
                <Button type="primary" onClick={onApprove} loading={approving} disabled={rejecting}>
                  Approve
                </Button>
                <Button danger onClick={onReject} loading={rejecting} disabled={approving}>
                  Reject
                </Button>
              </>
            )}
          </Space>
        )}
      </Space>
      {children}
    </div>
  );
}
