import type { ReactNode } from 'react';
import {
  DashboardOutlined,
  FileTextOutlined,
  BulbOutlined,
  CheckSquareOutlined,
  ScheduleOutlined,
  RobotOutlined,
  PlayCircleOutlined,
  ClockCircleOutlined,
  BarChartOutlined,
  SettingOutlined,
} from '@ant-design/icons';

export interface ProjectNavItem {
  key: string;
  label: string;
  icon: ReactNode;
  /** Path segment appended to `/projects/:projectId/`; '' means the project root (dashboard). */
  path: string;
}

/**
 * Full Sprint-1+ product nav. Only `dashboard` (and the top-level
 * `projects` list) has real functionality right now; everything else
 * routes to a "Coming soon" stub page but lives in the same shell so the
 * product reads as whole from day one.
 */
export const PROJECT_NAV_ITEMS: ProjectNavItem[] = [
  { key: 'dashboard', label: 'Dashboard', icon: <DashboardOutlined />, path: '' },
  { key: 'requirements', label: 'Requirements', icon: <FileTextOutlined />, path: 'requirements' },
  { key: 'test-design', label: 'Test Design', icon: <BulbOutlined />, path: 'test-design' },
  { key: 'test-cases', label: 'Test Cases', icon: <CheckSquareOutlined />, path: 'test-cases' },
  { key: 'test-plans', label: 'Test Plans', icon: <ScheduleOutlined />, path: 'test-plans' },
  { key: 'automation', label: 'Automation', icon: <RobotOutlined />, path: 'automation' },
  { key: 'testing', label: 'Testing', icon: <PlayCircleOutlined />, path: 'testing' },
  { key: 'schedules', label: 'Schedules', icon: <ClockCircleOutlined />, path: 'schedules' },
  { key: 'reports', label: 'Reports', icon: <BarChartOutlined />, path: 'reports' },
  { key: 'settings', label: 'Settings', icon: <SettingOutlined />, path: 'settings/members' },
];
