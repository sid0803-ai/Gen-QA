import { api } from './client';
import type { ProjectBreakdown, ProjectDashboard, RequirementCoverage, TrendPoint } from './types';

export function getProjectDashboard(projectId: string): Promise<ProjectDashboard> {
  return api.get<ProjectDashboard>(`/projects/${projectId}/dashboard`);
}

export function getProjectTrend(projectId: string, days = 30): Promise<TrendPoint[]> {
  return api.get<TrendPoint[]>(`/projects/${projectId}/reports/trend?days=${days}`);
}

export function getProjectBreakdown(projectId: string): Promise<ProjectBreakdown> {
  return api.get<ProjectBreakdown>(`/projects/${projectId}/reports/breakdown`);
}

export function getRequirementCoverage(
  projectId: string,
  requirementId: string,
): Promise<RequirementCoverage> {
  return api.get<RequirementCoverage>(
    `/projects/${projectId}/requirements/${requirementId}/coverage`,
  );
}
