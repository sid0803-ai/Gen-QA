import { Col, Row, Typography } from 'antd';
import { useParams } from 'react-router-dom';
import { StatTile } from '../../components/StatTile';
import { useProject } from '../../hooks/useProjects';
import { useProjectDashboard } from '../../hooks/useReports';

export default function ProjectDashboardPage() {
  const { projectId } = useParams();
  const { data: project, isLoading } = useProject(projectId);
  const { data: dashboard, isLoading: dashboardLoading } = useProjectDashboard(projectId);

  return (
    <div>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        {isLoading ? 'Loading…' : project?.name ?? 'Dashboard'}
      </Typography.Title>
      <Typography.Text type="secondary">Project overview.</Typography.Text>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} sm={12} lg={8}>
          <StatTile
            title="Requirements"
            value={dashboardLoading ? undefined : dashboard?.requirements_count ?? 0}
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatTile
            title="Test Cases"
            value={dashboardLoading ? undefined : dashboard?.test_cases_count ?? 0}
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatTile
            title="Automation Coverage"
            value={dashboardLoading ? undefined : dashboard?.automation_coverage_pct ?? 0}
            suffix="%"
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatTile
            title="Pass Rate"
            value={dashboardLoading ? undefined : dashboard?.pass_rate_pct ?? undefined}
            suffix="%"
            emptyText="No executions yet"
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatTile
            title="In Progress Executions"
            value={dashboardLoading ? undefined : dashboard?.in_progress_count ?? 0}
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatTile
            title="Open Failures"
            value={dashboardLoading ? undefined : dashboard?.open_failures_count ?? 0}
          />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatTile
            title="Scheduled Jobs"
            value={dashboardLoading ? undefined : dashboard?.scheduled_jobs_count ?? 0}
          />
        </Col>
      </Row>
    </div>
  );
}
