import { api } from './client';
import type { ScheduledJob, ScheduledJobCreateInput, ScheduledJobUpdateInput } from './types';

export function listSchedules(projectId: string): Promise<ScheduledJob[]> {
  return api.get<ScheduledJob[]>(`/projects/${projectId}/schedules`);
}

export function getSchedule(projectId: string, scheduleId: string): Promise<ScheduledJob> {
  return api.get<ScheduledJob>(`/projects/${projectId}/schedules/${scheduleId}`);
}

export function createSchedule(
  projectId: string,
  input: ScheduledJobCreateInput,
): Promise<ScheduledJob> {
  return api.post<ScheduledJob>(`/projects/${projectId}/schedules`, input);
}

export function updateSchedule(
  projectId: string,
  scheduleId: string,
  input: ScheduledJobUpdateInput,
): Promise<ScheduledJob> {
  return api.patch<ScheduledJob>(`/projects/${projectId}/schedules/${scheduleId}`, input);
}

export function deleteSchedule(projectId: string, scheduleId: string): Promise<void> {
  return api.delete<void>(`/projects/${projectId}/schedules/${scheduleId}`);
}
