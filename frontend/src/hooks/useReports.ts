import { useQuery } from '@tanstack/react-query';
import * as reportsApi from '../api/reports';

function reportsRootKey(projectId: string | undefined) {
  return ['projects', projectId, 'reports'] as const;
}

export function useProjectDashboard(projectId: string | undefined) {
  return useQuery({
    queryKey: [...reportsRootKey(projectId), 'dashboard'] as const,
    queryFn: () => reportsApi.getProjectDashboard(projectId as string),
    enabled: !!projectId,
  });
}

export function useProjectTrend(projectId: string | undefined, days = 30) {
  return useQuery({
    queryKey: [...reportsRootKey(projectId), 'trend', days] as const,
    queryFn: () => reportsApi.getProjectTrend(projectId as string, days),
    enabled: !!projectId,
  });
}

export function useProjectBreakdown(projectId: string | undefined) {
  return useQuery({
    queryKey: [...reportsRootKey(projectId), 'breakdown'] as const,
    queryFn: () => reportsApi.getProjectBreakdown(projectId as string),
    enabled: !!projectId,
  });
}

export function useRequirementCoverage(
  projectId: string | undefined,
  requirementId: string | undefined,
) {
  return useQuery({
    queryKey: ['projects', projectId, 'requirements', requirementId, 'coverage'] as const,
    queryFn: () => reportsApi.getRequirementCoverage(projectId as string, requirementId as string),
    enabled: !!projectId && !!requirementId,
  });
}
