import type { ReactNode } from 'react';
import { Button, Divider, Empty, Input, InputNumber, Select, Space, Switch, Tag, Typography } from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import type { TestingLevel, TestingLevelScope, TestStrategyPayload } from '../../api/types';

const { Title, Paragraph, Text } = Typography;

const LEVEL_LABELS: Record<TestingLevel, string> = {
  functional: 'Functional',
  api: 'API',
  ui: 'UI',
  integration: 'Integration',
  security: 'Security',
  performance: 'Performance',
  regression: 'Regression',
};

const LEVEL_OPTIONS = (Object.keys(LEVEL_LABELS) as TestingLevel[]).map((value) => ({
  value,
  label: LEVEL_LABELS[value],
}));

interface SectionProps {
  title: string;
  description?: string;
  children: ReactNode;
}

function Section({ title, description, children }: SectionProps) {
  return (
    <div style={{ marginBottom: 24 }}>
      <Title level={5} style={{ marginBottom: 4 }}>
        {title}
      </Title>
      {description && (
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
          {description}
        </Text>
      )}
      {children}
    </div>
  );
}

function LevelList({
  levels,
  editable,
  onChange,
}: {
  levels: TestingLevelScope[];
  editable: boolean;
  onChange: (levels: TestingLevelScope[]) => void;
}) {
  const update = (index: number, patch: Partial<TestingLevelScope>) => {
    onChange(levels.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  };
  const remove = (index: number) => onChange(levels.filter((_, i) => i !== index));

  if (levels.length === 0) {
    return editable ? null : (
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="None identified" style={{ margin: '8px 0' }} />
    );
  }

  if (!editable) {
    return (
      <Space direction="vertical" size={8} style={{ width: '100%' }}>
        {levels.map((l, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
            <Text strong style={{ width: 110 }}>
              {LEVEL_LABELS[l.level]}
            </Text>
            <Tag color={l.applicable ? 'green' : 'default'}>{l.applicable ? 'Applicable' : 'Not applicable'}</Tag>
            {l.applicable && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                ~{l.estimated_scenario_count} scenario{l.estimated_scenario_count === 1 ? '' : 's'}
              </Text>
            )}
            {l.notes && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {l.notes}
              </Text>
            )}
          </div>
        ))}
      </Space>
    );
  }

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      {levels.map((l, i) => (
        <Space key={i} align="start" wrap style={{ width: '100%' }}>
          <Select<TestingLevel>
            value={l.level}
            style={{ width: 130 }}
            onChange={(value) => update(i, { level: value })}
            options={LEVEL_OPTIONS}
          />
          <Space size={4} align="center">
            <Text style={{ fontSize: 12 }}>Applicable</Text>
            <Switch checked={l.applicable} onChange={(checked) => update(i, { applicable: checked })} />
          </Space>
          <Space size={4} align="center">
            <Text style={{ fontSize: 12 }}>Est. scenarios</Text>
            <InputNumber
              min={0}
              value={l.estimated_scenario_count}
              onChange={(value) => update(i, { estimated_scenario_count: value ?? 0 })}
              style={{ width: 90 }}
            />
          </Space>
          <Input
            placeholder="Notes (optional)"
            value={l.notes}
            onChange={(e) => update(i, { notes: e.target.value })}
            style={{ width: 240 }}
          />
          <Button type="text" danger icon={<DeleteOutlined />} onClick={() => remove(i)} />
        </Space>
      ))}
    </Space>
  );
}

function StringList({
  items,
  editable,
  onChange,
  placeholder,
}: {
  items: string[];
  editable: boolean;
  onChange: (items: string[]) => void;
  placeholder?: string;
}) {
  const update = (index: number, value: string) => onChange(items.map((item, i) => (i === index ? value : item)));
  const remove = (index: number) => onChange(items.filter((_, i) => i !== index));

  if (items.length === 0 && !editable) {
    return (
      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="None identified" style={{ margin: '8px 0' }} />
    );
  }

  if (!editable) {
    return (
      <ul style={{ margin: 0, paddingLeft: 20 }}>
        {items.map((item, i) => (
          <li key={i}>
            <Text>{item}</Text>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <Space direction="vertical" size={8} style={{ width: '100%' }}>
      {items.map((item, i) => (
        <Space key={i} style={{ width: '100%' }}>
          <Input
            style={{ width: 420, maxWidth: '100%' }}
            placeholder={placeholder}
            value={item}
            onChange={(e) => update(i, e.target.value)}
          />
          <Button type="text" danger icon={<DeleteOutlined />} onClick={() => remove(i)} />
        </Space>
      ))}
    </Space>
  );
}

export interface TestStrategyPayloadViewProps {
  payload: TestStrategyPayload;
  editable: boolean;
  onChange: (payload: TestStrategyPayload) => void;
}

/**
 * Renders the structured test strategy payload: a summary, a compact list of
 * testing-level scopes (level, applicable/not, estimated scenario count,
 * notes only when non-empty), the environments/test-data/dependencies
 * string lists, and the automation/manual scope-notes free text.
 */
export function TestStrategyPayloadView({ payload, editable, onChange }: TestStrategyPayloadViewProps) {
  const set = <K extends keyof TestStrategyPayload>(key: K, value: TestStrategyPayload[K]) =>
    onChange({ ...payload, [key]: value });

  return (
    <div>
      <Section title="Summary">
        {editable ? (
          <Input.TextArea rows={3} value={payload.summary} onChange={(e) => set('summary', e.target.value)} />
        ) : (
          <Paragraph>{payload.summary || <Text type="secondary">—</Text>}</Paragraph>
        )}
      </Section>

      <Divider style={{ margin: '16px 0' }} />

      <Section title="Testing Levels" description="Which levels of testing apply, and roughly how much.">
        <LevelList levels={payload.levels} editable={editable} onChange={(levels) => set('levels', levels)} />
        {editable && (
          <Button
            type="dashed"
            size="small"
            icon={<PlusOutlined />}
            onClick={() =>
              set('levels', [
                ...payload.levels,
                { level: 'functional', applicable: false, estimated_scenario_count: 0, notes: '' },
              ])
            }
            style={{ marginTop: 8 }}
          >
            Add level
          </Button>
        )}
      </Section>

      <Section title="Environments">
        <StringList
          items={payload.environments}
          editable={editable}
          onChange={(items) => set('environments', items)}
          placeholder="e.g. Staging"
        />
        {editable && (
          <Button
            type="dashed"
            size="small"
            icon={<PlusOutlined />}
            onClick={() => set('environments', [...payload.environments, ''])}
            style={{ marginTop: 8 }}
          >
            Add environment
          </Button>
        )}
      </Section>

      <Section title="Test Data Requirements">
        <StringList
          items={payload.test_data_requirements}
          editable={editable}
          onChange={(items) => set('test_data_requirements', items)}
          placeholder="e.g. Seeded accounts with expired subscriptions"
        />
        {editable && (
          <Button
            type="dashed"
            size="small"
            icon={<PlusOutlined />}
            onClick={() => set('test_data_requirements', [...payload.test_data_requirements, ''])}
            style={{ marginTop: 8 }}
          >
            Add requirement
          </Button>
        )}
      </Section>

      <Section title="Dependencies">
        <StringList
          items={payload.dependencies}
          editable={editable}
          onChange={(items) => set('dependencies', items)}
          placeholder="e.g. Payment gateway sandbox"
        />
        {editable && (
          <Button
            type="dashed"
            size="small"
            icon={<PlusOutlined />}
            onClick={() => set('dependencies', [...payload.dependencies, ''])}
            style={{ marginTop: 8 }}
          >
            Add dependency
          </Button>
        )}
      </Section>

      <Section title="Automation Scope Notes">
        {editable ? (
          <Input.TextArea
            rows={2}
            value={payload.automation_scope_notes}
            onChange={(e) => set('automation_scope_notes', e.target.value)}
          />
        ) : (
          <Paragraph>{payload.automation_scope_notes || <Text type="secondary">—</Text>}</Paragraph>
        )}
      </Section>

      <Section title="Manual Scope Notes">
        {editable ? (
          <Input.TextArea
            rows={2}
            value={payload.manual_scope_notes}
            onChange={(e) => set('manual_scope_notes', e.target.value)}
          />
        ) : (
          <Paragraph>{payload.manual_scope_notes || <Text type="secondary">—</Text>}</Paragraph>
        )}
      </Section>
    </div>
  );
}
