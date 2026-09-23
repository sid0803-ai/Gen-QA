import { api } from './client';
import type { Environment, EnvironmentCreateInput, EnvironmentUpdateInput } from './types';

export function listEnvironments(projectId: string): Promise<Environment[]> {
  return api.get<Environment[]>(`/projects/${projectId}/environments`);
}

export function getEnvironment(projectId: string, environmentId: string): Promise<Environment> {
  return api.get<Environment>(`/projects/${projectId}/environments/${environmentId}`);
}

export function createEnvironment(
  projectId: string,
  input: EnvironmentCreateInput,
): Promise<Environment> {
  return api.post<Environment>(`/projects/${projectId}/environments`, input);
}

export function updateEnvironment(
  projectId: string,
  environmentId: string,
  input: EnvironmentUpdateInput,
): Promise<Environment> {
  return api.patch<Environment>(`/projects/${projectId}/environments/${environmentId}`, input);
}

export function deleteEnvironment(projectId: string, environmentId: string): Promise<void> {
  return api.delete<void>(`/projects/${projectId}/environments/${environmentId}`);
}
