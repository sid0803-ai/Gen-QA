import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as feasibilityApi from '../api/feasibility';
import { requirementsKey } from './useRequirements';
import type { FeasibilityStudyPayload } from '../api/types';

export function feasibilitiesKey(projectId: string | undefined, requirementId: string | undefined) {
  return ['projects', projectId, 'requirements', requirementId, 'feasibility'] as const;
}

export function feasibilityKey(
  projectId: string | undefined,
  requirementId: string | undefined,
  feasibilityId: string | undefined,
) {
  return [...feasibilitiesKey(projectId, requirementId), feasibilityId] as const;
}

/** List of feasibility studies for a requirement, newest first. List items omit `payload`. */
export function useFeasibilities(projectId: string | undefined, requirementId: string | undefined) {
  return useQuery({
    queryKey: feasibilitiesKey(projectId, requirementId),
    queryFn: () => feasibilityApi.listFeasibilityStudies(projectId as string, requirementId as string),
    enabled: !!projectId && !!requirementId,
  });
}

/** Full feasibility study detail (incl. payload). Pass `enabled: false` to defer fetching until needed. */
export function useFeasibility(
  projectId: string | undefined,
  requirementId: string | undefined,
  feasibilityId: string | undefined,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: feasibilityKey(projectId, requirementId, feasibilityId),
    queryFn: () =>
      feasibilityApi.getFeasibilityStudy(
        projectId as string,
        requirementId as string,
        feasibilityId as string,
      ),
    enabled: !!projectId && !!requirementId && !!feasibilityId && (options?.enabled ?? true),
  });
}

/** Requirement list rows carry `latest_feasibility_status`, so also invalidate that list. */
function invalidateFeasibilityRelated(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId: string | undefined,
  requirementId: string | undefined,
) {
  queryClient.invalidateQueries({ queryKey: feasibilitiesKey(projectId, requirementId) });
  queryClient.invalidateQueries({ queryKey: requirementsKey(projectId) });
}

export function useCreateFeasibility(projectId: string | undefined, requirementId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      feasibilityApi.createFeasibilityStudy(projectId as string, requirementId as string),
    onSuccess: (data) => {
      queryClient.setQueryData(feasibilityKey(projectId, requirementId, data.id), data);
      invalidateFeasibilityRelated(queryClient, projectId, requirementId);
    },
  });
}

export function useUpdateFeasibility(
  projectId: string | undefined,
  requirementId: string | undefined,
  feasibilityId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: FeasibilityStudyPayload) =>
      feasibilityApi.updateFeasibilityStudy(
        projectId as string,
        requirementId as string,
        feasibilityId as string,
        payload,
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(feasibilityKey(projectId, requirementId, feasibilityId), data);
      queryClient.invalidateQueries({ queryKey: feasibilitiesKey(projectId, requirementId) });
    },
  });
}

export function useApproveFeasibility(
  projectId: string | undefined,
  requirementId: string | undefined,
  feasibilityId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      feasibilityApi.approveFeasibilityStudy(
        projectId as string,
        requirementId as string,
        feasibilityId as string,
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(feasibilityKey(projectId, requirementId, feasibilityId), data);
      invalidateFeasibilityRelated(queryClient, projectId, requirementId);
    },
  });
}

export function useRejectFeasibility(
  projectId: string | undefined,
  requirementId: string | undefined,
  feasibilityId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      feasibilityApi.rejectFeasibilityStudy(
        projectId as string,
        requirementId as string,
        feasibilityId as string,
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(feasibilityKey(projectId, requirementId, feasibilityId), data);
      invalidateFeasibilityRelated(queryClient, projectId, requirementId);
    },
  });
}
