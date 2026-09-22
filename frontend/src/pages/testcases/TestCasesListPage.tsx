import { useState } from 'react';
import { App as AntApp, Button, Drawer, Empty, Form, Input, Select, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined } from '@ant-design/icons';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useCreateTestCase, useTestCases } from '../../hooks/useTestCases';
import { useProjects } from '../../hooks/useProjects';
import { useRequirements } from '../../hooks/useRequirements';
import { StatusBadge } from '../../components/StatusBadge';
import { ApiError } from '../../api/client';
import { PRIORITY_OPTIONS } from '../../api/priority';
import {
  CATEGORY_LABELS,
  CATEGORY_OPTIONS,
  SEVERITY_COLORS,
  SEVERITY_LABELS,
  TESTING_LEVEL_LABELS,
  TESTING_LEVEL_OPTIONS,
} from '../../api/testCaseOptions';
import { TestCaseFormFields } from './TestCaseFormFields';
import type {
  Priority,
  ScenarioCategory,
  Severity,
  TestCaseCreateInput,
  TestCaseListParams,
  TestCaseStatus,
  TestCaseSummary,
  TestingLevel,
} from '../../api/types';

const TEST_CASE_STATUS_OPTIONS: { value: TestCaseStatus; label: string }[] = [
  { value: 'draft', label: 'Draft' },
  { value: 'approved', label: 'Approved' },
];

const AUTOMATION_FILTER_OPTIONS = [
  { value: 'true', label: 'Yes' },
  { value: 'false', label: 'No' },
];

export default function TestCasesListPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { data: projects } = useProjects();
  const { data: requirements } = useRequirements(projectId);
  const { message } = AntApp.useApp();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [form] = Form.useForm<TestCaseCreateInput>();

  const myRole = projects?.find((p) => p.id === projectId)?.role;
  const canCreate = myRole === 'admin' || myRole === 'member';

  const params: TestCaseListParams = {
    requirement_id: searchParams.get('requirement_id') ?? undefined,
    testing_level: (searchParams.get('testing_level') as TestingLevel | null) ?? undefined,
    category: (searchParams.get('category') as ScenarioCategory | null) ?? undefined,
    priority: (searchParams.get('priority') as Priority | null) ?? undefined,
    status: (searchParams.get('status') as TestCaseStatus | null) ?? undefined,
    automation_candidate: searchParams.has('automation_candidate')
      ? searchParams.get('automation_candidate') === 'true'
      : undefined,
    search: searchParams.get('search') ?? undefined,
  };

  const { data: testCases, isLoading } = useTestCases(projectId, params);
  const createTestCase = useCreateTestCase(projectId);

  const setParam = (key: string, value: string | undefined) => {
    const next = new URLSearchParams(searchParams);
    if (value === undefined || value === '') {
      next.delete(key);
    } else {
      next.set(key, value);
    }
    setSearchParams(next, { replace: true });
  };

  const goToTestCase = (id: string) => navigate(`/projects/${projectId}/test-cases/${id}`);
  const goToRequirement = (id: string) => navigate(`/projects/${projectId}/requirements/${id}`);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      const created = await createTestCase.mutateAsync(values);
      message.success('Test case created');
      setDrawerOpen(false);
      form.resetFields();
      goToTestCase(created.id);
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const columns: ColumnsType<TestCaseSummary> = [
    { title: 'Code', dataIndex: 'code', key: 'code', width: 110 },
    {
      title: 'Title',
      dataIndex: 'title',
      key: 'title',
      render: (title: string, record) => (
        <a
          onClick={(e) => {
            e.stopPropagation();
            goToTestCase(record.id);
          }}
        >
          {title}
        </a>
      ),
    },
    {
      title: 'Testing Level',
      dataIndex: 'testing_level',
      key: 'testing_level',
      width: 130,
      render: (level: TestingLevel) => TESTING_LEVEL_LABELS[level],
    },
    {
      title: 'Category',
      dataIndex: 'category',
      key: 'category',
      width: 140,
      render: (category: ScenarioCategory) => CATEGORY_LABELS[category],
    },
    {
      title: 'Priority',
      dataIndex: 'priority',
      key: 'priority',
      width: 110,
      render: (priority: Priority) => <StatusBadge status={priority} />,
    },
    {
      title: 'Severity',
      dataIndex: 'severity',
      key: 'severity',
      width: 110,
      render: (severity: Severity) => <Tag color={SEVERITY_COLORS[severity]}>{SEVERITY_LABELS[severity]}</Tag>,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (status: TestCaseStatus) => <StatusBadge status={status} />,
    },
    {
      title: 'Source',
      dataIndex: 'source',
      key: 'source',
      width: 90,
      render: (source: 'ai' | 'human') => <Tag color={source === 'ai' ? 'purple' : 'blue'}>{source === 'ai' ? 'AI' : 'Human'}</Tag>,
    },
    {
      title: 'Automation',
      dataIndex: 'automation_candidate',
      key: 'automation_candidate',
      width: 110,
      render: (value: boolean) => <Tag color={value ? 'green' : 'default'}>{value ? 'Yes' : 'No'}</Tag>,
    },
    {
      title: 'Requirement',
      dataIndex: 'requirement_title',
      key: 'requirement_title',
      render: (title: string, record) => (
        <a
          onClick={(e) => {
            e.stopPropagation();
            goToRequirement(record.requirement_id);
          }}
        >
          {title}
        </a>
      ),
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 140,
      render: (createdAt: string) => new Date(createdAt).toLocaleDateString(),
    },
  ];

  return (
    <div>
      <Space style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          Test Cases
        </Typography.Title>
        {canCreate && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setDrawerOpen(true)}>
            New Test Case
          </Button>
        )}
      </Space>

      <Space wrap style={{ marginBottom: 16 }} data-testid="test-case-filters">
        <Input.Search
          placeholder="Search title..."
          allowClear
          style={{ width: 220 }}
          defaultValue={params.search}
          onSearch={(value) => setParam('search', value || undefined)}
        />
        <Select
          allowClear
          placeholder="Requirement"
          style={{ width: 200 }}
          value={params.requirement_id}
          options={(requirements ?? []).map((r) => ({ value: r.id, label: r.title }))}
          onChange={(value) => setParam('requirement_id', value)}
        />
        <Select
          allowClear
          placeholder="Testing level"
          style={{ width: 150 }}
          value={params.testing_level}
          options={TESTING_LEVEL_OPTIONS}
          onChange={(value) => setParam('testing_level', value)}
        />
        <Select
          allowClear
          placeholder="Category"
          style={{ width: 160 }}
          value={params.category}
          options={CATEGORY_OPTIONS}
          onChange={(value) => setParam('category', value)}
        />
        <Select
          allowClear
          placeholder="Priority"
          style={{ width: 130 }}
          value={params.priority}
          options={PRIORITY_OPTIONS}
          onChange={(value) => setParam('priority', value)}
        />
        <Select
          allowClear
          placeholder="Status"
          style={{ width: 130 }}
          value={params.status}
          options={TEST_CASE_STATUS_OPTIONS}
          onChange={(value) => setParam('status', value)}
        />
        <Select
          allowClear
          placeholder="Automation"
          style={{ width: 130 }}
          value={params.automation_candidate === undefined ? undefined : String(params.automation_candidate)}
          options={AUTOMATION_FILTER_OPTIONS}
          onChange={(value) => setParam('automation_candidate', value)}
        />
      </Space>

      <Table<TestCaseSummary>
        rowKey="id"
        columns={columns}
        dataSource={testCases ?? []}
        loading={isLoading}
        onRow={(record) => ({
          onClick: () => goToTestCase(record.id),
          style: { cursor: 'pointer' },
        })}
        locale={{
          emptyText: <Empty description="No test cases yet." />,
        }}
      />

      {canCreate && (
        <Drawer
          title="New Test Case"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          width={520}
          destroyOnHidden
          extra={
            <Space>
              <Button onClick={() => setDrawerOpen(false)}>Cancel</Button>
              <Button type="primary" onClick={handleCreate} loading={createTestCase.isPending}>
                Create
              </Button>
            </Space>
          }
        >
          <Form<TestCaseCreateInput>
            form={form}
            layout="vertical"
            initialValues={{
              priority: 'medium',
              severity: 'major',
              category: 'positive',
              testing_level: 'functional',
              execution_type: 'manual',
              automation_candidate: false,
              steps: [''],
              tags: [],
            }}
          >
            <TestCaseFormFields
              requirementOptions={(requirements ?? []).map((r) => ({ id: r.id, title: r.title }))}
            />
          </Form>
        </Drawer>
      )}
    </div>
  );
}
