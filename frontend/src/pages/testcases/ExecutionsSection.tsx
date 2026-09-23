import { useEffect, useState } from 'react';
import { App as AntApp, Button, Card, Empty, Input, Select, Space, Spin, Table, Tag, Tooltip, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlayCircleOutlined } from '@ant-design/icons';
import { useQueryClient } from '@tanstack/react-query';
import { useAutomationScript } from '../../hooks/useAutomationScript';
import { useEnvironments } from '../../hooks/useEnvironments';
import { executionsKey, useCreateExecution, useExecution, useExecutions } from '../../hooks/useExecutions';
import { StatusBadge } from '../../components/StatusBadge';
import { ApiError } from '../../api/client';
import type { Execution, ExecutionStatus, ManualExecutionResultStatus } from '../../api/types';

const { Title, Text } = Typography;

const MANUAL_STATUS_OPTIONS: { value: ManualExecutionResultStatus; label: string }[] = [
  { value: 'passed', label: 'Passed' },
  { value: 'failed', label: 'Failed' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'skipped', label: 'Skipped' },
];

const NON_TERMINAL: ExecutionStatus[] = ['pending', 'running'];

function formatDuration(ms: number | null): string {
  if (ms == null) return '—';
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Manual recording + automated trigger for a test case, plus its execution
 * history. Shares the `useAutomationScript` query cache with
 * `AutomationScriptSection` (same query key, same component tree) so the
 * "Run" button's approved-script check doesn't refetch anything extra.
 */
export function ExecutionsSection({
  projectId,
  testCaseId,
  canEdit,
}: {
  projectId: string | undefined;
  testCaseId: string | undefined;
  canEdit: boolean;
}) {
  const { message } = AntApp.useApp();
  const queryClient = useQueryClient();
  const { data: environments, isLoading: environmentsLoading } = useEnvironments(projectId);
  const { data: script } = useAutomationScript(projectId, testCaseId);
  const { data: executions, isLoading: executionsLoading } = useExecutions(projectId, {
    test_case_id: testCaseId,
  });
  const createExecution = useCreateExecution(projectId);

  const [environmentId, setEnvironmentId] = useState<string | undefined>();
  const [manualStatus, setManualStatus] = useState<ManualExecutionResultStatus>('passed');
  const [actualResult, setActualResult] = useState('');
  const [comments, setComments] = useState('');
  const [activeExecutionId, setActiveExecutionId] = useState<string | undefined>();

  const { data: activeExecution } = useExecution(projectId, activeExecutionId, { poll: true });

  useEffect(() => {
    if (activeExecution && !NON_TERMINAL.includes(activeExecution.status)) {
      queryClient.invalidateQueries({ queryKey: executionsKey(projectId, { test_case_id: testCaseId }) });
    }
    // Only re-run when the polled execution's status actually transitions.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeExecution?.status]);

  const canRunAutomated = !!environmentId && script?.status === 'approved';
  const runDisabledReason = !environmentId
    ? 'Select an environment first'
    : script?.status !== 'approved'
      ? 'Approve an automation script before running it'
      : undefined;

  const handleRecordManual = async () => {
    if (!testCaseId || !environmentId) return;
    try {
      await createExecution.mutateAsync({
        test_case_id: testCaseId,
        environment_id: environmentId,
        type: 'manual',
        status: manualStatus,
        actual_result: actualResult || undefined,
        comments: comments || undefined,
      });
      message.success('Execution recorded');
      setActualResult('');
      setComments('');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleRunAutomated = async () => {
    if (!testCaseId || !environmentId) return;
    try {
      const result = await createExecution.mutateAsync({
        test_case_id: testCaseId,
        environment_id: environmentId,
        type: 'automated',
      });
      setActiveExecutionId(result.id);
      message.success('Automated run triggered');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const columns: ColumnsType<Execution> = [
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      width: 110,
      render: (t: Execution['type']) => (
        <Tag color={t === 'automated' ? 'purple' : 'blue'}>{t === 'automated' ? 'Automated' : 'Manual'}</Tag>
      ),
    },
    {
      title: 'Environment',
      dataIndex: 'environment_id',
      key: 'environment_id',
      width: 140,
      render: (id: string) => environments?.find((e) => e.id === id)?.name ?? id,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (s: ExecutionStatus) => <StatusBadge status={s} />,
    },
    { title: 'Triggered by', dataIndex: 'triggered_by', key: 'triggered_by', width: 150 },
    {
      title: 'Date',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (d: string) => new Date(d).toLocaleString(),
    },
    {
      title: 'Duration',
      dataIndex: 'duration_ms',
      key: 'duration_ms',
      width: 90,
      render: (ms: number | null) => formatDuration(ms),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginTop: 24, marginBottom: 12 }}>
        Executions
      </Title>

      <Card style={{ marginBottom: 16 }}>
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <div>
            <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: 0.4 }}>
              Environment *
            </Text>
            <div style={{ marginTop: 4 }} data-testid="execution-environment-select">
              <Select
                placeholder="Select environment"
                style={{ width: 240 }}
                value={environmentId}
                loading={environmentsLoading}
                options={(environments ?? []).map((e) => ({ value: e.id, label: e.name }))}
                onChange={setEnvironmentId}
              />
            </div>
          </div>

          {canEdit && (
            <>
              <div>
                <Text strong>Record manual result</Text>
                <Space direction="vertical" size={8} style={{ width: '100%', marginTop: 8 }}>
                  <span data-testid="manual-status-select">
                    <Select
                      value={manualStatus}
                      onChange={setManualStatus}
                      options={MANUAL_STATUS_OPTIONS}
                      style={{ width: 160 }}
                    />
                  </span>
                  <Input.TextArea
                    data-testid="manual-actual-result"
                    placeholder="Actual result"
                    value={actualResult}
                    onChange={(e) => setActualResult(e.target.value)}
                    rows={2}
                  />
                  <Input.TextArea
                    data-testid="manual-comments"
                    placeholder="Comments"
                    value={comments}
                    onChange={(e) => setComments(e.target.value)}
                    rows={2}
                  />
                  <span data-testid="record-result-button">
                    <Button
                      onClick={handleRecordManual}
                      disabled={!environmentId}
                      loading={createExecution.isPending}
                    >
                      Record Result
                    </Button>
                  </span>
                </Space>
              </div>

              <div>
                <Text strong>Automated run</Text>
                <div style={{ marginTop: 8 }}>
                  <Space>
                    <Tooltip title={runDisabledReason}>
                      <span data-testid="run-automated-button">
                        <Button
                          type="primary"
                          icon={<PlayCircleOutlined />}
                          onClick={handleRunAutomated}
                          disabled={!canRunAutomated}
                          loading={createExecution.isPending}
                        >
                          Run
                        </Button>
                      </span>
                    </Tooltip>
                    {activeExecution && (
                      <Space data-testid="active-execution-status">
                        {NON_TERMINAL.includes(activeExecution.status) && <Spin size="small" />}
                        <StatusBadge status={activeExecution.status} />
                      </Space>
                    )}
                  </Space>
                </div>
              </div>
            </>
          )}
        </Space>
      </Card>

      <Table<Execution>
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={executions ?? []}
        loading={executionsLoading}
        locale={{ emptyText: <Empty description="No executions yet." /> }}
        expandable={{
          expandedRowRender: (record) => (
            <Space direction="vertical" size={4} style={{ width: '100%' }}>
              {record.type === 'manual' ? (
                <>
                  <Text strong>Actual result</Text>
                  <Text style={{ whiteSpace: 'pre-wrap' }}>{record.actual_result || '—'}</Text>
                  <Text strong>Comments</Text>
                  <Text style={{ whiteSpace: 'pre-wrap' }}>{record.comments || '—'}</Text>
                </>
              ) : (
                <>
                  <Text strong>Logs</Text>
                  <Text style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 12, display: 'block' }}>
                    {record.logs || '—'}
                  </Text>
                  <Text strong>Error</Text>
                  <Text style={{ whiteSpace: 'pre-wrap' }}>{record.error_message || '—'}</Text>
                </>
              )}
            </Space>
          ),
        }}
      />
    </div>
  );
}
