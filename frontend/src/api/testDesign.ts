import { api } from './client';
import type { TestDesign, TestDesignDetail, TestDesignPayload, TestDesignScope } from './types';

/** Options for the scope picker shown next to the Test Design "Generate" button. */
export const TEST_DESIGN_SCOPE_OPTIONS: { value: TestDesignScope; label: string }[] = [
  { value: 'api', label: 'API' },
  { value: 'ui', label: 'UI' },
  { value: 'both', label: 'Both' },
];

export function listTestDesigns(projectId: string, requirementId: string): Promise<TestDesign[]> {
  return api.get<TestDesign[]>(`/projects/${projectId}/requirements/${requirementId}/test-design`);
}

export function getTestDesign(
  projectId: string,
  requirementId: string,
  testDesignId: string,
): Promise<TestDesignDetail> {
  return api.get<TestDesignDetail>(
    `/projects/${projectId}/requirements/${requirementId}/test-design/${testDesignId}`,
  );
}

export function createTestDesign(
  projectId: string,
  requirementId: string,
  scope: TestDesignScope,
): Promise<TestDesignDetail> {
  return api.post<TestDesignDetail>(`/projects/${projectId}/requirements/${requirementId}/test-design`, {
    scope,
  });
}

export function updateTestDesign(
  projectId: string,
  requirementId: string,
  testDesignId: string,
  payload: TestDesignPayload,
): Promise<TestDesignDetail> {
  return api.patch<TestDesignDetail>(
    `/projects/${projectId}/requirements/${requirementId}/test-design/${testDesignId}`,
    { payload },
  );
}

export function approveTestDesign(
  projectId: string,
  requirementId: string,
  testDesignId: string,
): Promise<TestDesignDetail> {
  return api.post<TestDesignDetail>(
    `/projects/${projectId}/requirements/${requirementId}/test-design/${testDesignId}/approve`,
  );
}

export function rejectTestDesign(
  projectId: string,
  requirementId: string,
  testDesignId: string,
): Promise<TestDesignDetail> {
  return api.post<TestDesignDetail>(
    `/projects/${projectId}/requirements/${requirementId}/test-design/${testDesignId}/reject`,
  );
}
