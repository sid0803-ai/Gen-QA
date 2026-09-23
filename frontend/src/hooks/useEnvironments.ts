import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as environmentsApi from '../api/environments';
import type { EnvironmentCreateInput, EnvironmentUpdateInput } from '../api/types';

export function environmentsKey(projectId: string | undefined) {
  return ['projects', projectId, 'environments'] as const;
}

export function environmentKey(projectId: string | undefined, environmentId: string | undefined) {
  return [...environmentsKey(projectId), environmentId] as const;
}

export function useEnvironments(projectId: string | undefined) {
  return useQuery({
    queryKey: environmentsKey(projectId),
    queryFn: () => environmentsApi.listEnvironments(projectId as string),
    enabled: !!projectId,
  });
}

export function useEnvironment(projectId: string | undefined, environmentId: string | undefined) {
  return useQuery({
    queryKey: environmentKey(projectId, environmentId),
    queryFn: () => environmentsApi.getEnvironment(projectId as string, environmentId as string),
    enabled: !!projectId && !!environmentId,
  });
}

export function useCreateEnvironment(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: EnvironmentCreateInput) =>
      environmentsApi.createEnvironment(projectId as string, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: environmentsKey(projectId) });
    },
  });
}

export function useUpdateEnvironment(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: EnvironmentUpdateInput }) =>
      environmentsApi.updateEnvironment(projectId as string, id, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: environmentsKey(projectId) });
    },
  });
}

export function useDeleteEnvironment(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (environmentId: string) =>
      environmentsApi.deleteEnvironment(projectId as string, environmentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: environmentsKey(projectId) });
    },
  });
}
