import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as projectsApi from '../api/projects';
import type { Role } from '../api/types';

function membersKey(projectId: string | undefined) {
  return ['projects', projectId, 'members'] as const;
}

export function useProjectMembers(projectId: string | undefined) {
  return useQuery({
    queryKey: membersKey(projectId),
    queryFn: () => projectsApi.listMembers(projectId as string),
    enabled: !!projectId,
  });
}

export function useAddMember(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { email: string; role: Role }) =>
      projectsApi.addMember(projectId as string, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: membersKey(projectId) });
    },
  });
}

export function useUpdateMemberRole(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: Role }) =>
      projectsApi.updateMemberRole(projectId as string, userId, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: membersKey(projectId) });
    },
  });
}

export function useRemoveMember(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => projectsApi.removeMember(projectId as string, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: membersKey(projectId) });
    },
  });
}
