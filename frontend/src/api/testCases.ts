import { api } from './client';
import type {
  TestCase,
  TestCaseCreateInput,
  TestCaseListParams,
  TestCaseSummary,
  TestCaseUpdateInput,
  TestCaseVersion,
} from './types';

function buildListQuery(params: TestCaseListParams): string {
  const search = new URLSearchParams();
  if (params.requirement_id) search.set('requirement_id', params.requirement_id);
  if (params.testing_level) search.set('testing_level', params.testing_level);
  if (params.category) search.set('category', params.category);
  if (params.priority) search.set('priority', params.priority);
  if (params.status) search.set('status', params.status);
  if (params.automation_candidate !== undefined) {
    search.set('automation_candidate', String(params.automation_candidate));
  }
  if (params.search) search.set('search', params.search);
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

/** Test cases span all requirements in a project — not nested under one requirement. */
export function listTestCases(
  projectId: string,
  params: TestCaseListParams = {},
): Promise<TestCaseSummary[]> {
  return api.get<TestCaseSummary[]>(`/projects/${projectId}/test-cases${buildListQuery(params)}`);
}

export function getTestCase(projectId: string, testCaseId: string): Promise<TestCase> {
  return api.get<TestCase>(`/projects/${projectId}/test-cases/${testCaseId}`);
}

export function createTestCase(projectId: string, input: TestCaseCreateInput): Promise<TestCase> {
  return api.post<TestCase>(`/projects/${projectId}/test-cases`, input);
}

export function updateTestCase(
  projectId: string,
  testCaseId: string,
  input: TestCaseUpdateInput,
): Promise<TestCase> {
  return api.patch<TestCase>(`/projects/${projectId}/test-cases/${testCaseId}`, input);
}

export function approveTestCase(projectId: string, testCaseId: string): Promise<TestCase> {
  return api.post<TestCase>(`/projects/${projectId}/test-cases/${testCaseId}/approve`);
}

export function deleteTestCase(projectId: string, testCaseId: string): Promise<void> {
  return api.delete<void>(`/projects/${projectId}/test-cases/${testCaseId}`);
}

export function listTestCaseVersions(
  projectId: string,
  testCaseId: string,
): Promise<TestCaseVersion[]> {
  return api.get<TestCaseVersion[]>(`/projects/${projectId}/test-cases/${testCaseId}/versions`);
}
