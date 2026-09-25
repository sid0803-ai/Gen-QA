import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as apiPerformerApi from '../api/apiPerformer';
import type {
  ApiRequestExecuteInput,
  SavedApiRequestCreateInput,
  SavedApiRequestInput,
} from '../api/types';
import { apiCollectionsTreeKey } from './useApiCollections';

export function savedRequestsKey(projectId: string | undefined) {
  return ['projects', projectId, 'api-requests'] as const;
}

export function savedRequestKey(projectId: string | undefined, requestId: string | undefined) {
  return [...savedRequestsKey(projectId), requestId] as const;
}

export function useSavedRequests(projectId: string | undefined) {
  return useQuery({
    queryKey: savedRequestsKey(projectId),
    queryFn: () => apiPerformerApi.listSavedRequests(projectId as string),
    enabled: !!projectId,
  });
}

export function useSavedRequest(projectId: string | undefined, requestId: string | undefined) {
  return useQuery({
    queryKey: savedRequestKey(projectId, requestId),
    queryFn: () => apiPerformerApi.getSavedRequest(projectId as string, requestId as string),
    enabled: !!projectId && !!requestId,
  });
}

export function useCreateSavedRequest(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: SavedApiRequestCreateInput) =>
      apiPerformerApi.createSavedRequest(projectId as string, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: savedRequestsKey(projectId) });
      queryClient.invalidateQueries({ queryKey: apiCollectionsTreeKey(projectId) });
    },
  });
}

export function useUpdateSavedRequest(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: SavedApiRequestInput }) =>
      apiPerformerApi.updateSavedRequest(projectId as string, id, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: savedRequestsKey(projectId) });
      queryClient.invalidateQueries({ queryKey: apiCollectionsTreeKey(projectId) });
    },
  });
}

export function useDeleteSavedRequest(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (requestId: string) =>
      apiPerformerApi.deleteSavedRequest(projectId as string, requestId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: savedRequestsKey(projectId) });
      queryClient.invalidateQueries({ queryKey: apiCollectionsTreeKey(projectId) });
    },
  });
}

/**
 * Ad-hoc execution result is ephemeral (shown in the response panel, never cached/refetched),
 * so this is a plain mutation rather than a query.
 */
export function useExecuteAdHocRequest(projectId: string | undefined) {
  return useMutation({
    mutationFn: (input: ApiRequestExecuteInput) =>
      apiPerformerApi.executeAdHocRequest(projectId as string, input),
  });
}

export function useExecuteSavedRequest(projectId: string | undefined) {
  return useMutation({
    mutationFn: ({ id, environmentId }: { id: string; environmentId?: string }) =>
      apiPerformerApi.executeSavedRequest(
        projectId as string,
        id,
        environmentId !== undefined ? { environment_id: environmentId } : undefined,
      ),
  });
}
