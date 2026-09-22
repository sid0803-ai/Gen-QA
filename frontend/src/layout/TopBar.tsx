import { Avatar, Dropdown, Select, Space, Typography } from 'antd';
import type { MenuProps } from 'antd';
import { DownOutlined, LogoutOutlined, UserOutlined } from '@ant-design/icons';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../auth/useAuth';
import { useProjects } from '../hooks/useProjects';
import { useAuthStore } from '../store/authStore';

export function TopBar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { projectId: routeProjectId } = useParams();
  const selectedProjectId = useAuthStore((s) => s.selectedProjectId);
  const setSelectedProjectId = useAuthStore((s) => s.setSelectedProjectId);
  const { user, logout } = useAuth();
  const { data: projects, isLoading } = useProjects();

  const activeProjectId = routeProjectId ?? selectedProjectId ?? undefined;

  const handleProjectChange = (projectId: string) => {
    setSelectedProjectId(projectId);
    // Preserve the current sub-page (e.g. stay on "requirements") when switching project.
    const segments = location.pathname.split('/').filter(Boolean);
    const rest = segments[0] === 'projects' ? segments.slice(2).join('/') : '';
    navigate(`/projects/${projectId}${rest ? `/${rest}` : ''}`);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const userMenuItems: MenuProps['items'] = [
    { key: 'email', label: user?.email, disabled: true },
    { type: 'divider' },
    { key: 'logout', label: 'Logout', icon: <LogoutOutlined />, onClick: handleLogout },
  ];

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
      <Select
        style={{ minWidth: 260 }}
        placeholder="Select a project"
        value={activeProjectId}
        onChange={handleProjectChange}
        loading={isLoading}
        options={(projects ?? []).map((p) => ({ value: p.id, label: p.name }))}
        notFoundContent="No projects yet"
      />
      <Dropdown menu={{ items: userMenuItems }} trigger={['click']}>
        <Space style={{ cursor: 'pointer' }}>
          <Avatar icon={<UserOutlined />} size="small" />
          <Typography.Text>{user?.full_name || user?.email}</Typography.Text>
          <DownOutlined style={{ fontSize: 10 }} />
        </Space>
      </Dropdown>
    </div>
  );
}
