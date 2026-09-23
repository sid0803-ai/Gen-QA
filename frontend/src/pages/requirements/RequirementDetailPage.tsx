import { useState } from 'react';
import { App as AntApp, Button, Card, Form, Modal, Popconfirm, Select, Skeleton, Space, Statistic, Typography } from 'antd';
import {
  ApartmentOutlined,
  BulbOutlined,
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
import {
  useApproveTestDesign,
  useCreateTestDesign,
  useRejectTestDesign,
  useTestDesign,
  useTestDesigns,
  useUpdateTestDesign,
} from '../../hooks/useTestDesign';
import { useProjects } from '../../hooks/useProjects';
import { useRequirementCoverage } from '../../hooks/useReports';
import { StatusBadge } from '../../components/StatusBadge';
import { ReviewSection } from '../../components/ReviewSection';
import { ApiError } from '../../api/client';
import { TEST_DESIGN_SCOPE_OPTIONS } from '../../api/testDesign';
import type {
  AnalysisDetail,
  FeasibilityDetail,
  RequirementAnalysisPayload,
  RequirementUpdateInput,
  FeasibilityStudyPayload,
  StrategyDetail,
  TestDesignDetail,
  TestDesignPayload,
  TestDesignScope,
  TestStrategyPayload,
} from '../../api/types';
import { RequirementFormFields } from './RequirementFormFields';
import { AnalysisPayloadView } from './AnalysisPayloadView';
import { FeasibilityPayloadView } from './FeasibilityPayloadView';
import { TestStrategyPayloadView } from './TestStrategyPayloadView';
import { TestDesignPayloadView } from './TestDesignPayloadView';

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
  const { data: coverage, isLoading: coverageLoading } = useRequirementCoverage(projectId, requirementId);
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

  // Test Design
  const { data: testDesigns, isLoading: testDesignsLoading } = useTestDesigns(projectId, requirementId);
  const createTestDesign = useCreateTestDesign(projectId, requirementId);
  const [testDesignScope, setTestDesignScope] = useState<TestDesignScope>('both');

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

  const handleGenerateTestDesign = async () => {
    try {
      await createTestDesign.mutateAsync(testDesignScope);
      message.success('Test design started');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleTestDesignApproveSuccess = (detail: TestDesignDetail) => {
    const count = detail.created_test_case_count ?? detail.created_test_case_ids?.length;
    const testCasesUrl = `/projects/${projectId}/test-cases?requirement_id=${requirementId}`;
    // Plain <a onClick={navigate}> rather than react-router's <Link>: antd's
    // message content is rendered through the AntApp holder, which sits
    // outside <BrowserRouter> in main.tsx, so a <Link> rendered there throws
    // (no Router context at that portal's mount point). `navigate` itself is
    // just a function closed over the router instance from this component
    // (which IS inside the Router), so calling it from a click handler here
    // works fine even though the anchor renders outside the Router tree.
    message.success(
      <span>
        {count != null
          ? `Test design approved — created ${count} test case${count === 1 ? '' : 's'}.`
          : 'Test design approved — test cases created.'}{' '}
        <a
          onClick={(e) => {
            e.preventDefault();
            navigate(testCasesUrl);
          }}
        >
          View in Test Cases
        </a>
      </span>,
      6,
    );
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

  const useTestDesignDetail = (id: string | undefined, opts?: { enabled?: boolean }) =>
    useTestDesign(projectId, requirementId, id, opts);
  const useTestDesignUpdate = (id: string | undefined) => useUpdateTestDesign(projectId, requirementId, id);
  const useTestDesignApprove = (id: string | undefined) => useApproveTestDesign(projectId, requirementId, id);
  const useTestDesignReject = (id: string | undefined) => useRejectTestDesign(projectId, requirementId, id);

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

      <Card
        title="Test coverage"
        size="small"
        style={{ marginTop: 16 }}
        data-testid="requirement-coverage-panel"
      >
        {coverageLoading ? (
          <Skeleton active paragraph={{ rows: 1 }} />
        ) : (
          <Space size={32} wrap>
            <Statistic title="Test cases" value={coverage?.test_case_count ?? 0} />
            <Statistic title="Automated" value={coverage?.automated_count ?? 0} />
            <Statistic title="Manual" value={coverage?.manual_count ?? 0} />
            <Statistic title="Hybrid" value={coverage?.hybrid_count ?? 0} />
            <Statistic
              title="Automation scripts approved"
              value={coverage?.automation_script_approved_count ?? 0}
            />
            {coverage?.pass_rate_pct != null ? (
              <Statistic title="Pass rate" value={coverage.pass_rate_pct} suffix="%" />
            ) : (
              <Statistic title="Pass rate" value="No runs yet" />
            )}
          </Space>
        )}
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

      <ReviewSection<TestDesignPayload, TestDesignDetail>
        title="Test Design"
        generateLabel="Generate Test Design"
        generateIcon={<BulbOutlined />}
        onGenerate={handleGenerateTestDesign}
        generating={createTestDesign.isPending}
        generateExtra={
          <Select<TestDesignScope>
            value={testDesignScope}
            onChange={setTestDesignScope}
            options={TEST_DESIGN_SCOPE_OPTIONS}
            style={{ width: 110 }}
          />
        }
        canEdit={canEdit}
        items={testDesigns}
        itemsLoading={testDesignsLoading}
        emptyEditableText="No test design yet — pick a scope and click Generate Test Design to generate AI-suggested test scenarios."
        emptyReadonlyText="No test design yet."
        historyTitle="Test Design History"
        itemName="Test design"
        useDetail={useTestDesignDetail}
        useUpdate={useTestDesignUpdate}
        useApprove={useTestDesignApprove}
        useReject={useTestDesignReject}
        onApproveSuccess={handleTestDesignApproveSuccess}
        renderPayload={(payload, editable, onChange) => (
          <TestDesignPayloadView payload={payload} editable={editable} onChange={onChange} />
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
