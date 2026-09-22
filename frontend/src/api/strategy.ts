import { api } from './client';
import type { Strategy, StrategyDetail, TestStrategyPayload } from './types';

export function listStrategies(projectId: string, requirementId: string): Promise<Strategy[]> {
  return api.get<Strategy[]>(`/projects/${projectId}/requirements/${requirementId}/strategy`);
}

export function getStrategy(
  projectId: string,
  requirementId: string,
  strategyId: string,
): Promise<StrategyDetail> {
  return api.get<StrategyDetail>(
    `/projects/${projectId}/requirements/${requirementId}/strategy/${strategyId}`,
  );
}

export function createStrategy(projectId: string, requirementId: string): Promise<StrategyDetail> {
  return api.post<StrategyDetail>(`/projects/${projectId}/requirements/${requirementId}/strategy`);
}

export function updateStrategy(
  projectId: string,
  requirementId: string,
  strategyId: string,
  payload: TestStrategyPayload,
): Promise<StrategyDetail> {
  return api.patch<StrategyDetail>(
    `/projects/${projectId}/requirements/${requirementId}/strategy/${strategyId}`,
    { payload },
  );
}

export function approveStrategy(
  projectId: string,
  requirementId: string,
  strategyId: string,
): Promise<StrategyDetail> {
  return api.post<StrategyDetail>(
    `/projects/${projectId}/requirements/${requirementId}/strategy/${strategyId}/approve`,
  );
}

export function rejectStrategy(
  projectId: string,
  requirementId: string,
  strategyId: string,
): Promise<StrategyDetail> {
  return api.post<StrategyDetail>(
    `/projects/${projectId}/requirements/${requirementId}/strategy/${strategyId}/reject`,
  );
}
