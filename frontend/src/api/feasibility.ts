import { api } from './client';
import type { Feasibility, FeasibilityDetail, FeasibilityStudyPayload } from './types';

export function listFeasibilityStudies(
  projectId: string,
  requirementId: string,
): Promise<Feasibility[]> {
  return api.get<Feasibility[]>(`/projects/${projectId}/requirements/${requirementId}/feasibility`);
}

export function getFeasibilityStudy(
  projectId: string,
  requirementId: string,
  feasibilityId: string,
): Promise<FeasibilityDetail> {
  return api.get<FeasibilityDetail>(
    `/projects/${projectId}/requirements/${requirementId}/feasibility/${feasibilityId}`,
  );
}

export function createFeasibilityStudy(
  projectId: string,
  requirementId: string,
): Promise<FeasibilityDetail> {
  return api.post<FeasibilityDetail>(`/projects/${projectId}/requirements/${requirementId}/feasibility`);
}

export function updateFeasibilityStudy(
  projectId: string,
  requirementId: string,
  feasibilityId: string,
  payload: FeasibilityStudyPayload,
): Promise<FeasibilityDetail> {
  return api.patch<FeasibilityDetail>(
    `/projects/${projectId}/requirements/${requirementId}/feasibility/${feasibilityId}`,
    { payload },
  );
}

export function approveFeasibilityStudy(
  projectId: string,
  requirementId: string,
  feasibilityId: string,
): Promise<FeasibilityDetail> {
  return api.post<FeasibilityDetail>(
    `/projects/${projectId}/requirements/${requirementId}/feasibility/${feasibilityId}/approve`,
  );
}

export function rejectFeasibilityStudy(
  projectId: string,
  requirementId: string,
  feasibilityId: string,
): Promise<FeasibilityDetail> {
  return api.post<FeasibilityDetail>(
    `/projects/${projectId}/requirements/${requirementId}/feasibility/${feasibilityId}/reject`,
  );
}
