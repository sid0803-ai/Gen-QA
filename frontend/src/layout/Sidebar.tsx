import { App as AntApp, Menu } from 'antd';
import type { MenuProps } from 'antd';
import { ProjectOutlined } from '@ant-design/icons';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { PROJECT_NAV_ITEMS } from './navConfig';

function resolveSelectedKey(pathname: string): string {
  const segments = pathname.split('/').filter(Boolean);
  if (segments[0] !== 'projects') return '';
  if (!segments[1]) return 'projects';

  const rest = segments.slice(2).join('/');
  if (!rest) return 'dashboard';
  if (rest.startsWith('settings')) return 'settings';
  return rest.split('/')[0];
}

export function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { projectId: routeProjectId } = useParams();
  const selectedProjectId = useAuthStore((s) => s.selectedProjectId);
  const { message } = AntApp.useApp();

  const activeProjectId = routeProjectId ?? selectedProjectId ?? undefined;
  const selectedKey = resolveSelectedKey(location.pathname);

  const items: MenuProps['items'] = [
    { key: 'projects', icon: <ProjectOutlined />, label: 'Projects' },
    { type: 'divider' },
    ...PROJECT_NAV_ITEMS.map((item) => ({
      key: item.key,
      icon: item.icon,
      label: item.label,
    })),
  ];

  const handleClick: MenuProps['onClick'] = ({ key }) => {
    if (key === 'projects') {
      navigate('/projects');
      return;
    }

    if (!activeProjectId) {
      message.info('Select a project first.');
      navigate('/projects');
      return;
    }

    const navItem = PROJECT_NAV_ITEMS.find((i) => i.key === key);
    if (!navItem) return;
    navigate(`/projects/${activeProjectId}${navItem.path ? `/${navItem.path}` : ''}`);
  };

  return (
    <>
      <div
        style={{
          color: '#fff',
          fontWeight: 600,
          fontSize: 18,
          padding: '16px 0',
          textAlign: 'center',
        }}
      >
        Gen-QA
      </div>
      <Menu theme="dark" mode="inline" selectedKeys={[selectedKey]} items={items} onClick={handleClick} />
    </>
  );
}
