import { api } from './client';
import type {
  PerformanceTest,
  PerformanceTestCreateInput,
  PerformanceTestRun,
  PerformanceTestRunSummary,
  PerformanceTestUpdateInput,
} from './types';

export function listPerformanceTests(projectId: string): Promise<PerformanceTest[]> {
  return api.get<PerformanceTest[]>(`/projects/${projectId}/performance-tests`);
}

export function getPerformanceTest(
  projectId: string,
  testId: string,
): Promise<PerformanceTest> {
  return api.get<PerformanceTest>(`/projects/${projectId}/performance-tests/${testId}`);
}

export function createPerformanceTest(
  projectId: string,
  input: PerformanceTestCreateInput,
): Promise<PerformanceTest> {
  return api.post<PerformanceTest>(`/projects/${projectId}/performance-tests`, input);
}

export function updatePerformanceTest(
  projectId: string,
  testId: string,
  input: PerformanceTestUpdateInput,
): Promise<PerformanceTest> {
  return api.patch<PerformanceTest>(
    `/projects/${projectId}/performance-tests/${testId}`,
    input,
  );
}

export function deletePerformanceTest(projectId: string, testId: string): Promise<void> {
  return api.delete<void>(`/projects/${projectId}/performance-tests/${testId}`);
}

/** Triggers a new run — returns it in `queued` status. */
export function triggerPerformanceTestRun(
  projectId: string,
  testId: string,
): Promise<PerformanceTestRunSummary> {
  return api.post<PerformanceTestRunSummary>(
    `/projects/${projectId}/performance-tests/${testId}/runs`,
  );
}

/** Newest first, per the contract. `raw_summary` may be omitted on each entry. */
export function listPerformanceTestRuns(
  projectId: string,
  testId: string,
): Promise<PerformanceTestRunSummary[]> {
  return api.get<PerformanceTestRunSummary[]>(
    `/projects/${projectId}/performance-tests/${testId}/runs`,
  );
}

/** Full detail for one run, including `raw_summary`. */
export function getPerformanceTestRun(
  projectId: string,
  testId: string,
  runId: string,
): Promise<PerformanceTestRun> {
  return api.get<PerformanceTestRun>(
    `/projects/${projectId}/performance-tests/${testId}/runs/${runId}`,
  );
}
