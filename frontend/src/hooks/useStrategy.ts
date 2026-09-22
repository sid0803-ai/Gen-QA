import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as strategyApi from '../api/strategy';
import { requirementsKey } from './useRequirements';
import type { TestStrategyPayload } from '../api/types';

export function strategiesKey(projectId: string | undefined, requirementId: string | undefined) {
  return ['projects', projectId, 'requirements', requirementId, 'strategy'] as const;
}

export function strategyKey(
  projectId: string | undefined,
  requirementId: string | undefined,
  strategyId: string | undefined,
) {
  return [...strategiesKey(projectId, requirementId), strategyId] as const;
}

/** List of test strategies for a requirement, newest first. List items omit `payload`. */
export function useStrategies(projectId: string | undefined, requirementId: string | undefined) {
  return useQuery({
    queryKey: strategiesKey(projectId, requirementId),
    queryFn: () => strategyApi.listStrategies(projectId as string, requirementId as string),
    enabled: !!projectId && !!requirementId,
  });
}

/** Full test strategy detail (incl. payload). Pass `enabled: false` to defer fetching until needed. */
export function useStrategy(
  projectId: string | undefined,
  requirementId: string | undefined,
  strategyId: string | undefined,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: strategyKey(projectId, requirementId, strategyId),
    queryFn: () =>
      strategyApi.getStrategy(projectId as string, requirementId as string, strategyId as string),
    enabled: !!projectId && !!requirementId && !!strategyId && (options?.enabled ?? true),
  });
}

/** Requirement list rows carry `latest_strategy_status`, so also invalidate that list. */
function invalidateStrategyRelated(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId: string | undefined,
  requirementId: string | undefined,
) {
  queryClient.invalidateQueries({ queryKey: strategiesKey(projectId, requirementId) });
  queryClient.invalidateQueries({ queryKey: requirementsKey(projectId) });
}

export function useCreateStrategy(projectId: string | undefined, requirementId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => strategyApi.createStrategy(projectId as string, requirementId as string),
    onSuccess: (data) => {
      queryClient.setQueryData(strategyKey(projectId, requirementId, data.id), data);
      invalidateStrategyRelated(queryClient, projectId, requirementId);
    },
  });
}

export function useUpdateStrategy(
  projectId: string | undefined,
  requirementId: string | undefined,
  strategyId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TestStrategyPayload) =>
      strategyApi.updateStrategy(
        projectId as string,
        requirementId as string,
        strategyId as string,
        payload,
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(strategyKey(projectId, requirementId, strategyId), data);
      queryClient.invalidateQueries({ queryKey: strategiesKey(projectId, requirementId) });
    },
  });
}

export function useApproveStrategy(
  projectId: string | undefined,
  requirementId: string | undefined,
  strategyId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      strategyApi.approveStrategy(projectId as string, requirementId as string, strategyId as string),
    onSuccess: (data) => {
      queryClient.setQueryData(strategyKey(projectId, requirementId, strategyId), data);
      invalidateStrategyRelated(queryClient, projectId, requirementId);
    },
  });
}

export function useRejectStrategy(
  projectId: string | undefined,
  requirementId: string | undefined,
  strategyId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      strategyApi.rejectStrategy(projectId as string, requirementId as string, strategyId as string),
    onSuccess: (data) => {
      queryClient.setQueryData(strategyKey(projectId, requirementId, strategyId), data);
      invalidateStrategyRelated(queryClient, projectId, requirementId);
    },
  });
}
