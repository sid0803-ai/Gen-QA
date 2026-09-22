import { useEffect, useState } from 'react';
import {
  App as AntApp,
  Button,
  Card,
  Collapse,
  Empty,
  Form,
  Modal,
  Popconfirm,
  Skeleton,
  Space,
  Typography,
} from 'antd';
import { DeleteOutlined, EditOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useDeleteRequirement, useRequirement, useUpdateRequirement } from '../../hooks/useRequirements';
import {
  useAnalyses,
  useAnalysis,
  useApproveAnalysis,
  useCreateAnalysis,
  useRejectAnalysis,
  useUpdateAnalysis,
} from '../../hooks/useAnalyses';
import { useProjects } from '../../hooks/useProjects';
import { StatusBadge } from '../../components/StatusBadge';
import { ApprovalPanel } from '../../components/ApprovalPanel';
import { ApiError } from '../../api/client';
import type { Analysis, RequirementAnalysisPayload, RequirementUpdateInput } from '../../api/types';
import { RequirementFormFields } from './RequirementFormFields';
import { AnalysisPayloadView } from './AnalysisPayloadView';

const { Title, Paragraph, Text } = Typography;

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: 0.4 }}>
        {label}
      </Text>
      <Paragraph style={{ marginBottom: 0, marginTop: 2, whiteSpace: 'pre-wrap' }}>
        {value ? value : <Text type="secondary">—</Text>}
      </Paragraph>
    </div>
  );
}

/** The most recent analysis: fully editable while draft, with approve/reject. */
function CurrentAnalysisPanel({
  projectId,
  requirementId,
  analysis,
  canReview,
}: {
  projectId: string;
  requirementId: string;
  analysis: Analysis;
  canReview: boolean;
}) {
  const { data: detail, isLoading } = useAnalysis(projectId, requirementId, analysis.id);
  const [draft, setDraft] = useState<RequirementAnalysisPayload | null>(null);
  const updateAnalysis = useUpdateAnalysis(projectId, requirementId, analysis.id);
  const approveAnalysis = useApproveAnalysis(projectId, requirementId, analysis.id);
  const rejectAnalysis = useRejectAnalysis(projectId, requirementId, analysis.id);
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
      await updateAnalysis.mutateAsync(draft);
      message.success('Analysis updated');
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
      await approveAnalysis.mutateAsync();
      message.success('Analysis approved');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleReject = async () => {
    if (guardDirty()) return;
    try {
      await rejectAnalysis.mutateAsync();
      message.success('Analysis rejected');
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
      saving={updateAnalysis.isPending}
      approving={approveAnalysis.isPending}
      rejecting={rejectAnalysis.isPending}
      onSave={handleSave}
      onApprove={handleApprove}
      onReject={handleReject}
    >
      <AnalysisPayloadView payload={draft} editable={editable} onChange={setDraft} />
    </ApprovalPanel>
  );
}

/** A prior analysis in the history list — read-only, payload lazy-loaded on expand. */
function HistoryAnalysisBody({
  projectId,
  requirementId,
  analysisId,
  active,
}: {
  projectId: string;
  requirementId: string;
  analysisId: string;
  active: boolean;
}) {
  const { data, isLoading } = useAnalysis(projectId, requirementId, analysisId, { enabled: active });
  if (!active) return null;
  if (isLoading || !data) return <Skeleton active paragraph={{ rows: 3 }} />;
  return (
    <ApprovalPanel status={data.status} createdAt={data.created_at} approvedAt={data.approved_at} canEdit={false} canReview={false}>
      <AnalysisPayloadView payload={data.payload} editable={false} onChange={() => {}} />
    </ApprovalPanel>
  );
}

export default function RequirementDetailPage() {
  const { projectId, requirementId } = useParams();
  const navigate = useNavigate();
  const { data: requirement, isLoading } = useRequirement(projectId, requirementId);
  const { data: projects } = useProjects();
  const updateRequirement = useUpdateRequirement(projectId, requirementId);
  const deleteRequirement = useDeleteRequirement(projectId);
  const { data: analyses, isLoading: analysesLoading } = useAnalyses(projectId, requirementId);
  const createAnalysis = useCreateAnalysis(projectId, requirementId);
  const { message } = AntApp.useApp();

  const [editOpen, setEditOpen] = useState(false);
  const [form] = Form.useForm<RequirementUpdateInput>();
  const [historyActiveKeys, setHistoryActiveKeys] = useState<string[]>([]);

  const myRole = projects?.find((p) => p.id === projectId)?.role;
  const canEdit = myRole === 'admin' || myRole === 'member';
  const isAdmin = myRole === 'admin';

  const openEdit = () => {
    if (!requirement) return;
    form.setFieldsValue({
      title: requirement.title,
      description: requirement.description,
      business_objective: requirement.business_objective ?? undefined,
      acceptance_criteria: requirement.acceptance_criteria ?? undefined,
      priority: requirement.priority,
    });
    setEditOpen(true);
  };

  const handleEditSave = async () => {
    try {
      const values = await form.validateFields();
      await updateRequirement.mutateAsync(values);
      message.success('Requirement updated');
      setEditOpen(false);
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleDelete = async () => {
    if (!requirementId) return;
    try {
      await deleteRequirement.mutateAsync(requirementId);
      message.success('Requirement deleted');
      navigate(`/projects/${projectId}/requirements`);
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleAnalyze = async () => {
    try {
      await createAnalysis.mutateAsync();
      message.success('Analysis started');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  if (isLoading || !requirement) {
    return <Skeleton active paragraph={{ rows: 6 }} />;
  }

  const [latest, ...history] = analyses ?? [];

  return (
    <div>
      <Space style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }} wrap>
        <Space direction="vertical" size={4}>
          <Space align="center">
            <Title level={3} style={{ margin: 0 }}>
              {requirement.title}
            </Title>
            <StatusBadge status={requirement.priority} />
          </Space>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Created {new Date(requirement.created_at).toLocaleString()}
          </Text>
        </Space>
        <Space>
          {canEdit && (
            <Button icon={<EditOutlined />} onClick={openEdit}>
              Edit
            </Button>
          )}
          {isAdmin && (
            <Popconfirm title="Delete this requirement?" onConfirm={handleDelete}>
              <Button danger icon={<DeleteOutlined />} loading={deleteRequirement.isPending}>
                Delete
              </Button>
            </Popconfirm>
          )}
        </Space>
      </Space>

      <Card style={{ marginTop: 16 }}>
        <Field label="Description" value={requirement.description} />
        <Field label="Business objective" value={requirement.business_objective} />
        <Field label="Acceptance criteria" value={requirement.acceptance_criteria} />
      </Card>

      <div style={{ marginTop: 24, marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={4} style={{ margin: 0 }}>
          AI Analysis
        </Title>
        {canEdit && (
          <Button type="primary" icon={<ThunderboltOutlined />} onClick={handleAnalyze} loading={createAnalysis.isPending}>
            Analyze
          </Button>
        )}
      </div>

      <Card>
        {analysesLoading ? (
          <Skeleton active paragraph={{ rows: 4 }} />
        ) : !latest ? (
          <Empty
            description={
              canEdit
                ? 'No analysis yet — click Analyze to generate an AI review of this requirement.'
                : 'No analysis yet.'
            }
          />
        ) : (
          projectId &&
          requirementId && (
            <CurrentAnalysisPanel
              projectId={projectId}
              requirementId={requirementId}
              analysis={latest}
              canReview={canEdit}
            />
          )
        )}
      </Card>

      {history.length > 0 && projectId && requirementId && (
        <div style={{ marginTop: 24 }}>
          <Title level={5}>Analysis History</Title>
          <Collapse
            activeKey={historyActiveKeys}
            onChange={(keys) => setHistoryActiveKeys(Array.isArray(keys) ? keys : [keys])}
            items={history.map((a) => ({
              key: a.id,
              label: (
                <Space>
                  <StatusBadge status={a.status} />
                  <Text type="secondary">{new Date(a.created_at).toLocaleString()}</Text>
                </Space>
              ),
              children: (
                <HistoryAnalysisBody
                  projectId={projectId}
                  requirementId={requirementId}
                  analysisId={a.id}
                  active={historyActiveKeys.includes(a.id)}
                />
              ),
            }))}
          />
        </div>
      )}

      {canEdit && (
        <Modal
          title="Edit Requirement"
          open={editOpen}
          onOk={handleEditSave}
          onCancel={() => setEditOpen(false)}
          confirmLoading={updateRequirement.isPending}
          okText="Save"
          destroyOnHidden
          width={640}
        >
          <Form<RequirementUpdateInput> form={form} layout="vertical">
            <RequirementFormFields />
          </Form>
        </Modal>
      )}
    </div>
  );
}
