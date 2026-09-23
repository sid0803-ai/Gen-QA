import { useMemo } from 'react';
import { Select, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useExecutions } from '../../hooks/useExecutions';
import { useTestCases } from '../../hooks/useTestCases';
import { useEnvironments } from '../../hooks/useEnvironments';
import { StatusBadge } from '../../components/StatusBadge';
import type { Execution, ExecutionListParams, ExecutionRunType, ExecutionStatus } from '../../api/types';

const STATUS_OPTIONS: { value: ExecutionStatus; label: string }[] = [
  { value: 'pending', label: 'Pending' },
  { value: 'running', label: 'Running' },
  { value: 'passed', label: 'Passed' },
  { value: 'failed', label: 'Failed' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'skipped', label: 'Skipped' },
  { value: 'error', label: 'Error' },
];

const TYPE_OPTIONS: { value: ExecutionRunType; label: string }[] = [
  { value: 'manual', label: 'Manual' },
  { value: 'automated', label: 'Automated' },
];

function formatDuration(ms: number | null): string {
  if (ms == null) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Project-wide execution history — filters mirror the API's query params via `useSearchParams`, same pattern as `TestCasesListPage`. */
export default function ExecutionHistoryPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { data: testCases } = useTestCases(projectId, {});
  const { data: environments } = useEnvironments(projectId);

  const params: ExecutionListParams = {
    status: (searchParams.get('status') as ExecutionStatus | null) ?? undefined,
    type: (searchParams.get('type') as ExecutionRunType | null) ?? undefined,
    environment_id: searchParams.get('environment_id') ?? undefined,
  };

  const { data: executions, isLoading } = useExecutions(projectId, params);

  const testCaseById = useMemo(() => {
    const map = new Map<string, { code: string; title: string }>();
    for (const tc of testCases ?? []) map.set(tc.id, { code: tc.code, title: tc.title });
    return map;
  }, [testCases]);

  const environmentById = useMemo(() => {
    const map = new Map<string, string>();
    for (const env of environments ?? []) map.set(env.id, env.name);
    return map;
  }, [environments]);

  const setParam = (key: string, value: string | undefined) => {
    const next = new URLSearchParams(searchParams);
    if (value === undefined || value === '') {
      next.delete(key);
    } else {
      next.set(key, value);
    }
    setSearchParams(next, { replace: true });
  };

  const columns: ColumnsType<Execution> = [
    {
      title: 'Test Case',
      dataIndex: 'test_case_id',
      key: 'test_case_id',
      render: (testCaseId: string) => {
        const tc = testCaseById.get(testCaseId);
        return (
          <a onClick={() => navigate(`/projects/${projectId}/test-cases/${testCaseId}`)}>
            {tc ? `${tc.code} — ${tc.title}` : testCaseId}
          </a>
        );
      },
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      width: 110,
      render: (type: ExecutionRunType) => (
        <Tag color={type === 'automated' ? 'purple' : 'blue'}>{type === 'automated' ? 'Automated' : 'Manual'}</Tag>
      ),
    },
    {
      title: 'Environment',
      dataIndex: 'environment_id',
      key: 'environment_id',
      width: 140,
      render: (environmentId: string) => environmentById.get(environmentId) ?? environmentId,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (status: ExecutionStatus) => <StatusBadge status={status} />,
    },
    { title: 'Triggered by', dataIndex: 'triggered_by', key: 'triggered_by', width: 160 },
    {
      title: 'Date',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (createdAt: string) => new Date(createdAt).toLocaleString(),
    },
    {
      title: 'Duration',
      dataIndex: 'duration_ms',
      key: 'duration_ms',
      width: 100,
      render: (durationMs: number | null) => formatDuration(durationMs),
    },
  ];

  return (
    <div>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        Testing
      </Typography.Title>

      <Space wrap style={{ marginBottom: 16 }} data-testid="execution-history-filters">
        <span data-testid="filter-status">
          <Select
            allowClear
            placeholder="Status"
            style={{ width: 140 }}
            value={params.status}
            options={STATUS_OPTIONS}
            onChange={(value) => setParam('status', value)}
          />
        </span>
        <span data-testid="filter-type">
          <Select
            allowClear
            placeholder="Type"
            style={{ width: 140 }}
            value={params.type}
            options={TYPE_OPTIONS}
            onChange={(value) => setParam('type', value)}
          />
        </span>
        <span data-testid="filter-environment">
          <Select
            allowClear
            placeholder="Environment"
            style={{ width: 180 }}
            value={params.environment_id}
            options={(environments ?? []).map((e) => ({ value: e.id, label: e.name }))}
            onChange={(value) => setParam('environment_id', value)}
          />
        </span>
      </Space>

      <Table<Execution>
        rowKey="id"
        columns={columns}
        dataSource={executions ?? []}
        loading={isLoading}
        expandable={{
          rowExpandable: () => true,
          expandedRowRender: (record) => (
            <Space direction="vertical" size={4} style={{ width: '100%' }}>
              {record.type === 'manual' ? (
                <>
                  <Typography.Text strong>Actual result</Typography.Text>
                  <Typography.Paragraph style={{ marginBottom: 8, whiteSpace: 'pre-wrap' }}>
                    {record.actual_result || <Typography.Text type="secondary">—</Typography.Text>}
                  </Typography.Paragraph>
                  <Typography.Text strong>Comments</Typography.Text>
                  <Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                    {record.comments || <Typography.Text type="secondary">—</Typography.Text>}
                  </Typography.Paragraph>
                </>
              ) : (
                <>
                  <Typography.Text strong>Logs</Typography.Text>
                  <Typography.Paragraph
                    style={{ marginBottom: 8, whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 12 }}
                  >
                    {record.logs || <Typography.Text type="secondary">—</Typography.Text>}
                  </Typography.Paragraph>
                  <Typography.Text strong>Error</Typography.Text>
                  <Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>
                    {record.error_message || <Typography.Text type="secondary">—</Typography.Text>}
                  </Typography.Paragraph>
                </>
              )}
            </Space>
          ),
        }}
        locale={{ emptyText: <Typography.Text type="secondary">No executions yet.</Typography.Text> }}
      />
    </div>
  );
}
