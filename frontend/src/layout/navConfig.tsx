import type { ReactNode } from 'react';
import {
  DashboardOutlined,
  FileTextOutlined,
  CheckSquareOutlined,
  ScheduleOutlined,
  RobotOutlined,
  PlayCircleOutlined,
  ClockCircleOutlined,
  BarChartOutlined,
  SettingOutlined,
  ApiOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';

export interface ProjectNavItem {
  key: string;
  label: string;
  icon: ReactNode;
  /** Path segment appended to `/projects/:projectId/`; '' means the project root (dashboard). */
  path: string;
}

/**
 * Full Sprint-1+ product nav. `dashboard`, `requirements` (incl. its AI
 * Analysis/Feasibility/Strategy/Test Design review sections), `test-cases`,
 * and the top-level `projects` list have real functionality; everything
 * else routes to a "Coming soon" stub page but lives in the same shell so
 * the product reads as whole from day one.
 *
 * Test Design deliberately has no standalone nav entry of its own — like
 * Feasibility and Strategy before it, it lives as a section on the
 * requirement detail page (`RequirementDetailPage`) rather than as a
 * separate top-level page, since a test design is generated per
 * requirement. Test Cases stays as its own top-level item because the
 * resulting test case repository genuinely is project-wide.
 */
export const PROJECT_NAV_ITEMS: ProjectNavItem[] = [
  { key: 'dashboard', label: 'Dashboard', icon: <DashboardOutlined />, path: '' },
  { key: 'requirements', label: 'Requirements', icon: <FileTextOutlined />, path: 'requirements' },
  { key: 'test-cases', label: 'Test Cases', icon: <CheckSquareOutlined />, path: 'test-cases' },
  { key: 'test-plans', label: 'Test Plans', icon: <ScheduleOutlined />, path: 'test-plans' },
  { key: 'automation', label: 'Automation', icon: <RobotOutlined />, path: 'automation' },
  { key: 'testing', label: 'Testing', icon: <PlayCircleOutlined />, path: 'testing' },
  { key: 'schedules', label: 'Schedules', icon: <ClockCircleOutlined />, path: 'schedules' },
  { key: 'api-performer', label: 'API Performer', icon: <ApiOutlined />, path: 'api-performer' },
  { key: 'performance', label: 'Performance', icon: <ThunderboltOutlined />, path: 'performance' },
  { key: 'reports', label: 'Reports', icon: <BarChartOutlined />, path: 'reports' },
  { key: 'settings', label: 'Settings', icon: <SettingOutlined />, path: 'settings/members' },
];
