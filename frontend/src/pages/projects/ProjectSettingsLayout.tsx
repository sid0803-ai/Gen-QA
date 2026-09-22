import { Tabs, Typography } from 'antd';
import { Outlet, useLocation, useNavigate, useParams } from 'react-router-dom';

export default function ProjectSettingsLayout() {
  const { projectId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  const activeKey = location.pathname.endsWith('/general') ? 'general' : 'members';

  return (
    <div>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        Settings
      </Typography.Title>
      <Tabs
        activeKey={activeKey}
        onChange={(key) => navigate(`/projects/${projectId}/settings/${key}`)}
        items={[
          { key: 'members', label: 'Members' },
          { key: 'general', label: 'Project settings' },
        ]}
      />
      <Outlet />
    </div>
  );
}
