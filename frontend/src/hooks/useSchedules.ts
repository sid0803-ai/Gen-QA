import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as schedulesApi from '../api/schedules';
import type { ScheduledJobCreateInput, ScheduledJobUpdateInput } from '../api/types';

export function schedulesKey(projectId: string | undefined) {
  return ['projects', projectId, 'schedules'] as const;
}

export function scheduleKey(projectId: string | undefined, scheduleId: string | undefined) {
  return [...schedulesKey(projectId), scheduleId] as const;
}

/**
 * The dashboard's `scheduled_jobs_count` tile derives from this same data
 * server-side, so mutations here also invalidate the dashboard query
 * (same key shape as `useProjectDashboard` in useReports.ts) to keep that
 * tile in sync without a manual refetch.
 */
function dashboardKey(projectId: string | undefined) {
  return ['projects', projectId, 'reports', 'dashboard'] as const;
}

export function useSchedules(projectId: string | undefined) {
  return useQuery({
    queryKey: schedulesKey(projectId),
    queryFn: () => schedulesApi.listSchedules(projectId as string),
    enabled: !!projectId,
  });
}

export function useSchedule(projectId: string | undefined, scheduleId: string | undefined) {
  return useQuery({
    queryKey: scheduleKey(projectId, scheduleId),
    queryFn: () => schedulesApi.getSchedule(projectId as string, scheduleId as string),
    enabled: !!projectId && !!scheduleId,
  });
}

function invalidateSchedules(queryClient: ReturnType<typeof useQueryClient>, projectId: string | undefined) {
  queryClient.invalidateQueries({ queryKey: schedulesKey(projectId) });
  queryClient.invalidateQueries({ queryKey: dashboardKey(projectId) });
}

export function useCreateSchedule(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ScheduledJobCreateInput) => schedulesApi.createSchedule(projectId as string, input),
    onSuccess: () => invalidateSchedules(queryClient, projectId),
  });
}

export function useUpdateSchedule(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: ScheduledJobUpdateInput }) =>
      schedulesApi.updateSchedule(projectId as string, id, input),
    onSuccess: (data) => {
      queryClient.setQueryData(scheduleKey(projectId, data.id), data);
      invalidateSchedules(queryClient, projectId);
    },
  });
}

export function useDeleteSchedule(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (scheduleId: string) => schedulesApi.deleteSchedule(projectId as string, scheduleId),
    onSuccess: () => invalidateSchedules(queryClient, projectId),
  });
}
