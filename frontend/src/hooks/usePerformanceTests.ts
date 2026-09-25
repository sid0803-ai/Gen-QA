import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Query } from '@tanstack/react-query';
import * as performanceTestsApi from '../api/performanceTests';
import type {
  PerformanceTestCreateInput,
  PerformanceTestRun,
  PerformanceTestUpdateInput,
} from '../api/types';

const NON_TERMINAL: PerformanceTestRun['status'][] = ['queued', 'running'];

function performanceTestsRootKey(projectId: string | undefined) {
  return ['projects', projectId, 'performance-tests'] as const;
}

export function performanceTestsKey(projectId: string | undefined) {
  return [...performanceTestsRootKey(projectId), 'list'] as const;
}

export function performanceTestKey(projectId: string | undefined, testId: string | undefined) {
  return [...performanceTestsRootKey(projectId), 'detail', testId] as const;
}

function performanceTestRunsRootKey(
  projectId: string | undefined,
  testId: string | undefined,
) {
  return [...performanceTestKey(projectId, testId), 'runs'] as const;
}

export function performanceTestRunsKey(
  projectId: string | undefined,
  testId: string | undefined,
) {
  return [...performanceTestRunsRootKey(projectId, testId), 'list'] as const;
}

export function performanceTestRunKey(
  projectId: string | undefined,
  testId: string | undefined,
  runId: string | undefined,
) {
  return [...performanceTestRunsRootKey(projectId, testId), 'detail', runId] as const;
}

export function usePerformanceTests(projectId: string | undefined) {
  return useQuery({
    queryKey: performanceTestsKey(projectId),
    queryFn: () => performanceTestsApi.listPerformanceTests(projectId as string),
    enabled: !!projectId,
  });
}

export function usePerformanceTest(projectId: string | undefined, testId: string | undefined) {
  return useQuery({
    queryKey: performanceTestKey(projectId, testId),
    queryFn: () => performanceTestsApi.getPerformanceTest(projectId as string, testId as string),
    enabled: !!projectId && !!testId,
  });
}

export function useCreatePerformanceTest(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: PerformanceTestCreateInput) =>
      performanceTestsApi.createPerformanceTest(projectId as string, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: performanceTestsKey(projectId) });
    },
  });
}

export function useUpdatePerformanceTest(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: PerformanceTestUpdateInput }) =>
      performanceTestsApi.updatePerformanceTest(projectId as string, id, input),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: performanceTestsKey(projectId) });
      queryClient.invalidateQueries({ queryKey: performanceTestKey(projectId, data.id) });
    },
  });
}

export function useDeletePerformanceTest(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (testId: string) =>
      performanceTestsApi.deletePerformanceTest(projectId as string, testId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: performanceTestsRootKey(projectId) });
    },
  });
}

export function usePerformanceTestRuns(
  projectId: string | undefined,
  testId: string | undefined,
) {
  return useQuery({
    queryKey: performanceTestRunsKey(projectId, testId),
    queryFn: () =>
      performanceTestsApi.listPerformanceTestRuns(projectId as string, testId as string),
    enabled: !!projectId && !!testId,
  });
}

/**
 * Fetches one run's full detail (including `raw_summary`). When `poll` is
 * true, refetches every ~2s while the run is still `queued`/`running` and
 * stops automatically once it reaches a terminal status (`completed` /
 * `failed`) — mirrors `useExecution`'s polling pattern in `useExecutions.ts`.
 */
export function usePerformanceTestRun(
  projectId: string | undefined,
  testId: string | undefined,
  runId: string | undefined,
  options?: { poll?: boolean },
) {
  return useQuery({
    queryKey: performanceTestRunKey(projectId, testId, runId),
    queryFn: () =>
      performanceTestsApi.getPerformanceTestRun(
        projectId as string,
        testId as string,
        runId as string,
      ),
    enabled: !!projectId && !!testId && !!runId,
    refetchInterval: options?.poll
      ? (query: Query<PerformanceTestRun>) =>
          NON_TERMINAL.includes(query.state.data?.status as PerformanceTestRun['status'])
            ? 2000
            : false
      : undefined,
  });
}

export function useTriggerPerformanceTestRun(
  projectId: string | undefined,
  testId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      performanceTestsApi.triggerPerformanceTestRun(projectId as string, testId as string),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: performanceTestRunsKey(projectId, testId) });
    },
  });
}
