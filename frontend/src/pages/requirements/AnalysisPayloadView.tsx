import type { ReactNode } from 'react';
import { Button, Divider, Empty, Input, Select, Space, Tag, Typography } from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import type {
  AmbiguityItem,
  RationaleItem,
  RequirementAnalysisPayload,
  RiskItem,
} from '../../api/types';

const { Title, Paragraph, Text } = Typography;

const SEVERITY_COLORS: Record<RiskItem['severity'], string> = {
  low: 'green',
  medium: 'gold',
  high: 'red',
};

interface SectionProps {
  title: string;
  description?: string;
  empty?: boolean;
  editable?: boolean;
  onAdd?: () => void;
  addLabel?: string;
  children: ReactNode;
}

function Section({ title, description, empty, editable, onAdd, addLabel, children }: SectionProps) {
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
      {empty && !editable ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="None identified"
          style={{ margin: '8px 0' }}
        />
      ) : (
        children
      )}
      {editable && onAdd && (
        <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={onAdd} style={{ marginTop: 8 }}>
          {addLabel ?? 'Add item'}
        </Button>
      )}
    </div>
  );
}

/** Statement + a smaller/secondary rationale line — makes "AI explains why" visible. */
function RationaleList({
  items,
  editable,
  onChange,
}: {
  items: RationaleItem[];
  editable: boolean;
  onChange: (items: RationaleItem[]) => void;
}) {
  const update = (index: number, patch: Partial<RationaleItem>) => {
    onChange(items.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  };
  const remove = (index: number) => onChange(items.filter((_, i) => i !== index));

  if (!editable) {
    return (
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        {items.map((item, i) => (
          <div key={i}>
            <Text>{item.statement}</Text>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>
              {item.rationale}
            </Text>
          </div>
        ))}
      </Space>
    );
  }

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      {items.map((item, i) => (
        <Space key={i} align="start" style={{ width: '100%' }}>
          <Space direction="vertical" size={4} style={{ width: 480, maxWidth: '100%' }}>
            <Input
              placeholder="Statement"
              value={item.statement}
              onChange={(e) => update(i, { statement: e.target.value })}
            />
            <Input
              placeholder="Rationale — why the AI flagged this"
              value={item.rationale}
              onChange={(e) => update(i, { rationale: e.target.value })}
            />
          </Space>
          <Button type="text" danger icon={<DeleteOutlined />} onClick={() => remove(i)} />
        </Space>
      ))}
    </Space>
  );
}

function RiskList({
  items,
  editable,
  onChange,
}: {
  items: RiskItem[];
  editable: boolean;
  onChange: (items: RiskItem[]) => void;
}) {
  const update = (index: number, patch: Partial<RiskItem>) => {
    onChange(items.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  };
  const remove = (index: number) => onChange(items.filter((_, i) => i !== index));

  if (!editable) {
    return (
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        {items.map((item, i) => (
          <div key={i}>
            <Space align="center">
              <Text>{item.statement}</Text>
              <Tag color={SEVERITY_COLORS[item.severity]}>{item.severity.toUpperCase()}</Tag>
            </Space>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>
              {item.rationale}
            </Text>
          </div>
        ))}
      </Space>
    );
  }

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      {items.map((item, i) => (
        <Space key={i} align="start" style={{ width: '100%' }}>
          <Space direction="vertical" size={4} style={{ width: 420, maxWidth: '100%' }}>
            <Input
              placeholder="Statement"
              value={item.statement}
              onChange={(e) => update(i, { statement: e.target.value })}
            />
            <Input
              placeholder="Rationale — why the AI flagged this"
              value={item.rationale}
              onChange={(e) => update(i, { rationale: e.target.value })}
            />
          </Space>
          <Select<RiskItem['severity']>
            value={item.severity}
            style={{ width: 110 }}
            onChange={(value) => update(i, { severity: value })}
            options={[
              { value: 'low', label: 'Low' },
              { value: 'medium', label: 'Medium' },
              { value: 'high', label: 'High' },
            ]}
          />
          <Button type="text" danger icon={<DeleteOutlined />} onClick={() => remove(i)} />
        </Space>
      ))}
    </Space>
  );
}

function AmbiguityList({
  items,
  editable,
  onChange,
}: {
  items: AmbiguityItem[];
  editable: boolean;
  onChange: (items: AmbiguityItem[]) => void;
}) {
  const update = (index: number, patch: Partial<AmbiguityItem>) => {
    onChange(items.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  };
  const remove = (index: number) => onChange(items.filter((_, i) => i !== index));

  if (!editable) {
    return (
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        {items.map((item, i) => (
          <div key={i}>
            <Text>{item.statement}</Text>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>
              Clarify: {item.clarifying_question}
            </Text>
          </div>
        ))}
      </Space>
    );
  }

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      {items.map((item, i) => (
        <Space key={i} align="start" style={{ width: '100%' }}>
          <Space direction="vertical" size={4} style={{ width: 480, maxWidth: '100%' }}>
            <Input
              placeholder="Ambiguous statement"
              value={item.statement}
              onChange={(e) => update(i, { statement: e.target.value })}
            />
            <Input
              placeholder="Clarifying question"
              value={item.clarifying_question}
              onChange={(e) => update(i, { clarifying_question: e.target.value })}
            />
          </Space>
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
}: {
  items: string[];
  editable: boolean;
  onChange: (items: string[]) => void;
}) {
  const update = (index: number, value: string) => {
    onChange(items.map((item, i) => (i === index ? value : item)));
  };
  const remove = (index: number) => onChange(items.filter((_, i) => i !== index));

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
            style={{ width: 480, maxWidth: '100%' }}
            value={item}
            onChange={(e) => update(i, e.target.value)}
          />
          <Button type="text" danger icon={<DeleteOutlined />} onClick={() => remove(i)} />
        </Space>
      ))}
    </Space>
  );
}

export interface AnalysisPayloadViewProps {
  payload: RequirementAnalysisPayload;
  editable: boolean;
  onChange: (payload: RequirementAnalysisPayload) => void;
}

/**
 * Renders the structured AI analysis payload as legible, grouped sections
 * (not a data dump). Each rationale-bearing item shows its statement plus a
 * smaller/secondary rationale line, so the "AI explains why" is visually
 * obvious. When `editable`, every section supports inline edit/add/remove.
 */
export function AnalysisPayloadView({ payload, editable, onChange }: AnalysisPayloadViewProps) {
  const set = <K extends keyof RequirementAnalysisPayload>(
    key: K,
    value: RequirementAnalysisPayload[K],
  ) => onChange({ ...payload, [key]: value });

  return (
    <div>
      <Section title="Summary">
        {editable ? (
          <Input.TextArea
            rows={3}
            value={payload.summary}
            onChange={(e) => set('summary', e.target.value)}
          />
        ) : (
          <Paragraph>{payload.summary || <Text type="secondary">—</Text>}</Paragraph>
        )}
      </Section>

      <Divider style={{ margin: '16px 0' }} />

      <Section
        title="Business Rules"
        empty={payload.business_rules.length === 0}
        editable={editable}
        addLabel="Add business rule"
        onAdd={() => set('business_rules', [...payload.business_rules, { statement: '', rationale: '' }])}
      >
        <RationaleList
          items={payload.business_rules}
          editable={editable}
          onChange={(items) => set('business_rules', items)}
        />
      </Section>

      <Section
        title="Functional Conditions"
        empty={payload.functional_conditions.length === 0}
        editable={editable}
        addLabel="Add condition"
        onAdd={() =>
          set('functional_conditions', [...payload.functional_conditions, { statement: '', rationale: '' }])
        }
      >
        <RationaleList
          items={payload.functional_conditions}
          editable={editable}
          onChange={(items) => set('functional_conditions', items)}
        />
      </Section>

      <Section
        title="Risks"
        description="Severity reflects the AI's assessment of impact if unaddressed."
        empty={payload.risks.length === 0}
        editable={editable}
        addLabel="Add risk"
        onAdd={() =>
          set('risks', [...payload.risks, { statement: '', rationale: '', severity: 'medium' }])
        }
      >
        <RiskList items={payload.risks} editable={editable} onChange={(items) => set('risks', items)} />
      </Section>

      <Section
        title="Ambiguities"
        description="Statements the AI could not resolve confidently, with a suggested clarifying question."
        empty={payload.ambiguities.length === 0}
        editable={editable}
        addLabel="Add ambiguity"
        onAdd={() =>
          set('ambiguities', [...payload.ambiguities, { statement: '', clarifying_question: '' }])
        }
      >
        <AmbiguityList
          items={payload.ambiguities}
          editable={editable}
          onChange={(items) => set('ambiguities', items)}
        />
      </Section>

      <Section
        title="Missing Information"
        empty={payload.missing_information.length === 0}
        editable={editable}
        addLabel="Add item"
        onAdd={() => set('missing_information', [...payload.missing_information, ''])}
      >
        <StringList
          items={payload.missing_information}
          editable={editable}
          onChange={(items) => set('missing_information', items)}
        />
      </Section>

      <Section
        title="Edge Cases"
        empty={payload.edge_cases.length === 0}
        editable={editable}
        addLabel="Add edge case"
        onAdd={() => set('edge_cases', [...payload.edge_cases, { statement: '', rationale: '' }])}
      >
        <RationaleList
          items={payload.edge_cases}
          editable={editable}
          onChange={(items) => set('edge_cases', items)}
        />
      </Section>

      <Section
        title="Automation Candidates"
        empty={payload.automation_candidates.length === 0}
        editable={editable}
        addLabel="Add candidate"
        onAdd={() =>
          set('automation_candidates', [...payload.automation_candidates, { statement: '', rationale: '' }])
        }
      >
        <RationaleList
          items={payload.automation_candidates}
          editable={editable}
          onChange={(items) => set('automation_candidates', items)}
        />
      </Section>

      <Section
        title="Manual Candidates"
        empty={payload.manual_candidates.length === 0}
        editable={editable}
        addLabel="Add candidate"
        onAdd={() =>
          set('manual_candidates', [...payload.manual_candidates, { statement: '', rationale: '' }])
        }
      >
        <RationaleList
          items={payload.manual_candidates}
          editable={editable}
          onChange={(items) => set('manual_candidates', items)}
        />
      </Section>
    </div>
  );
}
