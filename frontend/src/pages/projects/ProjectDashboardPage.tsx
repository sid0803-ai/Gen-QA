import { Col, Row, Typography } from 'antd';
import { useParams } from 'react-router-dom';
import { StatTile } from '../../components/StatTile';
import { useProject } from '../../hooks/useProjects';

export default function ProjectDashboardPage() {
  const { projectId } = useParams();
  const { data: project, isLoading } = useProject(projectId);

  return (
    <div>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        {isLoading ? 'Loading…' : project?.name ?? 'Dashboard'}
      </Typography.Title>
      <Typography.Text type="secondary">
        Project overview. These tiles will populate with real data in later sprints.
      </Typography.Text>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} sm={12} lg={8}>
          <StatTile title="Requirements" value={0} />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatTile title="Test Cases" value={0} />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatTile title="Automation Coverage" value={0} suffix="%" />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatTile title="Latest Execution" />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatTile title="Open Failures" value={0} />
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <StatTile title="Scheduled Jobs" value={0} />
        </Col>
      </Row>
    </div>
  );
}
