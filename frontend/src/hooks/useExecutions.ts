import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Query } from '@tanstack/react-query';
import * as executionsApi from '../api/executions';
import type { Execution, ExecutionCreateInput, ExecutionListParams } from '../api/types';

const NON_TERMINAL: Execution['status'][] = ['pending', 'running'];

function executionsRootKey(projectId: string | undefined) {
  return ['projects', projectId, 'executions'] as const;
}

export function executionsKey(projectId: string | undefined, params: ExecutionListParams = {}) {
  return [...executionsRootKey(projectId), 'list', params] as const;
}

export function executionKey(projectId: string | undefined, executionId: string | undefined) {
  return [...executionsRootKey(projectId), 'detail', executionId] as const;
}

export function useExecutions(projectId: string | undefined, params: ExecutionListParams = {}) {
  return useQuery({
    queryKey: executionsKey(projectId, params),
    queryFn: () => executionsApi.listExecutions(projectId as string, params),
    enabled: !!projectId,
  });
}

/**
 * Fetches one execution. When `poll` is true, refetches every ~2s while the
 * execution is still `pending`/`running` and stops automatically once it
 * reaches a terminal status — the idiomatic TanStack Query way to drive a
 * "trigger then watch it finish" UI without a manual interval/timeout.
 */
export function useExecution(
  projectId: string | undefined,
  executionId: string | undefined,
  options?: { poll?: boolean },
) {
  return useQuery({
    queryKey: executionKey(projectId, executionId),
    queryFn: () => executionsApi.getExecution(projectId as string, executionId as string),
    enabled: !!projectId && !!executionId,
    refetchInterval: options?.poll
      ? (query: Query<Execution>) => (NON_TERMINAL.includes(query.state.data?.status as Execution['status']) ? 2000 : false)
      : undefined,
  });
}

export function useCreateExecution(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ExecutionCreateInput) => executionsApi.createExecution(projectId as string, input),
    onSuccess: (data) => {
      queryClient.setQueryData(executionKey(projectId, data.id), data);
      queryClient.invalidateQueries({ queryKey: executionsRootKey(projectId) });
    },
  });
}
