import { useEffect, useState } from 'react';
import { Alert, App as AntApp, Button, Card, Collapse, Empty, Input, Select, Skeleton, Space, Tag, Typography } from 'antd';
import { ThunderboltOutlined } from '@ant-design/icons';
import {
  useApproveAutomationScript,
  useAutomationScript,
  useAutomationScriptVersions,
  useGenerateAutomationScript,
  useUpdateAutomationScript,
} from '../../hooks/useAutomationScript';
import { useEnvironments } from '../../hooks/useEnvironments';
import { StatusBadge } from '../../components/StatusBadge';
import { ApiError } from '../../api/client';

const { Title, Text } = Typography;

function ScriptVersionHistoryBody({
  projectId,
  testCaseId,
  enabled,
}: {
  projectId: string | undefined;
  testCaseId: string | undefined;
  enabled: boolean;
}) {
  const { data: versions, isLoading } = useAutomationScriptVersions(projectId, testCaseId, { enabled });
  if (!enabled) return null;
  if (isLoading || !versions) {
    return <Skeleton active paragraph={{ rows: 3 }} />;
  }
  if (versions.length === 0) {
    return <Text type="secondary">No prior versions.</Text>;
  }
  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      {versions.map((v) => (
        <div key={v.version_number} style={{ borderLeft: '2px solid #f0f0f0', paddingLeft: 12 }}>
          <Space wrap>
            <Text strong>Version {v.version_number}</Text>
            <Tag color={v.source === 'ai' ? 'purple' : 'blue'}>{v.source === 'ai' ? 'AI' : 'Human'}</Tag>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {v.created_by} · {new Date(v.created_at).toLocaleString()}
            </Text>
          </Space>
        </div>
      ))}
    </Space>
  );
}

/**
 * Generate/edit/approve section for a test case's Playwright automation
 * script. Deliberately renders the code as a plain monospace
 * `Input.TextArea` (not a Monaco-style editor) to keep bundle size/scope down
 * this sprint.
 */
export function AutomationScriptSection({
  projectId,
  testCaseId,
  canEdit,
}: {
  projectId: string | undefined;
  testCaseId: string | undefined;
  canEdit: boolean;
}) {
  const { data: script, isLoading } = useAutomationScript(projectId, testCaseId);
  const { data: environments, isLoading: environmentsLoading } = useEnvironments(projectId);
  const generate = useGenerateAutomationScript(projectId, testCaseId);
  const update = useUpdateAutomationScript(projectId, testCaseId);
  const approve = useApproveAutomationScript(projectId, testCaseId);
  const { message } = AntApp.useApp();

  const [environmentId, setEnvironmentId] = useState<string | undefined>();
  const [code, setCode] = useState('');
  const [historyKeys, setHistoryKeys] = useState<string[]>([]);
  const historyOpen = historyKeys.includes('history');

  useEffect(() => {
    if (script) setCode(script.current_version.code);
  }, [script]);

  const hasEnvironments = (environments?.length ?? 0) > 0;
  const isDirty = !!script && code !== script.current_version.code;

  const handleGenerate = async () => {
    try {
      await generate.mutateAsync({ environment_id: environmentId });
      message.success(script ? 'Script regenerated' : 'Script generated');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleSave = async () => {
    try {
      await update.mutateAsync({ code });
      message.success('Script saved');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleApprove = async () => {
    try {
      await approve.mutateAsync();
      message.success('Script approved');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  return (
    <div>
      <div
        style={{
          marginTop: 24,
          marginBottom: 12,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 8,
        }}
      >
        <Title level={4} style={{ margin: 0 }}>
          Automation Script
        </Title>
        {canEdit && (
          <Space wrap>
            <span data-testid="script-environment-select">
              <Select
                allowClear
                placeholder="Environment (context)"
                style={{ width: 200 }}
                value={environmentId}
                loading={environmentsLoading}
                options={(environments ?? []).map((e) => ({ value: e.id, label: e.name }))}
                onChange={setEnvironmentId}
              />
            </span>
            <span data-testid="generate-script-button">
              <Button
                type="primary"
                icon={<ThunderboltOutlined />}
                onClick={handleGenerate}
                loading={generate.isPending}
                disabled={!hasEnvironments}
              >
                {script ? 'Regenerate Script' : 'Generate Script'}
              </Button>
            </span>
          </Space>
        )}
      </div>

      {canEdit && !environmentsLoading && !hasEnvironments && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="No environments yet — add one in Project Settings > Environments to generate an automation script."
        />
      )}

      <Card>
        {isLoading ? (
          <Skeleton active paragraph={{ rows: 4 }} />
        ) : !script ? (
          <Empty
            description={
              canEdit ? 'No automation script yet — click Generate Script to create one.' : 'No automation script yet.'
            }
          />
        ) : (
          <div>
            <Space style={{ marginBottom: 12 }} align="center" wrap>
              <StatusBadge status={script.status} />
              <Tag color={script.current_version.source === 'ai' ? 'purple' : 'blue'}>
                {script.current_version.source === 'ai' ? 'AI' : 'Human'}
              </Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                v{script.current_version.version_number} · {script.current_version.created_by} ·{' '}
                {new Date(script.current_version.created_at).toLocaleString()}
              </Text>
            </Space>
            <Input.TextArea
              data-testid="script-code-textarea"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              readOnly={!canEdit}
              autoSize={{ minRows: 10, maxRows: 30 }}
              style={{ fontFamily: 'monospace', fontSize: 12 }}
            />
            {canEdit && (
              <Space style={{ marginTop: 12 }}>
                <span data-testid="save-script-button">
                  <Button onClick={handleSave} disabled={!isDirty} loading={update.isPending}>
                    Save
                  </Button>
                </span>
                {script.status === 'draft' && (
                  <span data-testid="approve-script-button">
                    <Button type="primary" onClick={handleApprove} loading={approve.isPending} disabled={isDirty}>
                      Approve
                    </Button>
                  </span>
                )}
              </Space>
            )}
          </div>
        )}
      </Card>

      {script && (
        <div style={{ marginTop: 24 }}>
          <Collapse
            activeKey={historyKeys}
            onChange={(keys) => setHistoryKeys(Array.isArray(keys) ? keys : [keys])}
            items={[
              {
                key: 'history',
                label: 'Version History',
                children: <ScriptVersionHistoryBody projectId={projectId} testCaseId={testCaseId} enabled={historyOpen} />,
              },
            ]}
          />
        </div>
      )}
    </div>
  );
}
