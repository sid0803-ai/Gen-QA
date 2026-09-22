import { Button, Divider, Empty, Input, Select, Space, Tag, Typography } from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import type { FeasibilityRecommendation, FeasibilityScenario, FeasibilityStudyPayload } from '../../api/types';

const { Title, Paragraph, Text } = Typography;

const RECOMMENDATION_COLORS: Record<FeasibilityRecommendation, string> = {
  automate: 'green',
  manual: 'blue',
  hybrid: 'purple',
  needs_review: 'orange',
};

const RECOMMENDATION_LABELS: Record<FeasibilityRecommendation, string> = {
  automate: 'Automate',
  manual: 'Manual',
  hybrid: 'Hybrid',
  needs_review: 'Needs review',
};

const RECOMMENDATION_OPTIONS = (Object.keys(RECOMMENDATION_LABELS) as FeasibilityRecommendation[]).map(
  (value) => ({ value, label: RECOMMENDATION_LABELS[value] }),
);

function RecommendationTag({ value }: { value: FeasibilityRecommendation }) {
  return <Tag color={RECOMMENDATION_COLORS[value]}>{RECOMMENDATION_LABELS[value]}</Tag>;
}

function ScenarioList({
  scenarios,
  editable,
  onChange,
}: {
  scenarios: FeasibilityScenario[];
  editable: boolean;
  onChange: (scenarios: FeasibilityScenario[]) => void;
}) {
  const update = (index: number, patch: Partial<FeasibilityScenario>) => {
    onChange(scenarios.map((s, i) => (i === index ? { ...s, ...patch } : s)));
  };
  const remove = (index: number) => onChange(scenarios.filter((_, i) => i !== index));

  if (!editable) {
    return (
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        {scenarios.map((s, i) => {
          const override = s.overridden_recommendation;
          const overridden = override !== null && override !== s.recommendation;
          return (
            <div key={i}>
              <Text strong>{s.title}</Text>
              <Paragraph style={{ marginBottom: 4 }}>{s.description}</Paragraph>
              <Space align="center" wrap>
                {overridden ? (
                  <>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      AI suggested:
                    </Text>
                    <Tag style={{ textDecoration: 'line-through', opacity: 0.6 }}>
                      {RECOMMENDATION_LABELS[s.recommendation]}
                    </Tag>
                    <RecommendationTag value={override} />
                  </>
                ) : (
                  <RecommendationTag value={override ?? s.recommendation} />
                )}
              </Space>
              <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 4, marginBottom: 0 }}>
                {s.reason}
              </Paragraph>
            </div>
          );
        })}
      </Space>
    );
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      {scenarios.map((s, i) => {
        const override = s.overridden_recommendation;
        const effectiveOverride = override ?? s.recommendation;
        const overridden = override !== null && override !== s.recommendation;
        return (
          <div
            key={i}
            style={{ border: '1px solid #f0f0f0', borderRadius: 6, padding: 12, position: 'relative' }}
          >
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
              onClick={() => remove(i)}
              style={{ position: 'absolute', top: 8, right: 8 }}
            />
            <Space direction="vertical" size={8} style={{ width: '100%', paddingRight: 32 }}>
              <Input
                placeholder="Scenario title"
                value={s.title}
                onChange={(e) => update(i, { title: e.target.value })}
              />
              <Input.TextArea
                placeholder="Description"
                rows={2}
                value={s.description}
                onChange={(e) => update(i, { description: e.target.value })}
              />
              <Input
                placeholder="Reason — why the AI recommended this"
                value={s.reason}
                onChange={(e) => update(i, { reason: e.target.value })}
              />
              <Space align="center" wrap>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  AI recommendation:
                </Text>
                <RecommendationTag value={s.recommendation} />
                <Text type="secondary" style={{ fontSize: 12, marginLeft: 8 }}>
                  Reviewer override:
                </Text>
                <Select<FeasibilityRecommendation>
                  value={effectiveOverride}
                  style={{ width: 160 }}
                  onChange={(value) => update(i, { overridden_recommendation: value })}
                  options={RECOMMENDATION_OPTIONS}
                />
                {overridden && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    (differs from AI suggestion:{' '}
                    <span style={{ textDecoration: 'line-through' }}>
                      {RECOMMENDATION_LABELS[s.recommendation]}
                    </span>
                    )
                  </Text>
                )}
              </Space>
            </Space>
          </div>
        );
      })}
    </Space>
  );
}

export interface FeasibilityPayloadViewProps {
  payload: FeasibilityStudyPayload;
  editable: boolean;
  onChange: (payload: FeasibilityStudyPayload) => void;
}

/**
 * Renders the structured feasibility study payload: a summary, then a list
 * of scenarios each showing the AI's automate/manual/hybrid/needs_review
 * recommendation as a colored tag plus its reasoning. While editable, a
 * reviewer can override each scenario's recommendation without losing sight
 * of what the AI originally said (both tags render when they differ).
 */
export function FeasibilityPayloadView({ payload, editable, onChange }: FeasibilityPayloadViewProps) {
  const set = <K extends keyof FeasibilityStudyPayload>(key: K, value: FeasibilityStudyPayload[K]) =>
    onChange({ ...payload, [key]: value });

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

      <Divider style={{ margin: '16px 0' }} />

      <div>
        <Title level={5} style={{ marginBottom: 4 }}>
          Scenarios
        </Title>
        {payload.scenarios.length === 0 && !editable ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="None identified" style={{ margin: '8px 0' }} />
        ) : (
          <ScenarioList
            scenarios={payload.scenarios}
            editable={editable}
            onChange={(scenarios) => set('scenarios', scenarios)}
          />
        )}
        {editable && (
          <Button
            type="dashed"
            size="small"
            icon={<PlusOutlined />}
            onClick={() =>
              set('scenarios', [
                ...payload.scenarios,
                {
                  title: '',
                  description: '',
                  recommendation: 'needs_review',
                  reason: '',
                  overridden_recommendation: null,
                },
              ])
            }
            style={{ marginTop: 8 }}
          >
            Add scenario
          </Button>
        )}
      </div>
    </div>
  );
}
