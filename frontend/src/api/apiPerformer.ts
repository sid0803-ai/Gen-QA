import { api } from './client';
import type {
  ApiExecuteResult,
  ApiRequestExecuteInput,
  SavedApiRequest,
  SavedApiRequestInput,
} from './types';

export function listSavedRequests(projectId: string): Promise<SavedApiRequest[]> {
  return api.get<SavedApiRequest[]>(`/projects/${projectId}/api-requests`);
}

export function getSavedRequest(
  projectId: string,
  requestId: string,
): Promise<SavedApiRequest> {
  return api.get<SavedApiRequest>(`/projects/${projectId}/api-requests/${requestId}`);
}

export function createSavedRequest(
  projectId: string,
  input: SavedApiRequestInput,
): Promise<SavedApiRequest> {
  return api.post<SavedApiRequest>(`/projects/${projectId}/api-requests`, input);
}

export function updateSavedRequest(
  projectId: string,
  requestId: string,
  input: SavedApiRequestInput,
): Promise<SavedApiRequest> {
  return api.patch<SavedApiRequest>(`/projects/${projectId}/api-requests/${requestId}`, input);
}

export function deleteSavedRequest(projectId: string, requestId: string): Promise<void> {
  return api.delete<void>(`/projects/${projectId}/api-requests/${requestId}`);
}

/** Ad-hoc execution — nothing is saved. */
export function executeAdHocRequest(
  projectId: string,
  input: ApiRequestExecuteInput,
): Promise<ApiExecuteResult> {
  return api.post<ApiExecuteResult>(`/projects/${projectId}/api-requests/execute`, input);
}

/** Executes a saved request; `input.environment_id` optionally overrides its own environment for this one run. */
export function executeSavedRequest(
  projectId: string,
  requestId: string,
  input?: { environment_id?: string },
): Promise<ApiExecuteResult> {
  return api.post<ApiExecuteResult>(
    `/projects/${projectId}/api-requests/${requestId}/execute`,
    input,
  );
}
