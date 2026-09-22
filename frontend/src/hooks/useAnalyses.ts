import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as requirementsApi from '../api/requirements';
import { requirementsKey } from './useRequirements';
import type { RequirementAnalysisPayload } from '../api/types';

export function analysesKey(projectId: string | undefined, requirementId: string | undefined) {
  return ['projects', projectId, 'requirements', requirementId, 'analyses'] as const;
}

export function analysisKey(
  projectId: string | undefined,
  requirementId: string | undefined,
  analysisId: string | undefined,
) {
  return [...analysesKey(projectId, requirementId), analysisId] as const;
}

/** List of analyses for a requirement, newest first. List items omit `payload`. */
export function useAnalyses(projectId: string | undefined, requirementId: string | undefined) {
  return useQuery({
    queryKey: analysesKey(projectId, requirementId),
    queryFn: () => requirementsApi.listAnalyses(projectId as string, requirementId as string),
    enabled: !!projectId && !!requirementId,
  });
}

/** Full analysis detail (incl. payload). Pass `enabled: false` to defer fetching until needed. */
export function useAnalysis(
  projectId: string | undefined,
  requirementId: string | undefined,
  analysisId: string | undefined,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: analysisKey(projectId, requirementId, analysisId),
    queryFn: () =>
      requirementsApi.getAnalysis(
        projectId as string,
        requirementId as string,
        analysisId as string,
      ),
    enabled: !!projectId && !!requirementId && !!analysisId && (options?.enabled ?? true),
  });
}

/** Requirement list rows carry `latest_analysis_status`, so also invalidate that list. */
function invalidateAnalysisRelated(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId: string | undefined,
  requirementId: string | undefined,
) {
  queryClient.invalidateQueries({ queryKey: analysesKey(projectId, requirementId) });
  queryClient.invalidateQueries({ queryKey: requirementsKey(projectId) });
}

export function useCreateAnalysis(projectId: string | undefined, requirementId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      requirementsApi.createAnalysis(projectId as string, requirementId as string),
    onSuccess: (data) => {
      queryClient.setQueryData(analysisKey(projectId, requirementId, data.id), data);
      invalidateAnalysisRelated(queryClient, projectId, requirementId);
    },
  });
}

export function useUpdateAnalysis(
  projectId: string | undefined,
  requirementId: string | undefined,
  analysisId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RequirementAnalysisPayload) =>
      requirementsApi.updateAnalysis(
        projectId as string,
        requirementId as string,
        analysisId as string,
        payload,
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(analysisKey(projectId, requirementId, analysisId), data);
      queryClient.invalidateQueries({ queryKey: analysesKey(projectId, requirementId) });
    },
  });
}

export function useApproveAnalysis(
  projectId: string | undefined,
  requirementId: string | undefined,
  analysisId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      requirementsApi.approveAnalysis(
        projectId as string,
        requirementId as string,
        analysisId as string,
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(analysisKey(projectId, requirementId, analysisId), data);
      invalidateAnalysisRelated(queryClient, projectId, requirementId);
    },
  });
}

export function useRejectAnalysis(
  projectId: string | undefined,
  requirementId: string | undefined,
  analysisId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      requirementsApi.rejectAnalysis(
        projectId as string,
        requirementId as string,
        analysisId as string,
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(analysisKey(projectId, requirementId, analysisId), data);
      invalidateAnalysisRelated(queryClient, projectId, requirementId);
    },
  });
}
