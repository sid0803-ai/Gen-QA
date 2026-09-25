import { useEffect, useMemo, useState } from 'react';
import {
  App as AntApp,
  Button,
  Card,
  Col,
  Collapse,
  Descriptions,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { DeleteOutlined, PlusOutlined, SyncOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { JsonOrPlainView } from '../../components/JsonView';
import { useApiCollectionsTree } from '../../hooks/useApiCollections';
import { useSavedRequests } from '../../hooks/useApiPerformer';
import {
  performanceTestRunsKey,
  useCreatePerformanceTest,
  useDeletePerformanceTest,
  usePerformanceTestRun,
  usePerformanceTestRuns,
  usePerformanceTests,
  useTriggerPerformanceTestRun,
} from '../../hooks/usePerformanceTests';
import { ApiError } from '../../api/client';
import { methodColor } from '../../constants/httpMethod';
import type {
  ApiCollectionTreeNode,
  PerformanceTest,
  PerformanceTestRun,
  PerformanceTestRunStatus,
  PerformanceTestRunSummary,
  SavedApiRequest,
} from '../../api/types';

const { Title, Text } = Typography;

const NON_TERMINAL_STATUSES: PerformanceTestRunStatus[] = ['queued', 'running'];

function formatDateTime(value: string | null): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

function formatMs(value: number | null): string {
  return value === null || value === undefined ? '—' : `${value.toFixed(0)} ms`;
}

function formatRps(value: number | null): string {
  return value === null || value === undefined ? '—' : `${value.toFixed(2)}/s`;
}

/** `error_rate` is assumed to be a 0..1 fraction (standard k6 convention) and rendered as a percentage. */
function formatErrorRate(value: number | null): string {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(2)}%`;
}

function statusTag(status: PerformanceTestRunStatus) {
  switch (status) {
    case 'queued':
      return <Tag>Queued</Tag>;
    case 'running':
      return (
        <Tag icon={<SyncOutlined spin />} color="processing">
          Running
        </Tag>
      );
    case 'completed':
      return <Tag color="success">Completed</Tag>;
    case 'failed':
      return <Tag color="error">Failed</Tag>;
    default:
      return <Tag>{status}</Tag>;
  }
}

/** Flattened, group-labeled option shape for the "pick a saved request" Select — built from the Collection -> Folder -> Request tree. */
interface RequestOption {
  value: string;
  label: React.ReactNode;
  searchText: string;
}

function buildRequestOptionGroups(tree: ApiCollectionTreeNode[]) {
  return tree.map((collection) => {
    const toOption = (
      req: { id: string; name: string; method: string },
      folderName?: string,
    ): RequestOption => ({
      value: req.id,
      label: (
        <Space size={6}>
          <Text style={{ color: methodColor(req.method), fontWeight: 700, fontSize: 11 }}>
            {req.method}
          </Text>
          <span>{req.name}</span>
          {folderName && <Text type="secondary">({folderName})</Text>}
        </Space>
      ),
      searchText: `${req.method} ${req.name} ${folderName ?? ''}`.toLowerCase(),
    });
    return {
      label: collection.name,
      options: [
        ...collection.requests.map((r) => toOption(r)),
        ...collection.folders.flatMap((f) => f.requests.map((r) => toOption(r, f.name))),
      ],
    };
  });
}

interface CreateFormValues {
  name: string;
  saved_request_id: string;
  vus: number;
  duration_seconds: number;
}

/** Full detail (metrics + raw JSON) for one run — fetched separately from the list since the list may omit `raw_summary`. Polls while the run is non-terminal. */
function RunDetailPanel({
  projectId,
  testId,
  run,
}: {
  projectId: string;
  testId: string;
  run: PerformanceTestRunSummary;
}) {
  const { data: detail } = usePerformanceTestRun(projectId, testId, run.id, {
    poll: NON_TERMINAL_STATUSES.includes(run.status),
  });
  const effective: PerformanceTestRun | PerformanceTestRunSummary = detail ?? run;

  return (
    <div style={{ padding: '8px 24px' }}>
      {effective.status === 'failed' && effective.error_message && (
        <Text type="danger" style={{ display: 'block', marginBottom: 12 }}>
          Error: {effective.error_message}
        </Text>
      )}
      <Descriptions size="small" bordered column={3} style={{ marginBottom: 12 }}>
        <Descriptions.Item label="Requests">{effective.request_count ?? '—'}</Descriptions.Item>
        <Descriptions.Item label="Failed">{effective.failed_count ?? '—'}</Descriptions.Item>
        <Descriptions.Item label="Error rate">{formatErrorRate(effective.error_rate)}</Descriptions.Item>
        <Descriptions.Item label="Avg latency">{formatMs(effective.avg_duration_ms)}</Descriptions.Item>
        <Descriptions.Item label="P95 latency">{formatMs(effective.p95_duration_ms)}</Descriptions.Item>
        <Descriptions.Item label="Requests/sec">{formatRps(effective.requests_per_second)}</Descriptions.Item>
        <Descriptions.Item label="Min latency">{formatMs(effective.min_duration_ms)}</Descriptions.Item>
        <Descriptions.Item label="Max latency">{formatMs(effective.max_duration_ms)}</Descriptions.Item>
        <Descriptions.Item label="Started">{formatDateTime(effective.started_at)}</Descriptions.Item>
      </Descriptions>
      {'raw_summary' in effective && effective.raw_summary ? (
        <Collapse
          size="small"
          items={[
            {
              key: 'raw',
              label: 'Raw k6 summary',
              children: <JsonOrPlainView text={JSON.stringify(effective.raw_summary)} />,
            },
          ]}
        />
      ) : null}
    </div>
  );
}

/** Run history + "Run" trigger for one performance test — rendered as the expanded row content of the main test table. */
function RunsPanel({ projectId, test }: { projectId: string; test: PerformanceTest }) {
  const { message } = AntApp.useApp();
  const queryClient = useQueryClient();
  const { data: runs, isLoading } = usePerformanceTestRuns(projectId, test.id);
  const triggerRun = useTriggerPerformanceTestRun(projectId, test.id);

  // Tracks whichever run (just-triggered, or still in-flight from before a reload) should be
  // live-polled until it reaches a terminal status — see `usePerformanceTestRun`'s poll option.
  const [pollingRunId, setPollingRunId] = useState<string | undefined>(undefined);
  const pollingRun = usePerformanceTestRun(projectId, test.id, pollingRunId, { poll: true });

  useEffect(() => {
    if (pollingRunId || !runs || runs.length === 0) return;
    const latest = runs[0];
    if (NON_TERMINAL_STATUSES.includes(latest.status)) setPollingRunId(latest.id);
    // Only re-derive when the run list identity changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runs]);

  useEffect(() => {
    if (!pollingRun.data) return;
    if (!NON_TERMINAL_STATUSES.includes(pollingRun.data.status)) {
      queryClient.invalidateQueries({ queryKey: performanceTestRunsKey(projectId, test.id) });
      setPollingRunId(undefined);
    }
  }, [pollingRun.data, queryClient, projectId, test.id]);

  const handleRun = async () => {
    try {
      const run = await triggerRun.mutateAsync();
      setPollingRunId(run.id);
      message.success('Performance test run started');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  // Overlay the freshest polled state onto the matching row so status/metrics update live
  // without waiting for the list to be invalidated.
  const rows = useMemo(
    () =>
      (runs ?? []).map((r) => (r.id === pollingRun.data?.id ? { ...r, ...pollingRun.data } : r)),
    [runs, pollingRun.data],
  );

  const columns: ColumnsType<PerformanceTestRunSummary> = [
    { title: 'Status', key: 'status', width: 120, render: (_, r) => statusTag(r.status) },
    { title: 'VUs', dataIndex: 'vus', key: 'vus', width: 70 },
    {
      title: 'Duration',
      dataIndex: 'duration_seconds',
      key: 'duration_seconds',
      width: 90,
      render: (v: number) => `${v}s`,
    },
    { title: 'Started', dataIndex: 'started_at', key: 'started_at', width: 170, render: formatDateTime },
    {
      title: 'Avg latency',
      dataIndex: 'avg_duration_ms',
      key: 'avg_duration_ms',
      width: 110,
      render: formatMs,
    },
    {
      title: 'P95 latency',
      dataIndex: 'p95_duration_ms',
      key: 'p95_duration_ms',
      width: 110,
      render: formatMs,
    },
    {
      title: 'Requests/sec',
      dataIndex: 'requests_per_second',
      key: 'requests_per_second',
      width: 110,
      render: formatRps,
    },
    {
      title: 'Error rate',
      dataIndex: 'error_rate',
      key: 'error_rate',
      width: 100,
      render: formatErrorRate,
    },
  ];

  return (
    <div style={{ padding: '8px 16px' }}>
      <Space style={{ marginBottom: 12 }}>
        <span data-testid={`run-test-button-${test.id}`}>
          <Button
            type="primary"
            size="small"
            icon={<ThunderboltOutlined />}
            loading={triggerRun.isPending}
            onClick={handleRun}
          >
            Run
          </Button>
        </span>
      </Space>
      <Table<PerformanceTestRunSummary>
        rowKey="id"
        size="small"
        columns={columns}
        dataSource={rows}
        loading={isLoading}
        pagination={rows.length > 10 ? { pageSize: 10 } : false}
        locale={{ emptyText: <Empty description="No runs yet." image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
        expandable={{
          expandedRowRender: (record) => (
            <RunDetailPanel projectId={projectId} testId={test.id} run={record} />
          ),
        }}
      />
    </div>
  );
}

/**
 * Sprint 10: Performance Testing ("Performer") — pick an already-saved API
 * Performer request, configure a k6 load test (virtual users + duration),
 * run it, and watch results (avg/p95 latency, requests/sec, error rate)
 * stream in, with full run history retained per test.
 */
export default function PerformancePage() {
  const { projectId } = useParams();
  const { message } = AntApp.useApp();

  const { data: tests, isLoading: testsLoading } = usePerformanceTests(projectId);
  const { data: savedRequests } = useSavedRequests(projectId);
  const { data: tree, isLoading: treeLoading } = useApiCollectionsTree(projectId);

  const createTest = useCreatePerformanceTest(projectId);
  const deleteTest = useDeletePerformanceTest(projectId);

  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm<CreateFormValues>();

  const savedRequestById = useMemo(() => {
    const map = new Map<string, SavedApiRequest>();
    for (const r of savedRequests ?? []) map.set(r.id, r);
    return map;
  }, [savedRequests]);

  const requestOptionGroups = useMemo(() => buildRequestOptionGroups(tree ?? []), [tree]);

  const openCreate = () => {
    form.resetFields();
    form.setFieldsValue({ vus: 10, duration_seconds: 30 });
    setModalOpen(true);
  };

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      await createTest.mutateAsync({
        name: values.name,
        saved_request_id: values.saved_request_id,
        vus: values.vus,
        duration_seconds: values.duration_seconds,
      });
      message.success('Performance test created');
      setModalOpen(false);
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteTest.mutateAsync(id);
      message.success('Performance test deleted');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const columns: ColumnsType<PerformanceTest> = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    {
      title: 'Target request',
      key: 'target',
      render: (_, record) => {
        const req = savedRequestById.get(record.saved_request_id);
        if (!req) {
          return <Text type="secondary">{record.saved_request_id}</Text>;
        }
        return (
          <Space size={6}>
            <Text style={{ color: methodColor(req.method), fontWeight: 700, fontSize: 12 }}>
              {req.method}
            </Text>
            <Text ellipsis style={{ maxWidth: 260 }}>
              {req.name}
            </Text>
          </Space>
        );
      },
    },
    { title: 'VUs', dataIndex: 'vus', key: 'vus', width: 80 },
    {
      title: 'Duration',
      dataIndex: 'duration_seconds',
      key: 'duration_seconds',
      width: 100,
      render: (v: number) => `${v}s`,
    },
    { title: 'Created', dataIndex: 'created_at', key: 'created_at', width: 170, render: formatDateTime },
    {
      title: '',
      key: 'actions',
      width: 64,
      render: (_, record) => (
        <Popconfirm
          title="Delete this performance test? Its run history will be deleted too."
          okText="Delete"
          okButtonProps={{ danger: true }}
          onConfirm={() => handleDelete(record.id)}
        >
          <span data-testid={`delete-performance-test-button-${record.id}`}>
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
              loading={deleteTest.isPending && deleteTest.variables === record.id}
              onClick={(e) => e.stopPropagation()}
            />
          </span>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>
          Performance Testing
        </Title>
        <span data-testid="new-performance-test-button">
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            New Performance Test
          </Button>
        </span>
      </Space>

      <Card size="small">
        <Table<PerformanceTest>
          rowKey="id"
          columns={columns}
          dataSource={tests ?? []}
          loading={testsLoading}
          locale={{
            emptyText: (
              <Empty description="No performance tests yet. Create one from a saved API Performer request." />
            ),
          }}
          expandable={{
            expandedRowRender: (record) =>
              projectId ? <RunsPanel projectId={projectId} test={record} /> : null,
          }}
        />
      </Card>

      <Modal
        title="New Performance Test"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        confirmLoading={createTest.isPending}
        okText="Create"
        destroyOnHidden
        width={560}
      >
        <Form<CreateFormValues> form={form} layout="vertical">
          <Form.Item name="name" label="Name" rules={[{ required: true, message: 'Enter a name' }]}>
            <Input placeholder="Checkout API load test" data-testid="performance-test-name-input" />
          </Form.Item>
          <Form.Item
            name="saved_request_id"
            label="Saved request"
            rules={[{ required: true, message: 'Select a saved request' }]}
            extra={
              requestOptionGroups.every((g) => g.options.length === 0) && !treeLoading
                ? 'No saved requests yet — save one in API Performer first.'
                : undefined
            }
          >
            <Select<string>
              placeholder="Select a saved request"
              showSearch
              loading={treeLoading}
              options={requestOptionGroups}
              filterOption={(input, option) => {
                const opt = option as unknown as { searchText?: string } | undefined;
                return !!opt?.searchText?.includes(input.toLowerCase());
              }}
              data-testid="performance-test-request-select"
            />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="vus"
                label="Virtual users"
                rules={[{ required: true, message: 'Enter a VU count' }]}
              >
                <InputNumber
                  min={1}
                  max={500}
                  style={{ width: '100%' }}
                  data-testid="performance-test-vus-input"
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="duration_seconds"
                label="Duration (seconds)"
                rules={[{ required: true, message: 'Enter a duration' }]}
              >
                <InputNumber
                  min={1}
                  max={3600}
                  style={{ width: '100%' }}
                  data-testid="performance-test-duration-input"
                />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>
    </div>
  );
}
