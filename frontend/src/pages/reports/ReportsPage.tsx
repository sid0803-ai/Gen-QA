import { useState } from 'react';
import { Card, Col, Row, Select, Skeleton, Typography } from 'antd';
import { useParams } from 'react-router-dom';
import { useProjectBreakdown, useProjectTrend } from '../../hooks/useReports';
import { TrendChart } from '../../charts/TrendChart';
import { BreakdownBarChart } from '../../charts/BreakdownBarChart';
import { CHARTABLE_STATUSES, STATUS_COLOR, STATUS_LABEL } from '../../charts/statusPalette';

const DAYS_OPTIONS = [
  { value: 7, label: 'Last 7 days' },
  { value: 30, label: 'Last 30 days' },
  { value: 90, label: 'Last 90 days' },
];

const NO_RUNS_COLOR = '#c3c2b7';

function BreakdownLegend() {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 16 }}>
      {CHARTABLE_STATUSES.map((status) => (
        <div key={status} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span aria-hidden style={{ width: 10, height: 10, borderRadius: 2, background: STATUS_COLOR[status], display: 'inline-block' }} />
          <Typography.Text style={{ fontSize: 12 }} type="secondary">
            {STATUS_LABEL[status]}
          </Typography.Text>
        </div>
      ))}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span aria-hidden style={{ width: 10, height: 10, borderRadius: 2, background: NO_RUNS_COLOR, display: 'inline-block' }} />
        <Typography.Text style={{ fontSize: 12 }} type="secondary">
          No runs
        </Typography.Text>
      </div>
    </div>
  );
}

export default function ReportsPage() {
  const { projectId } = useParams();
  const [days, setDays] = useState(30);

  const { data: trend, isLoading: trendLoading } = useProjectTrend(projectId, days);
  const { data: breakdown, isLoading: breakdownLoading } = useProjectBreakdown(projectId);

  return (
    <div>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        Reports
      </Typography.Title>
      <Typography.Text type="secondary">
        Execution trends and coverage breakdowns for this project.
      </Typography.Text>

      <Card
        title="Execution trend"
        style={{ marginTop: 24 }}
        extra={
          <span data-testid="reports-trend-days-select">
            <Select value={days} onChange={setDays} options={DAYS_OPTIONS} style={{ width: 150 }} />
          </span>
        }
      >
        {trendLoading ? (
          <Skeleton active paragraph={{ rows: 5 }} />
        ) : (
          <TrendChart data={trend ?? []} />
        )}
      </Card>

      <Card title="Breakdown" style={{ marginTop: 24 }}>
        {breakdownLoading ? (
          <Skeleton active paragraph={{ rows: 6 }} />
        ) : (
          <>
            <BreakdownLegend />
            <Row gutter={[24, 24]}>
              <Col xs={24} lg={12}>
                <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
                  By testing level
                </Typography.Text>
                <BreakdownBarChart
                  testId="reports-breakdown-testing-level"
                  rows={(breakdown?.by_testing_level ?? []).map((e) => ({
                    label: e.testing_level,
                    entry: e,
                  }))}
                />
              </Col>
              <Col xs={24} lg={12}>
                <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
                  By category
                </Typography.Text>
                <BreakdownBarChart
                  testId="reports-breakdown-category"
                  rows={(breakdown?.by_category ?? []).map((e) => ({
                    label: e.category,
                    entry: e,
                  }))}
                />
              </Col>
              <Col xs={24} lg={12}>
                <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
                  By priority
                </Typography.Text>
                <BreakdownBarChart
                  testId="reports-breakdown-priority"
                  rows={(breakdown?.by_priority ?? []).map((e) => ({
                    label: e.priority,
                    entry: e,
                  }))}
                />
              </Col>
            </Row>
          </>
        )}
      </Card>
    </div>
  );
}
