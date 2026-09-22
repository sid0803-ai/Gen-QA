import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as projectsApi from '../api/projects';
import type { ProjectCreateInput, ProjectUpdateInput } from '../api/types';

export const projectsKey = ['projects'] as const;

export function useProjects() {
  return useQuery({
    queryKey: projectsKey,
    queryFn: projectsApi.listProjects,
  });
}

export function useProject(projectId: string | undefined) {
  return useQuery({
    queryKey: [...projectsKey, projectId],
    queryFn: () => projectsApi.getProject(projectId as string),
    enabled: !!projectId,
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ProjectCreateInput) => projectsApi.createProject(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectsKey });
    },
  });
}

export function useUpdateProject(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ProjectUpdateInput) => projectsApi.updateProject(projectId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectsKey });
    },
  });
}
