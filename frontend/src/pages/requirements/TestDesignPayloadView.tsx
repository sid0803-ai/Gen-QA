import { Button, Divider, Empty, Input, Select, Space, Switch, Tag, Typography } from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import {
  CATEGORY_COLORS,
  CATEGORY_LABELS,
  CATEGORY_OPTIONS,
  SEVERITY_COLORS,
  SEVERITY_LABELS,
  SEVERITY_OPTIONS,
  TESTING_LEVEL_LABELS,
  TESTING_LEVEL_OPTIONS,
} from '../../api/testCaseOptions';
import { PRIORITY_OPTIONS } from '../../api/priority';
import { TEST_DESIGN_SCOPE_OPTIONS } from '../../api/testDesign';
import type {
  Priority,
  ScenarioCategory,
  Severity,
  TestDesignPayload,
  TestDesignScenario,
  TestDesignScope,
  TestingLevel,
} from '../../api/types';

const { Title, Paragraph, Text } = Typography;

const PRIORITY_COLORS: Record<Priority, string> = {
  low: 'blue',
  medium: 'gold',
  high: 'orange',
  critical: 'red',
};

function emptyScenario(): TestDesignScenario {
  return {
    title: '',
    category: 'positive',
    testing_level: 'functional',
    priority: 'medium',
    severity: 'major',
    preconditions: '',
    test_data: '',
    steps: [],
    expected_result: '',
    business_rule: '',
    automation_candidate: false,
    include: true,
  };
}

function StepsList({
  steps,
  editable,
  onChange,
}: {
  steps: string[];
  editable: boolean;
  onChange: (steps: string[]) => void;
}) {
  const update = (index: number, value: string) => onChange(steps.map((s, i) => (i === index ? value : s)));
  const remove = (index: number) => onChange(steps.filter((_, i) => i !== index));

  if (steps.length === 0 && !editable) {
    return <Text type="secondary">—</Text>;
  }

  if (!editable) {
    return (
      <ol style={{ margin: 0, paddingLeft: 20 }}>
        {steps.map((step, i) => (
          <li key={i}>
            <Text>{step}</Text>
          </li>
        ))}
      </ol>
    );
  }

  return (
    <Space direction="vertical" size={6} style={{ width: '100%' }}>
      {steps.map((step, i) => (
        <Space key={i} style={{ width: '100%' }}>
          <Text type="secondary" style={{ width: 20 }}>
            {i + 1}.
          </Text>
          <Input
            style={{ width: 400, maxWidth: '100%' }}
            value={step}
            onChange={(e) => update(i, e.target.value)}
            placeholder="Step"
          />
          <Button type="text" danger icon={<DeleteOutlined />} onClick={() => remove(i)} />
        </Space>
      ))}
      <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => onChange([...steps, ''])}>
        Add step
      </Button>
    </Space>
  );
}

function ScenarioCard({
  scenario,
  editable,
  onChange,
  onRemove,
}: {
  scenario: TestDesignScenario;
  editable: boolean;
  onChange: (patch: Partial<TestDesignScenario>) => void;
  onRemove: () => void;
}) {
  const included = scenario.include;

  return (
    <div style={{ border: '1px solid #f0f0f0', borderRadius: 6, padding: 12, position: 'relative' }}>
      <Space align="start" style={{ width: '100%', justifyContent: 'space-between' }}>
        <div style={{ flex: 1, marginRight: 12 }}>
          {editable ? (
            <Input
              placeholder="Scenario title"
              value={scenario.title}
              onChange={(e) => onChange({ title: e.target.value })}
              style={{ fontWeight: 600 }}
            />
          ) : (
            <Text strong delete={!included}>
              {scenario.title || <Text type="secondary">Untitled scenario</Text>}
            </Text>
          )}
        </div>
        <Space align="center">
          <Text type="secondary" style={{ fontSize: 12 }}>
            Include
          </Text>
          <Switch checked={included} disabled={!editable} onChange={(checked) => onChange({ include: checked })} />
          {editable && <Button type="text" danger icon={<DeleteOutlined />} onClick={onRemove} />}
        </Space>
      </Space>

      <div style={{ opacity: included ? 1 : 0.45, marginTop: 12 }}>
        <Space wrap style={{ marginBottom: 12 }}>
          {editable ? (
            <>
              <Select<ScenarioCategory>
                value={scenario.category}
                style={{ width: 150 }}
                options={CATEGORY_OPTIONS}
                onChange={(value) => onChange({ category: value })}
              />
              <Select<TestingLevel>
                value={scenario.testing_level}
                style={{ width: 130 }}
                options={TESTING_LEVEL_OPTIONS}
                onChange={(value) => onChange({ testing_level: value })}
              />
              <Select<Priority>
                value={scenario.priority}
                style={{ width: 120 }}
                options={PRIORITY_OPTIONS}
                onChange={(value) => onChange({ priority: value })}
              />
              <Select<Severity>
                value={scenario.severity}
                style={{ width: 120 }}
                options={SEVERITY_OPTIONS}
                onChange={(value) => onChange({ severity: value })}
              />
              <Space size={4} align="center">
                <Text style={{ fontSize: 12 }}>Automation candidate</Text>
                <Switch
                  checked={scenario.automation_candidate}
                  onChange={(checked) => onChange({ automation_candidate: checked })}
                />
              </Space>
            </>
          ) : (
            <>
              <Tag color={CATEGORY_COLORS[scenario.category]}>{CATEGORY_LABELS[scenario.category]}</Tag>
              <Tag>{TESTING_LEVEL_LABELS[scenario.testing_level]}</Tag>
              <Tag color={PRIORITY_COLORS[scenario.priority]}>{scenario.priority}</Tag>
              <Tag color={SEVERITY_COLORS[scenario.severity]}>{SEVERITY_LABELS[scenario.severity]}</Tag>
              {scenario.automation_candidate && <Tag color="processing">Automation candidate</Tag>}
              {!included && <Tag>Excluded from approval</Tag>}
            </>
          )}
        </Space>

        <div style={{ marginBottom: 8 }}>
          <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase' }}>
            Preconditions
          </Text>
          {editable ? (
            <Input.TextArea
              rows={2}
              value={scenario.preconditions}
              onChange={(e) => onChange({ preconditions: e.target.value })}
            />
          ) : (
            <Paragraph style={{ marginBottom: 0 }}>{scenario.preconditions || <Text type="secondary">—</Text>}</Paragraph>
          )}
        </div>

        <div style={{ marginBottom: 8 }}>
          <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase' }}>
            Test data
          </Text>
          {editable ? (
            <Input.TextArea
              rows={2}
              value={scenario.test_data}
              onChange={(e) => onChange({ test_data: e.target.value })}
            />
          ) : (
            <Paragraph style={{ marginBottom: 0 }}>{scenario.test_data || <Text type="secondary">—</Text>}</Paragraph>
          )}
        </div>

        <div style={{ marginBottom: 8 }}>
          <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase' }}>
            Steps
          </Text>
          <StepsList steps={scenario.steps} editable={editable} onChange={(steps) => onChange({ steps })} />
        </div>

        <div style={{ marginBottom: 8 }}>
          <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase' }}>
            Expected result
          </Text>
          {editable ? (
            <Input.TextArea
              rows={2}
              value={scenario.expected_result}
              onChange={(e) => onChange({ expected_result: e.target.value })}
            />
          ) : (
            <Paragraph style={{ marginBottom: 0 }}>{scenario.expected_result || <Text type="secondary">—</Text>}</Paragraph>
          )}
        </div>

        <div>
          <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase' }}>
            Business rule
          </Text>
          {editable ? (
            <Input.TextArea
              rows={2}
              value={scenario.business_rule}
              onChange={(e) => onChange({ business_rule: e.target.value })}
            />
          ) : (
            <Paragraph style={{ marginBottom: 0 }}>{scenario.business_rule || <Text type="secondary">—</Text>}</Paragraph>
          )}
        </div>
      </div>
    </div>
  );
}

export interface TestDesignPayloadViewProps {
  payload: TestDesignPayload;
  editable: boolean;
  onChange: (payload: TestDesignPayload) => void;
}

/**
 * Renders the structured test design payload: a summary, the generation
 * scope, then one card per scenario (title/category/testing level/priority/
 * severity as tags, preconditions/test data/expected result/steps laid out
 * legibly, and an `include` switch). Unchecking `include` on an editable
 * scenario greys out its body so it's obvious the scenario won't be
 * promoted into a real Test Case on approve.
 */
export function TestDesignPayloadView({ payload, editable, onChange }: TestDesignPayloadViewProps) {
  const set = <K extends keyof TestDesignPayload>(key: K, value: TestDesignPayload[K]) =>
    onChange({ ...payload, [key]: value });

  const updateScenario = (index: number, patch: Partial<TestDesignScenario>) => {
    set(
      'scenarios',
      payload.scenarios.map((s, i) => (i === index ? { ...s, ...patch } : s)),
    );
  };
  const removeScenario = (index: number) => {
    set(
      'scenarios',
      payload.scenarios.filter((_, i) => i !== index),
    );
  };

  const includedCount = payload.scenarios.filter((s) => s.include).length;

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <Title level={5} style={{ marginBottom: 4 }}>
          Summary
        </Title>
        {editable ? (
          <Input.TextArea rows={3} value={payload.summary} onChange={(e) => set('summary', e.target.value)} />
        ) : (
          <Paragraph>{payload.summary || <Text type="secondary">—</Text>}</Paragraph>
        )}
      </div>

      <div style={{ marginBottom: 24 }}>
        <Title level={5} style={{ marginBottom: 4 }}>
          Scope
        </Title>
        {editable ? (
          <Select<TestDesignScope>
            value={payload.scope}
            style={{ width: 160 }}
            options={TEST_DESIGN_SCOPE_OPTIONS}
            onChange={(value) => set('scope', value)}
          />
        ) : (
          <Tag>{TEST_DESIGN_SCOPE_OPTIONS.find((o) => o.value === payload.scope)?.label ?? payload.scope}</Tag>
        )}
      </div>

      <Divider style={{ margin: '16px 0' }} />

      <div>
        <Space align="baseline" style={{ marginBottom: 4 }}>
          <Title level={5} style={{ marginBottom: 0 }}>
            Scenarios
          </Title>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {includedCount} of {payload.scenarios.length} included
          </Text>
        </Space>
        {payload.scenarios.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="None identified" style={{ margin: '8px 0' }} />
        ) : (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            {payload.scenarios.map((scenario, i) => (
              <ScenarioCard
                key={i}
                scenario={scenario}
                editable={editable}
                onChange={(patch) => updateScenario(i, patch)}
                onRemove={() => removeScenario(i)}
              />
            ))}
          </Space>
        )}
        {editable && (
          <Button
            type="dashed"
            size="small"
            icon={<PlusOutlined />}
            onClick={() => set('scenarios', [...payload.scenarios, emptyScenario()])}
            style={{ marginTop: 8 }}
          >
            Add scenario
          </Button>
        )}
      </div>
    </div>
  );
}
