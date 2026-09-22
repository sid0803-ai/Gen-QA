import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as requirementsApi from '../api/requirements';
import type { RequirementCreateInput, RequirementUpdateInput } from '../api/types';

export function requirementsKey(projectId: string | undefined) {
  return ['projects', projectId, 'requirements'] as const;
}

export function requirementKey(projectId: string | undefined, requirementId: string | undefined) {
  return ['projects', projectId, 'requirements', requirementId] as const;
}

export function useRequirements(projectId: string | undefined) {
  return useQuery({
    queryKey: requirementsKey(projectId),
    queryFn: () => requirementsApi.listRequirements(projectId as string),
    enabled: !!projectId,
  });
}

export function useRequirement(projectId: string | undefined, requirementId: string | undefined) {
  return useQuery({
    queryKey: requirementKey(projectId, requirementId),
    queryFn: () => requirementsApi.getRequirement(projectId as string, requirementId as string),
    enabled: !!projectId && !!requirementId,
  });
}

export function useCreateRequirement(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: RequirementCreateInput) =>
      requirementsApi.createRequirement(projectId as string, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: requirementsKey(projectId) });
    },
  });
}

export function useUpdateRequirement(
  projectId: string | undefined,
  requirementId: string | undefined,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: RequirementUpdateInput) =>
      requirementsApi.updateRequirement(projectId as string, requirementId as string, input),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: requirementsKey(projectId) });
      queryClient.setQueryData(requirementKey(projectId, requirementId), data);
    },
  });
}

export function useDeleteRequirement(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (requirementId: string) =>
      requirementsApi.deleteRequirement(projectId as string, requirementId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: requirementsKey(projectId) });
    },
  });
}
