import { api } from './client';
import type {
  Analysis,
  AnalysisDetail,
  Requirement,
  RequirementAnalysisPayload,
  RequirementCreateInput,
  RequirementSummary,
  RequirementUpdateInput,
} from './types';

export function listRequirements(projectId: string): Promise<RequirementSummary[]> {
  return api.get<RequirementSummary[]>(`/projects/${projectId}/requirements`);
}

export function getRequirement(projectId: string, requirementId: string): Promise<Requirement> {
  return api.get<Requirement>(`/projects/${projectId}/requirements/${requirementId}`);
}

export function createRequirement(
  projectId: string,
  input: RequirementCreateInput,
): Promise<Requirement> {
  return api.post<Requirement>(`/projects/${projectId}/requirements`, input);
}

export function updateRequirement(
  projectId: string,
  requirementId: string,
  input: RequirementUpdateInput,
): Promise<Requirement> {
  return api.patch<Requirement>(`/projects/${projectId}/requirements/${requirementId}`, input);
}

export function deleteRequirement(projectId: string, requirementId: string): Promise<void> {
  return api.delete<void>(`/projects/${projectId}/requirements/${requirementId}`);
}

export function listAnalyses(projectId: string, requirementId: string): Promise<Analysis[]> {
  return api.get<Analysis[]>(`/projects/${projectId}/requirements/${requirementId}/analyses`);
}

export function getAnalysis(
  projectId: string,
  requirementId: string,
  analysisId: string,
): Promise<AnalysisDetail> {
  return api.get<AnalysisDetail>(
    `/projects/${projectId}/requirements/${requirementId}/analyses/${analysisId}`,
  );
}

export function createAnalysis(
  projectId: string,
  requirementId: string,
): Promise<AnalysisDetail> {
  return api.post<AnalysisDetail>(`/projects/${projectId}/requirements/${requirementId}/analyses`);
}

export function updateAnalysis(
  projectId: string,
  requirementId: string,
  analysisId: string,
  payload: RequirementAnalysisPayload,
): Promise<AnalysisDetail> {
  return api.patch<AnalysisDetail>(
    `/projects/${projectId}/requirements/${requirementId}/analyses/${analysisId}`,
    { payload },
  );
}

export function approveAnalysis(
  projectId: string,
  requirementId: string,
  analysisId: string,
): Promise<AnalysisDetail> {
  return api.post<AnalysisDetail>(
    `/projects/${projectId}/requirements/${requirementId}/analyses/${analysisId}/approve`,
  );
}

export function rejectAnalysis(
  projectId: string,
  requirementId: string,
  analysisId: string,
): Promise<AnalysisDetail> {
  return api.post<AnalysisDetail>(
    `/projects/${projectId}/requirements/${requirementId}/analyses/${analysisId}/reject`,
  );
}
