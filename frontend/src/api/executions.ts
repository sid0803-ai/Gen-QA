import { api } from './client';
import type { Execution, ExecutionCreateInput, ExecutionListParams } from './types';

function buildListQuery(params: ExecutionListParams): string {
  const search = new URLSearchParams();
  if (params.test_case_id) search.set('test_case_id', params.test_case_id);
  if (params.status) search.set('status', params.status);
  if (params.type) search.set('type', params.type);
  if (params.environment_id) search.set('environment_id', params.environment_id);
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

export function listExecutions(
  projectId: string,
  params: ExecutionListParams = {},
): Promise<Execution[]> {
  return api.get<Execution[]>(`/projects/${projectId}/executions${buildListQuery(params)}`);
}

export function getExecution(projectId: string, executionId: string): Promise<Execution> {
  return api.get<Execution>(`/projects/${projectId}/executions/${executionId}`);
}

export function createExecution(
  projectId: string,
  input: ExecutionCreateInput,
): Promise<Execution> {
  return api.post<Execution>(`/projects/${projectId}/executions`, input);
}
