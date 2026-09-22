import { useState } from 'react';
import {
  App as AntApp,
  Button,
  Card,
  Collapse,
  Drawer,
  Form,
  Popconfirm,
  Skeleton,
  Space,
  Tag,
  Typography,
} from 'antd';
import { DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import {
  useApproveTestCase,
  useDeleteTestCase,
  useTestCase,
  useTestCaseVersions,
  useUpdateTestCase,
} from '../../hooks/useTestCases';
import { useProjects } from '../../hooks/useProjects';
import { StatusBadge } from '../../components/StatusBadge';
import { ApiError } from '../../api/client';
import {
  CATEGORY_LABELS,
  EXECUTION_TYPE_LABELS,
  SEVERITY_COLORS,
  SEVERITY_LABELS,
  TESTING_LEVEL_LABELS,
} from '../../api/testCaseOptions';
import { TestCaseFormFields } from './TestCaseFormFields';
import type { TestCaseUpdateInput, TestCaseVersion } from '../../api/types';

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

function StepsField({ steps }: { steps: string[] }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: 0.4 }}>
        Steps
      </Text>
      {steps.length === 0 ? (
        <Paragraph style={{ marginTop: 2 }}>
          <Text type="secondary">—</Text>
        </Paragraph>
      ) : (
        <ol style={{ margin: '2px 0 0', paddingLeft: 20 }}>
          {steps.map((step, i) => (
            <li key={i}>
              <Text>{step}</Text>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function VersionSnapshot({ snapshot }: { snapshot: TestCaseVersion['snapshot'] }) {
  return (
    <div>
      {snapshot.title !== undefined && <Field label="Title" value={snapshot.title} />}
      {snapshot.status !== undefined && (
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase' }}>
            Status
          </Text>
          <div style={{ marginTop: 2 }}>
            <StatusBadge status={snapshot.status} />
          </div>
        </div>
      )}
      {snapshot.preconditions !== undefined && <Field label="Preconditions" value={snapshot.preconditions} />}
      {snapshot.test_data !== undefined && <Field label="Test data" value={snapshot.test_data} />}
      {snapshot.steps !== undefined && <StepsField steps={snapshot.steps} />}
      {snapshot.expected_result !== undefined && <Field label="Expected result" value={snapshot.expected_result} />}
      {snapshot.business_rule !== undefined && <Field label="Business rule" value={snapshot.business_rule} />}
    </div>
  );
}

function VersionHistoryBody({ projectId, testCaseId }: { projectId: string | undefined; testCaseId: string | undefined }) {
  const { data: versions, isLoading } = useTestCaseVersions(projectId, testCaseId);
  if (isLoading || !versions) {
    return <Skeleton active paragraph={{ rows: 3 }} />;
  }
  if (versions.length === 0) {
    return <Text type="secondary">No prior versions.</Text>;
  }
  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      {versions.map((v) => (
        <div key={v.version_number} style={{ borderLeft: '2px solid #f0f0f0', paddingLeft: 12 }}>
          <Space style={{ marginBottom: 4 }}>
            <Text strong>Version {v.version_number}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {v.edited_by} · {new Date(v.edited_at).toLocaleString()}
            </Text>
          </Space>
          <VersionSnapshot snapshot={v.snapshot} />
        </div>
      ))}
    </Space>
  );
}

export default function TestCaseDetailPage() {
  const { projectId, testCaseId } = useParams();
  const navigate = useNavigate();
  const { data: testCase, isLoading } = useTestCase(projectId, testCaseId);
  const { data: projects } = useProjects();
  const updateTestCase = useUpdateTestCase(projectId, testCaseId);
  const approveTestCase = useApproveTestCase(projectId, testCaseId);
  const deleteTestCase = useDeleteTestCase(projectId);
  const { message } = AntApp.useApp();

  const [editOpen, setEditOpen] = useState(false);
  const [historyKeys, setHistoryKeys] = useState<string[]>([]);
  const [form] = Form.useForm<TestCaseUpdateInput>();

  const myRole = projects?.find((p) => p.id === projectId)?.role;
  const canEdit = myRole === 'admin' || myRole === 'member';
  const isAdmin = myRole === 'admin';
  const historyOpen = historyKeys.includes('history');

  const openEdit = () => {
    if (!testCase) return;
    form.setFieldsValue({
      title: testCase.title,
      category: testCase.category,
      testing_level: testCase.testing_level,
      priority: testCase.priority,
      severity: testCase.severity,
      preconditions: testCase.preconditions,
      test_data: testCase.test_data,
      steps: testCase.steps,
      expected_result: testCase.expected_result,
      business_rule: testCase.business_rule,
      automation_candidate: testCase.automation_candidate,
      execution_type: testCase.execution_type,
      tags: testCase.tags,
    });
    setEditOpen(true);
  };

  const handleEditSave = async () => {
    try {
      const values = await form.validateFields();
      await updateTestCase.mutateAsync(values);
      message.success('Test case updated');
      setEditOpen(false);
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleApprove = async () => {
    try {
      await approveTestCase.mutateAsync();
      message.success('Test case approved');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleDelete = async () => {
    if (!testCaseId) return;
    try {
      await deleteTestCase.mutateAsync(testCaseId);
      message.success('Test case deleted');
      navigate(`/projects/${projectId}/test-cases`);
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  if (isLoading || !testCase) {
    return <Skeleton active paragraph={{ rows: 8 }} />;
  }

  return (
    <div>
      <Space style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }} wrap>
        <Space direction="vertical" size={4}>
          <Space align="center" wrap>
            <Text type="secondary">{testCase.code}</Text>
            <Title level={3} style={{ margin: 0 }}>
              {testCase.title}
            </Title>
            <StatusBadge status={testCase.status} />
          </Space>
          <Space wrap>
            <Tag>{TESTING_LEVEL_LABELS[testCase.testing_level]}</Tag>
            <Tag>{CATEGORY_LABELS[testCase.category]}</Tag>
            <StatusBadge status={testCase.priority} />
            <Tag color={SEVERITY_COLORS[testCase.severity]}>{SEVERITY_LABELS[testCase.severity]}</Tag>
            <Tag color={testCase.source === 'ai' ? 'purple' : 'blue'}>
              {testCase.source === 'ai' ? 'AI' : 'Human'}
            </Tag>
            <Tag color={testCase.automation_candidate ? 'green' : 'default'}>
              {testCase.automation_candidate ? 'Automation candidate' : 'Not automation candidate'}
            </Tag>
            <Tag>{EXECUTION_TYPE_LABELS[testCase.execution_type]}</Tag>
          </Space>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Requirement:{' '}
            <a onClick={() => navigate(`/projects/${projectId}/requirements/${testCase.requirement_id}`)}>
              {testCase.requirement_title}
            </a>
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Created {new Date(testCase.created_at).toLocaleString()}
          </Text>
        </Space>
        <Space>
          {canEdit && (
            <Button icon={<EditOutlined />} onClick={openEdit}>
              Edit
            </Button>
          )}
          {canEdit && testCase.status === 'draft' && (
            <Button type="primary" onClick={handleApprove} loading={approveTestCase.isPending}>
              Approve
            </Button>
          )}
          {isAdmin && (
            <Popconfirm title="Delete this test case?" onConfirm={handleDelete}>
              <Button danger icon={<DeleteOutlined />} loading={deleteTestCase.isPending}>
                Delete
              </Button>
            </Popconfirm>
          )}
        </Space>
      </Space>

      {testCase.tags.length > 0 && (
        <Space wrap style={{ marginTop: 12 }}>
          {testCase.tags.map((tag) => (
            <Tag key={tag}>{tag}</Tag>
          ))}
        </Space>
      )}

      <Card style={{ marginTop: 16 }}>
        <Field label="Preconditions" value={testCase.preconditions} />
        <Field label="Test data" value={testCase.test_data} />
        <StepsField steps={testCase.steps} />
        <Field label="Expected result" value={testCase.expected_result} />
        <Field label="Business rule" value={testCase.business_rule} />
      </Card>

      <div style={{ marginTop: 24 }}>
        <Collapse
          activeKey={historyKeys}
          onChange={(keys) => setHistoryKeys(Array.isArray(keys) ? keys : [keys])}
          items={[
            {
              key: 'history',
              label: 'Version History',
              children: historyOpen ? (
                <VersionHistoryBody projectId={projectId} testCaseId={testCaseId} />
              ) : null,
            },
          ]}
        />
      </div>

      {canEdit && (
        <Drawer
          title="Edit Test Case"
          open={editOpen}
          onClose={() => setEditOpen(false)}
          width={520}
          destroyOnHidden
          extra={
            <Space>
              <Button onClick={() => setEditOpen(false)}>Cancel</Button>
              <Button type="primary" onClick={handleEditSave} loading={updateTestCase.isPending}>
                Save
              </Button>
            </Space>
          }
        >
          <Form<TestCaseUpdateInput> form={form} layout="vertical">
            <TestCaseFormFields />
          </Form>
        </Drawer>
      )}
    </div>
  );
}

