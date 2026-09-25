import { useState } from 'react';
import {
  App as AntApp,
  Alert,
  Button,
  Col,
  Collapse,
  Empty,
  Input,
  List,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import { DeleteOutlined, PlusOutlined, SendOutlined } from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import { KeyValueListEditor } from '../../components/KeyValueListEditor';
import { useEnvironments } from '../../hooks/useEnvironments';
import {
  useCreateSavedRequest,
  useDeleteSavedRequest,
  useExecuteAdHocRequest,
  useSavedRequests,
  useUpdateSavedRequest,
} from '../../hooks/useApiPerformer';
import { ApiError } from '../../api/client';
import type { ApiExecuteResult, ApiRequestMethod, SavedApiRequest } from '../../api/types';

const { Title, Text } = Typography;

const METHODS: ApiRequestMethod[] = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'];

const METHOD_COLORS: Record<ApiRequestMethod, string> = {
  GET: 'blue',
  POST: 'green',
  PUT: 'orange',
  PATCH: 'purple',
  DELETE: 'red',
  HEAD: 'default',
  OPTIONS: 'default',
};

interface BuilderState {
  method: ApiRequestMethod;
  url: string;
  environmentId: string | undefined;
  headers: Record<string, string>;
  queryParams: Record<string, string>;
  body: string;
}

const BLANK_BUILDER: BuilderState = {
  method: 'GET',
  url: '',
  environmentId: undefined,
  headers: {},
  queryParams: {},
  body: '',
};

function statusTagColor(statusCode: number | null): string {
  if (statusCode === null) return 'error';
  if (statusCode >= 200 && statusCode < 300) return 'success';
  if (statusCode >= 300 && statusCode < 400) return 'blue';
  if (statusCode >= 400 && statusCode < 500) return 'warning';
  return 'error';
}

function formatBody(body: string): string {
  if (!body) return '';
  try {
    return JSON.stringify(JSON.parse(body), null, 2);
  } catch {
    return body;
  }
}

/**
 * Sprint 8: API Performer. A built-in, Postman-lite tool: builder on the
 * right (method/URL/environment/headers/query params/body), saved-request
 * list on the left, response panel below the builder. Ad-hoc "Send" never
 * requires saving first — saving is a separate, optional action.
 */
export default function ApiPerformerPage() {
  const { projectId } = useParams();
  const { message } = AntApp.useApp();

  const { data: savedRequests, isLoading: savedRequestsLoading } = useSavedRequests(projectId);
  const { data: environments, isLoading: environmentsLoading } = useEnvironments(projectId);

  const createSavedRequest = useCreateSavedRequest(projectId);
  const updateSavedRequest = useUpdateSavedRequest(projectId);
  const deleteSavedRequest = useDeleteSavedRequest(projectId);
  const executeAdHoc = useExecuteAdHocRequest(projectId);

  const [builder, setBuilder] = useState<BuilderState>(BLANK_BUILDER);
  const [loadedRequest, setLoadedRequest] = useState<SavedApiRequest | null>(null);
  const [response, setResponse] = useState<ApiExecuteResult | null>(null);
  const [saveAsModalOpen, setSaveAsModalOpen] = useState(false);
  const [newRequestName, setNewRequestName] = useState('');

  const handleNewRequest = () => {
    setBuilder(BLANK_BUILDER);
    setLoadedRequest(null);
    setResponse(null);
  };

  const handleLoadRequest = (req: SavedApiRequest) => {
    setLoadedRequest(req);
    setBuilder({
      method: req.method as ApiRequestMethod,
      url: req.url,
      environmentId: req.environment_id ?? undefined,
      headers: req.headers,
      queryParams: req.query_params,
      body: req.body ?? '',
    });
    setResponse(null);
  };

  const handleDelete = async (requestId: string) => {
    try {
      await deleteSavedRequest.mutateAsync(requestId);
      message.success('Request deleted');
      if (loadedRequest?.id === requestId) {
        handleNewRequest();
      }
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleSend = async () => {
    if (!builder.url.trim()) {
      message.warning('Enter a URL');
      return;
    }
    try {
      const result = await executeAdHoc.mutateAsync({
        method: builder.method,
        url: builder.url,
        headers: builder.headers,
        query_params: builder.queryParams,
        body: builder.body || undefined,
        environment_id: builder.environmentId,
      });
      setResponse(result);
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const buildSaveInput = () => ({
    method: builder.method,
    url: builder.url,
    headers: builder.headers,
    query_params: builder.queryParams,
    body: builder.body || undefined,
    environment_id: builder.environmentId,
  });

  const handleSaveInPlace = async () => {
    if (!loadedRequest) return;
    try {
      const updated = await updateSavedRequest.mutateAsync({
        id: loadedRequest.id,
        input: buildSaveInput(),
      });
      setLoadedRequest(updated);
      message.success('Request saved');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const openSaveAsModal = () => {
    setNewRequestName(loadedRequest ? `${loadedRequest.name} (copy)` : '');
    setSaveAsModalOpen(true);
  };

  const handleSaveAsNew = async () => {
    if (!newRequestName.trim()) {
      message.warning('Enter a name');
      return;
    }
    try {
      const created = await createSavedRequest.mutateAsync({
        name: newRequestName.trim(),
        ...buildSaveInput(),
      });
      setLoadedRequest(created);
      setSaveAsModalOpen(false);
      message.success('Request saved');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const headerEntries = Object.entries(response?.headers ?? {});

  return (
    <div>
      <Title level={3} style={{ marginBottom: 16 }}>
        API Performer
      </Title>

      <Row gutter={16}>
        <Col span={7}>
          <Space style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
            <Text strong>Saved Requests</Text>
            <span data-testid="new-request-button">
              <Button size="small" icon={<PlusOutlined />} onClick={handleNewRequest}>
                New Request
              </Button>
            </span>
          </Space>
          <List
            loading={savedRequestsLoading}
            dataSource={savedRequests ?? []}
            locale={{ emptyText: <Empty description="No saved requests yet." /> }}
            renderItem={(req) => (
              <List.Item
                key={req.id}
                data-testid={`saved-request-${req.id}`}
                onClick={() => handleLoadRequest(req)}
                style={{
                  cursor: 'pointer',
                  paddingLeft: 8,
                  paddingRight: 8,
                  background: loadedRequest?.id === req.id ? '#f0f5ff' : undefined,
                }}
                actions={[
                  <Popconfirm
                    key="delete"
                    title="Delete this request?"
                    okText="Delete"
                    okButtonProps={{ danger: true }}
                    onConfirm={(e) => {
                      e?.stopPropagation();
                      handleDelete(req.id);
                    }}
                  >
                    <span data-testid={`delete-request-button-${req.id}`}>
                      <Button
                        type="text"
                        danger
                        size="small"
                        icon={<DeleteOutlined />}
                        loading={deleteSavedRequest.isPending && deleteSavedRequest.variables === req.id}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </span>
                  </Popconfirm>,
                ]}
              >
                <Space size={8}>
                  <Tag color={METHOD_COLORS[req.method as ApiRequestMethod] ?? 'default'}>
                    {req.method}
                  </Tag>
                  <Text ellipsis style={{ maxWidth: 140 }}>
                    {req.name}
                  </Text>
                </Space>
              </List.Item>
            )}
          />
        </Col>

        <Col span={17}>
          <Space.Compact style={{ width: '100%', marginBottom: 4 }}>
            <Select
              value={builder.method}
              style={{ width: 120 }}
              options={METHODS.map((m) => ({ value: m, label: m }))}
              onChange={(method) => setBuilder((b) => ({ ...b, method }))}
              data-testid="request-method-select"
            />
            <Input
              placeholder="https://api.example.com/resource"
              value={builder.url}
              onChange={(e) => setBuilder((b) => ({ ...b, url: e.target.value }))}
              data-testid="request-url-input"
            />
          </Space.Compact>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Use {'{{base_url}}'} or {'{{VARIABLE_NAME}}'} to reference the selected environment.
          </Text>

          <div style={{ marginTop: 12, marginBottom: 12 }}>
            <Space direction="vertical" size={4} style={{ width: '100%' }}>
              <Text strong>Environment</Text>
              <Select
                allowClear
                placeholder="No environment"
                style={{ width: 280 }}
                loading={environmentsLoading}
                value={builder.environmentId}
                options={(environments ?? []).map((e) => ({ value: e.id, label: e.name }))}
                onChange={(environmentId) => setBuilder((b) => ({ ...b, environmentId }))}
                data-testid="request-environment-select"
              />
            </Space>
          </div>

          <Tabs
            items={[
              {
                key: 'headers',
                label: 'Headers',
                children: (
                  <KeyValueListEditor
                    value={builder.headers}
                    onChange={(headers) => setBuilder((b) => ({ ...b, headers }))}
                  />
                ),
              },
              {
                key: 'query',
                label: 'Query Params',
                children: (
                  <KeyValueListEditor
                    value={builder.queryParams}
                    onChange={(queryParams) => setBuilder((b) => ({ ...b, queryParams }))}
                  />
                ),
              },
              {
                key: 'body',
                label: 'Body',
                children: (
                  <Input.TextArea
                    value={builder.body}
                    onChange={(e) => setBuilder((b) => ({ ...b, body: e.target.value }))}
                    autoSize={{ minRows: 6, maxRows: 16 }}
                    placeholder="Request body (raw)"
                    style={{ fontFamily: 'monospace', fontSize: 12 }}
                    data-testid="request-body-textarea"
                  />
                ),
              },
            ]}
          />

          <Space style={{ marginTop: 12, marginBottom: 20 }}>
            <span data-testid="send-request-button">
              <Button
                type="primary"
                icon={<SendOutlined />}
                loading={executeAdHoc.isPending}
                onClick={handleSend}
              >
                Send
              </Button>
            </span>
            {loadedRequest ? (
              <span data-testid="save-request-button">
                <Button loading={updateSavedRequest.isPending} onClick={handleSaveInPlace}>
                  Save
                </Button>
              </span>
            ) : null}
            <span data-testid={loadedRequest ? 'save-as-new-request-button' : 'save-request-button'}>
              <Button onClick={openSaveAsModal}>{loadedRequest ? 'Save as New' : 'Save'}</Button>
            </span>
          </Space>

          {loadedRequest && (
            <Text type="secondary" style={{ display: 'block', marginBottom: 12, fontSize: 12 }}>
              Editing saved request: <Text strong>{loadedRequest.name}</Text>
            </Text>
          )}

          <Title level={5}>Response</Title>
          {executeAdHoc.isPending && <Text type="secondary">Sending…</Text>}
          {!executeAdHoc.isPending && response && (
            <>
              {response.error ? (
                <Alert type="error" showIcon message="Request failed" description={response.error} />
              ) : (
                <>
                  <Space style={{ marginBottom: 8 }} align="center">
                    <span data-testid="response-status">
                      <Tag color={statusTagColor(response.status_code)}>
                        {response.status_code ?? 'No response'}
                      </Tag>
                    </span>
                    <Text type="secondary">{response.duration_ms} ms</Text>
                  </Space>
                  {headerEntries.length > 0 && (
                    <Collapse
                      size="small"
                      style={{ marginBottom: 8 }}
                      items={[
                        {
                          key: 'headers',
                          label: 'Response Headers',
                          children: (
                            <Space direction="vertical" size={2}>
                              {headerEntries.map(([k, v]) => (
                                <Text key={k} code style={{ fontSize: 12 }}>
                                  {k}: {v}
                                </Text>
                              ))}
                            </Space>
                          ),
                        },
                      ]}
                    />
                  )}
                  <pre
                    data-testid="response-body"
                    style={{
                      fontFamily: 'monospace',
                      fontSize: 12,
                      background: '#f5f5f5',
                      padding: 12,
                      borderRadius: 4,
                      maxHeight: 400,
                      overflow: 'auto',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                    }}
                  >
                    {formatBody(response.body)}
                  </pre>
                </>
              )}
            </>
          )}
          {!executeAdHoc.isPending && !response && (
            <Text type="secondary">Send a request to see the response here.</Text>
          )}
        </Col>
      </Row>

      <Modal
        title={loadedRequest ? 'Save as New Request' : 'Save Request'}
        open={saveAsModalOpen}
        onOk={handleSaveAsNew}
        onCancel={() => setSaveAsModalOpen(false)}
        confirmLoading={createSavedRequest.isPending}
        okText="Save"
        destroyOnHidden
      >
        <Input
          placeholder="Request name"
          value={newRequestName}
          onChange={(e) => setNewRequestName(e.target.value)}
          data-testid="save-request-name-input"
        />
      </Modal>
    </div>
  );
}
