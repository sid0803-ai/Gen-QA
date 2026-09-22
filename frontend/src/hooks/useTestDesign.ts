import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as testDesignApi from '../api/testDesign';
import { requirementsKey } from './useRequirements';
import type { TestDesignPayload, TestDesignScope } from '../api/types';

export function testDesignsKey(projectId: string | undefined, requirementId: string | undefined) {
  return ['projects', projectId, 'requirements', requirementId, 'test-design'] as const;
}

export function testDesignKey(
  projectId: string | undefined,
  requirementId: string | undefined,
  testDesignId: string | undefined,
) {
  return [...testDesignsKey(projectId, requirementId), testDesignId] as const;
}

/** List of test designs for a requirement, newest first. List items omit `payload`. */
export function useTestDesigns(projectId: string | undefined, requirementId: string | undefined) {
  return useQuery({
    queryKey: testDesignsKey(projectId, requirementId),
    queryFn: () => testDesignApi.listTestDesigns(projectId as string, requirementId as string),
    enabled: !!projectId && !!requirementId,
  });
}

/** Full test design detail (incl. payload). Pass `enabled: false` to defer fetching until needed. */
export function useTestDesign(
  projectId: string | undefined,
  requirementId: string | undefined,
  testDesignId: string | undefined,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: testDesignKey(projectId, requirementId, testDesignId),
    queryFn: () =>
      testDesignApi.getTestDesign(projectId as string, requirementId as string, testDesignId as string),
    enabled: !!projectId && !!requirementId && !!testDesignId && (options?.enabled ?? true),
  });
}

/** Requirement list rows carry `latest_test_design_status`, so also invalidate that list. */
function invalidateTestDesignRelated(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId: string | undefined,
  requirementId: string | undefined,
) {
  queryClient.invalidateQueries({ queryKey: testDesignsKey(projectId, requirementId) });
  queryClient.invalidateQueries({ queryKey: requirementsKey(projectId) });
}

export function useCreateTestDesign(projectId: string | undefined, requirementId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (scope: TestDesignScope) =>
      testDesignApi.createTestDesign(projectId as string, requirementId as string, scope),
    onSuccess: (data) => {
      queryClient.setQueryData(testDesignKey(projectId, requirementId, data.id), data);
      invalidateTestDesignRelated(queryClient, projectId, requirementId);
    },
  });
}

export function useUpdateTestDesign(
  projectId: string | undefined,
  requirementId: string | undefined,
  testDesignId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TestDesignPayload) =>
      testDesignApi.updateTestDesign(
        projectId as string,
        requirementId as string,
        testDesignId as string,
        payload,
      ),
    onSuccess: (data) => {
      queryClient.setQueryData(testDesignKey(projectId, requirementId, testDesignId), data);
      queryClient.invalidateQueries({ queryKey: testDesignsKey(projectId, requirementId) });
    },
  });
}

export function useApproveTestDesign(
  projectId: string | undefined,
  requirementId: string | undefined,
  testDesignId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      testDesignApi.approveTestDesign(projectId as string, requirementId as string, testDesignId as string),
    onSuccess: (data) => {
      queryClient.setQueryData(testDesignKey(projectId, requirementId, testDesignId), data);
      invalidateTestDesignRelated(queryClient, projectId, requirementId);
      // Approving promotes included scenarios into real Test Cases server-side.
      queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'test-cases'] });
    },
  });
}

export function useRejectTestDesign(
  projectId: string | undefined,
  requirementId: string | undefined,
  testDesignId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      testDesignApi.rejectTestDesign(projectId as string, requirementId as string, testDesignId as string),
    onSuccess: (data) => {
      queryClient.setQueryData(testDesignKey(projectId, requirementId, testDesignId), data);
      invalidateTestDesignRelated(queryClient, projectId, requirementId);
    },
  });
}
