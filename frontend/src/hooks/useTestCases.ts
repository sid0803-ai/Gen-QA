import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as testCasesApi from '../api/testCases';
import type { TestCaseCreateInput, TestCaseListParams, TestCaseUpdateInput } from '../api/types';

/** Root key for everything test-case related in a project — invalidating this catches list (any filter combo) and detail queries alike. */
function testCasesRootKey(projectId: string | undefined) {
  return ['projects', projectId, 'test-cases'] as const;
}

export function testCasesKey(projectId: string | undefined, params: TestCaseListParams = {}) {
  return [...testCasesRootKey(projectId), 'list', params] as const;
}

export function testCaseKey(projectId: string | undefined, testCaseId: string | undefined) {
  return [...testCasesRootKey(projectId), 'detail', testCaseId] as const;
}

export function testCaseVersionsKey(projectId: string | undefined, testCaseId: string | undefined) {
  return [...testCaseKey(projectId, testCaseId), 'versions'] as const;
}

/** Test cases span all requirements in a project. `params` drives server-side filtering + search. */
export function useTestCases(projectId: string | undefined, params: TestCaseListParams = {}) {
  return useQuery({
    queryKey: testCasesKey(projectId, params),
    queryFn: () => testCasesApi.listTestCases(projectId as string, params),
    enabled: !!projectId,
  });
}

export function useTestCase(projectId: string | undefined, testCaseId: string | undefined) {
  return useQuery({
    queryKey: testCaseKey(projectId, testCaseId),
    queryFn: () => testCasesApi.getTestCase(projectId as string, testCaseId as string),
    enabled: !!projectId && !!testCaseId,
  });
}

/** Version history — read-only, fetched lazily (pass `enabled: false` until the section is expanded). */
export function useTestCaseVersions(
  projectId: string | undefined,
  testCaseId: string | undefined,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: testCaseVersionsKey(projectId, testCaseId),
    queryFn: () => testCasesApi.listTestCaseVersions(projectId as string, testCaseId as string),
    enabled: !!projectId && !!testCaseId && (options?.enabled ?? true),
  });
}

function invalidateTestCases(queryClient: ReturnType<typeof useQueryClient>, projectId: string | undefined) {
  queryClient.invalidateQueries({ queryKey: testCasesRootKey(projectId) });
}

export function useCreateTestCase(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: TestCaseCreateInput) => testCasesApi.createTestCase(projectId as string, input),
    onSuccess: () => invalidateTestCases(queryClient, projectId),
  });
}

export function useUpdateTestCase(projectId: string | undefined, testCaseId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: TestCaseUpdateInput) =>
      testCasesApi.updateTestCase(projectId as string, testCaseId as string, input),
    onSuccess: (data) => {
      queryClient.setQueryData(testCaseKey(projectId, testCaseId), data);
      invalidateTestCases(queryClient, projectId);
    },
  });
}

export function useApproveTestCase(projectId: string | undefined, testCaseId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => testCasesApi.approveTestCase(projectId as string, testCaseId as string),
    onSuccess: (data) => {
      queryClient.setQueryData(testCaseKey(projectId, testCaseId), data);
      invalidateTestCases(queryClient, projectId);
    },
  });
}

export function useDeleteTestCase(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (testCaseId: string) => testCasesApi.deleteTestCase(projectId as string, testCaseId),
    onSuccess: () => invalidateTestCases(queryClient, projectId),
  });
}
