import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import * as automationScriptApi from '../api/automationScript';
import { ApiError } from '../api/client';
import type { AutomationScript, AutomationScriptGenerateInput, AutomationScriptUpdateInput } from '../api/types';

export function automationScriptKey(projectId: string | undefined, testCaseId: string | undefined) {
  return ['projects', projectId, 'test-cases', testCaseId, 'automation-script'] as const;
}

export function automationScriptVersionsKey(
  projectId: string | undefined,
  testCaseId: string | undefined,
) {
  return [...automationScriptKey(projectId, testCaseId), 'versions'] as const;
}

/** Fetches the current script; resolves to `null` (not an error) when none has been generated yet (404). */
async function fetchAutomationScriptOrNull(
  projectId: string,
  testCaseId: string,
): Promise<AutomationScript | null> {
  try {
    return await automationScriptApi.getAutomationScript(projectId, testCaseId);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export function useAutomationScript(projectId: string | undefined, testCaseId: string | undefined) {
  return useQuery({
    queryKey: automationScriptKey(projectId, testCaseId),
    queryFn: () => fetchAutomationScriptOrNull(projectId as string, testCaseId as string),
    enabled: !!projectId && !!testCaseId,
  });
}

/**
 * Bulk-fetches automation script status for many test cases (e.g. the project-wide
 * Automation overview). The contract has no batch endpoint, so this fans out one
 * request per test case via the same per-test-case query/cache key used on the
 * detail page — visiting a test case afterwards is then a cache hit.
 */
export function useAutomationScriptsByTestCase(
  projectId: string | undefined,
  testCaseIds: string[],
) {
  const results = useQueries({
    queries: testCaseIds.map((testCaseId) => ({
      queryKey: automationScriptKey(projectId, testCaseId),
      queryFn: () => fetchAutomationScriptOrNull(projectId as string, testCaseId),
      enabled: !!projectId,
    })),
  });

  const map = new Map<string, AutomationScript | null>();
  testCaseIds.forEach((id, i) => {
    const data = results[i]?.data;
    if (data !== undefined) map.set(id, data);
  });

  return { map, isLoading: results.some((r) => r.isLoading) };
}

export function useAutomationScriptVersions(
  projectId: string | undefined,
  testCaseId: string | undefined,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: automationScriptVersionsKey(projectId, testCaseId),
    queryFn: () => automationScriptApi.listAutomationScriptVersions(projectId as string, testCaseId as string),
    enabled: !!projectId && !!testCaseId && (options?.enabled ?? true),
  });
}

function invalidateAutomationScript(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId: string | undefined,
  testCaseId: string | undefined,
) {
  queryClient.invalidateQueries({ queryKey: automationScriptVersionsKey(projectId, testCaseId) });
}

export function useGenerateAutomationScript(
  projectId: string | undefined,
  testCaseId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AutomationScriptGenerateInput) =>
      automationScriptApi.generateAutomationScript(projectId as string, testCaseId as string, input),
    onSuccess: (data) => {
      queryClient.setQueryData(automationScriptKey(projectId, testCaseId), data);
      invalidateAutomationScript(queryClient, projectId, testCaseId);
    },
  });
}

export function useUpdateAutomationScript(
  projectId: string | undefined,
  testCaseId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AutomationScriptUpdateInput) =>
      automationScriptApi.updateAutomationScript(projectId as string, testCaseId as string, input),
    onSuccess: (data) => {
      queryClient.setQueryData(automationScriptKey(projectId, testCaseId), data);
      invalidateAutomationScript(queryClient, projectId, testCaseId);
    },
  });
}

export function useApproveAutomationScript(
  projectId: string | undefined,
  testCaseId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => automationScriptApi.approveAutomationScript(projectId as string, testCaseId as string),
    onSuccess: (data) => {
      queryClient.setQueryData(automationScriptKey(projectId, testCaseId), data);
      invalidateAutomationScript(queryClient, projectId, testCaseId);
    },
  });
}
