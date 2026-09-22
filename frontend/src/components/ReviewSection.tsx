import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { App as AntApp, Button, Card, Collapse, Empty, Skeleton, Space, Typography } from 'antd';
import { StatusBadge } from './StatusBadge';
import { ApprovalPanel } from './ApprovalPanel';
import { ApiError } from '../api/client';

const { Title, Text } = Typography;

/** Minimal shape every "AI suggests -> human reviews -> approves" list-row shares. */
export interface ReviewItem {
  id: string;
  status: string;
  created_at: string;
  approved_at?: string | null;
}

type ReviewDetailHook<TDetail> = (
  id: string | undefined,
  options?: { enabled?: boolean },
) => { data: TDetail | undefined; isLoading: boolean };

type ReviewMutationHook<TDetail, TArg = void> = (id: string | undefined) => {
  mutateAsync: (arg: TArg) => Promise<TDetail>;
  isPending: boolean;
};

interface PayloadRenderer<TPayload> {
  (payload: TPayload, editable: boolean, onChange: (payload: TPayload) => void): ReactNode;
}

/** The most recent item: fully editable while draft, with approve/reject. */
function CurrentReviewPanel<TPayload, TDetail extends ReviewItem & { payload: TPayload }>({
  item,
  canReview,
  useDetail,
  useUpdate,
  useApprove,
  useReject,
  renderPayload,
  itemName,
  onApproveSuccess,
}: {
  item: ReviewItem;
  canReview: boolean;
  useDetail: ReviewDetailHook<TDetail>;
  useUpdate: ReviewMutationHook<TDetail, TPayload>;
  useApprove: ReviewMutationHook<TDetail>;
  useReject: ReviewMutationHook<TDetail>;
  renderPayload: PayloadRenderer<TPayload>;
  itemName: string;
  onApproveSuccess?: (detail: TDetail) => void;
}) {
  const { data: detail, isLoading } = useDetail(item.id);
  const [draft, setDraft] = useState<TPayload | null>(null);
  const update = useUpdate(item.id);
  const approve = useApprove(item.id);
  const reject = useReject(item.id);
  const { message } = AntApp.useApp();

  useEffect(() => {
    if (detail) setDraft(detail.payload);
  }, [detail]);

  if (isLoading || !detail || !draft) {
    return <Skeleton active paragraph={{ rows: 4 }} />;
  }

  const isDirty = JSON.stringify(draft) !== JSON.stringify(detail.payload);
  const editable = canReview && detail.status === 'draft';

  const handleSave = async () => {
    try {
      await update.mutateAsync(draft);
      message.success(`${itemName} updated`);
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const guardDirty = () => {
    if (isDirty) {
      message.warning('Save your changes before approving or rejecting.');
      return true;
    }
    return false;
  };

  const handleApprove = async () => {
    if (guardDirty()) return;
    try {
      const result = await approve.mutateAsync();
      if (onApproveSuccess) {
        onApproveSuccess(result);
      } else {
        message.success(`${itemName} approved`);
      }
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleReject = async () => {
    if (guardDirty()) return;
    try {
      await reject.mutateAsync();
      message.success(`${itemName} rejected`);
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  return (
    <ApprovalPanel
      status={detail.status}
      createdAt={detail.created_at}
      approvedAt={detail.approved_at}
      canEdit={editable}
      canReview={editable}
      isDirty={isDirty}
      saving={update.isPending}
      approving={approve.isPending}
      rejecting={reject.isPending}
      onSave={handleSave}
      onApprove={handleApprove}
      onReject={handleReject}
    >
      {renderPayload(draft, editable, setDraft)}
    </ApprovalPanel>
  );
}

/** A prior item in the history list — read-only, payload lazy-loaded on expand. */
function HistoryReviewBody<TPayload, TDetail extends ReviewItem & { payload: TPayload }>({
  itemId,
  active,
  useDetail,
  renderPayload,
}: {
  itemId: string;
  active: boolean;
  useDetail: ReviewDetailHook<TDetail>;
  renderPayload: PayloadRenderer<TPayload>;
}) {
  const { data, isLoading } = useDetail(itemId, { enabled: active });
  if (!active) return null;
  if (isLoading || !data) return <Skeleton active paragraph={{ rows: 3 }} />;
  return (
    <ApprovalPanel
      status={data.status}
      createdAt={data.created_at}
      approvedAt={data.approved_at}
      canEdit={false}
      canReview={false}
    >
      {renderPayload(data.payload, false, () => {})}
    </ApprovalPanel>
  );
}

export interface ReviewSectionProps<TPayload, TDetail extends ReviewItem & { payload: TPayload }> {
  /** Section heading, e.g. "AI Analysis" / "Feasibility Study" / "Test Strategy". */
  title: string;
  /** Label for the "generate a new draft" button, e.g. "Analyze". */
  generateLabel: string;
  generateIcon?: ReactNode;
  onGenerate: () => void | Promise<void>;
  generating: boolean;
  /**
   * Extra control rendered next to the generate button, e.g. a scope picker
   * that the caller's `onGenerate` closure reads from its own local state.
   * Keeps sections with no pre-generate input (Analysis/Feasibility/Strategy)
   * simple while letting Test Design (which needs a scope) opt in.
   */
  generateExtra?: ReactNode;
  /** Member/admin — gates the generate button and edit/approve/reject inside the current panel. */
  canEdit: boolean;
  items: ReviewItem[] | undefined;
  itemsLoading: boolean;
  emptyEditableText: string;
  emptyReadonlyText: string;
  historyTitle: string;
  /** Noun used in save/approve/reject toasts, e.g. "Analysis" / "Feasibility study". */
  itemName: string;
  useDetail: ReviewDetailHook<TDetail>;
  useUpdate: ReviewMutationHook<TDetail, TPayload>;
  useApprove: ReviewMutationHook<TDetail>;
  useReject: ReviewMutationHook<TDetail>;
  renderPayload: PayloadRenderer<TPayload>;
  /**
   * Called instead of the generic "$itemName approved" toast when an approve
   * succeeds — lets a section show payload-specific success UI (e.g. Test
   * Design surfacing how many Test Cases were just created).
   */
  onApproveSuccess?: (detail: TDetail) => void;
}

/**
 * Generic "AI suggests -> human reviews -> approves" section: a generate
 * button, the current draft/approved/rejected item rendered via
 * `ApprovalPanel` + the caller's payload view, and a collapsed read-only
 * history list below. Parameterized so the AI Analysis, Feasibility Study,
 * and Test Strategy sections on the requirement detail page share this one
 * wrapper instead of tripling the same boilerplate.
 */
export function ReviewSection<TPayload, TDetail extends ReviewItem & { payload: TPayload }>({
  title,
  generateLabel,
  generateIcon,
  onGenerate,
  generating,
  generateExtra,
  canEdit,
  items,
  itemsLoading,
  emptyEditableText,
  emptyReadonlyText,
  historyTitle,
  itemName,
  useDetail,
  useUpdate,
  useApprove,
  useReject,
  renderPayload,
  onApproveSuccess,
}: ReviewSectionProps<TPayload, TDetail>) {
  const [historyActiveKeys, setHistoryActiveKeys] = useState<string[]>([]);
  const [latest, ...history] = items ?? [];

  return (
    <div>
      <div
        style={{
          marginTop: 24,
          marginBottom: 12,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Title level={4} style={{ margin: 0 }}>
          {title}
        </Title>
        {canEdit && (
          <Space>
            {generateExtra}
            <Button type="primary" icon={generateIcon} onClick={onGenerate} loading={generating}>
              {generateLabel}
            </Button>
          </Space>
        )}
      </div>

      <Card>
        {itemsLoading ? (
          <Skeleton active paragraph={{ rows: 4 }} />
        ) : !latest ? (
          <Empty description={canEdit ? emptyEditableText : emptyReadonlyText} />
        ) : (
          <CurrentReviewPanel
            item={latest}
            canReview={canEdit}
            useDetail={useDetail}
            useUpdate={useUpdate}
            useApprove={useApprove}
            useReject={useReject}
            renderPayload={renderPayload}
            itemName={itemName}
            onApproveSuccess={onApproveSuccess}
          />
        )}
      </Card>

      {history.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <Title level={5}>{historyTitle}</Title>
          <Collapse
            activeKey={historyActiveKeys}
            onChange={(keys) => setHistoryActiveKeys(Array.isArray(keys) ? keys : [keys])}
            items={history.map((h) => ({
              key: h.id,
              label: (
                <Space>
                  <StatusBadge status={h.status} />
                  <Text type="secondary">{new Date(h.created_at).toLocaleString()}</Text>
                </Space>
              ),
              children: (
                <HistoryReviewBody
                  itemId={h.id}
                  active={historyActiveKeys.includes(h.id)}
                  useDetail={useDetail}
                  renderPayload={renderPayload}
                />
              ),
            }))}
          />
        </div>
      )}
    </div>
  );
}
