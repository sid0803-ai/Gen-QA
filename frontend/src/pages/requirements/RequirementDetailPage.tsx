import { useState } from 'react';
import { App as AntApp, Button, Card, Form, Modal, Popconfirm, Skeleton, Space, Typography } from 'antd';
import {
  ApartmentOutlined,
  DeleteOutlined,
  EditOutlined,
  ExperimentOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
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
import {
  useApproveFeasibility,
  useCreateFeasibility,
  useFeasibilities,
  useFeasibility,
  useRejectFeasibility,
  useUpdateFeasibility,
} from '../../hooks/useFeasibility';
import {
  useApproveStrategy,
  useCreateStrategy,
  useRejectStrategy,
  useStrategies,
  useStrategy,
  useUpdateStrategy,
} from '../../hooks/useStrategy';
import { useProjects } from '../../hooks/useProjects';
import { StatusBadge } from '../../components/StatusBadge';
import { ReviewSection } from '../../components/ReviewSection';
import { ApiError } from '../../api/client';
import type {
  AnalysisDetail,
  FeasibilityDetail,
  RequirementAnalysisPayload,
  RequirementUpdateInput,
  FeasibilityStudyPayload,
  StrategyDetail,
  TestStrategyPayload,
} from '../../api/types';
import { RequirementFormFields } from './RequirementFormFields';
import { AnalysisPayloadView } from './AnalysisPayloadView';
import { FeasibilityPayloadView } from './FeasibilityPayloadView';
import { TestStrategyPayloadView } from './TestStrategyPayloadView';

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

export default function RequirementDetailPage() {
  const { projectId, requirementId } = useParams();
  const navigate = useNavigate();
  const { data: requirement, isLoading } = useRequirement(projectId, requirementId);
  const { data: projects } = useProjects();
  const updateRequirement = useUpdateRequirement(projectId, requirementId);
  const deleteRequirement = useDeleteRequirement(projectId);
  const { message } = AntApp.useApp();

  // AI Analysis
  const { data: analyses, isLoading: analysesLoading } = useAnalyses(projectId, requirementId);
  const createAnalysis = useCreateAnalysis(projectId, requirementId);

  // Feasibility Study
  const { data: feasibilityStudies, isLoading: feasibilityLoading } = useFeasibilities(
    projectId,
    requirementId,
  );
  const createFeasibility = useCreateFeasibility(projectId, requirementId);

  // Test Strategy
  const { data: strategies, isLoading: strategiesLoading } = useStrategies(projectId, requirementId);
  const createStrategy = useCreateStrategy(projectId, requirementId);

  const [editOpen, setEditOpen] = useState(false);
  const [form] = Form.useForm<RequirementUpdateInput>();

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

  const handleRunFeasibility = async () => {
    try {
      await createFeasibility.mutateAsync();
      message.success('Feasibility study started');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleGenerateStrategy = async () => {
    try {
      await createStrategy.mutateAsync();
      message.success('Test strategy started');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  // Named `use*` wrappers (not inline arrows) so eslint-plugin-react-hooks
  // recognizes these as hooks rather than plain callbacks when passed as
  // props to ReviewSection.
  const useAnalysisDetail = (id: string | undefined, opts?: { enabled?: boolean }) =>
    useAnalysis(projectId, requirementId, id, opts);
  const useAnalysisUpdate = (id: string | undefined) => useUpdateAnalysis(projectId, requirementId, id);
  const useAnalysisApprove = (id: string | undefined) => useApproveAnalysis(projectId, requirementId, id);
  const useAnalysisReject = (id: string | undefined) => useRejectAnalysis(projectId, requirementId, id);

  const useFeasibilityDetail = (id: string | undefined, opts?: { enabled?: boolean }) =>
    useFeasibility(projectId, requirementId, id, opts);
  const useFeasibilityUpdate = (id: string | undefined) => useUpdateFeasibility(projectId, requirementId, id);
  const useFeasibilityApprove = (id: string | undefined) =>
    useApproveFeasibility(projectId, requirementId, id);
  const useFeasibilityReject = (id: string | undefined) => useRejectFeasibility(projectId, requirementId, id);

  const useStrategyDetail = (id: string | undefined, opts?: { enabled?: boolean }) =>
    useStrategy(projectId, requirementId, id, opts);
  const useStrategyUpdate = (id: string | undefined) => useUpdateStrategy(projectId, requirementId, id);
  const useStrategyApprove = (id: string | undefined) => useApproveStrategy(projectId, requirementId, id);
  const useStrategyReject = (id: string | undefined) => useRejectStrategy(projectId, requirementId, id);

  if (isLoading || !requirement) {
    return <Skeleton active paragraph={{ rows: 6 }} />;
  }

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

      <ReviewSection<RequirementAnalysisPayload, AnalysisDetail>
        title="AI Analysis"
        generateLabel="Analyze"
        generateIcon={<ThunderboltOutlined />}
        onGenerate={handleAnalyze}
        generating={createAnalysis.isPending}
        canEdit={canEdit}
        items={analyses}
        itemsLoading={analysesLoading}
        emptyEditableText="No analysis yet — click Analyze to generate an AI review of this requirement."
        emptyReadonlyText="No analysis yet."
        historyTitle="Analysis History"
        itemName="Analysis"
        useDetail={useAnalysisDetail}
        useUpdate={useAnalysisUpdate}
        useApprove={useAnalysisApprove}
        useReject={useAnalysisReject}
        renderPayload={(payload, editable, onChange) => (
          <AnalysisPayloadView payload={payload} editable={editable} onChange={onChange} />
        )}
      />

      <ReviewSection<FeasibilityStudyPayload, FeasibilityDetail>
        title="Feasibility Study"
        generateLabel="Run Feasibility Study"
        generateIcon={<ExperimentOutlined />}
        onGenerate={handleRunFeasibility}
        generating={createFeasibility.isPending}
        canEdit={canEdit}
        items={feasibilityStudies}
        itemsLoading={feasibilityLoading}
        emptyEditableText="No feasibility study yet — click Run Feasibility Study to generate an AI assessment of automation feasibility."
        emptyReadonlyText="No feasibility study yet."
        historyTitle="Feasibility Study History"
        itemName="Feasibility study"
        useDetail={useFeasibilityDetail}
        useUpdate={useFeasibilityUpdate}
        useApprove={useFeasibilityApprove}
        useReject={useFeasibilityReject}
        renderPayload={(payload, editable, onChange) => (
          <FeasibilityPayloadView payload={payload} editable={editable} onChange={onChange} />
        )}
      />

      <ReviewSection<TestStrategyPayload, StrategyDetail>
        title="Test Strategy"
        generateLabel="Generate Test Strategy"
        generateIcon={<ApartmentOutlined />}
        onGenerate={handleGenerateStrategy}
        generating={createStrategy.isPending}
        canEdit={canEdit}
        items={strategies}
        itemsLoading={strategiesLoading}
        emptyEditableText="No test strategy yet — click Generate Test Strategy to generate an AI-recommended testing approach."
        emptyReadonlyText="No test strategy yet."
        historyTitle="Test Strategy History"
        itemName="Test strategy"
        useDetail={useStrategyDetail}
        useUpdate={useStrategyUpdate}
        useApprove={useStrategyApprove}
        useReject={useStrategyReject}
        renderPayload={(payload, editable, onChange) => (
          <TestStrategyPayloadView payload={payload} editable={editable} onChange={onChange} />
        )}
      />

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
