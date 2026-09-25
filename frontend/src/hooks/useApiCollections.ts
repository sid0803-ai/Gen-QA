import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as apiCollectionsApi from '../api/apiCollections';
import type {
  ApiCollectionInput,
  ApiCollectionUpdateInput,
  ApiFolderInput,
  ApiFolderUpdateInput,
} from '../api/types';

export function apiCollectionsTreeKey(projectId: string | undefined) {
  return ['projects', projectId, 'api-collections', 'tree'] as const;
}

export function apiCollectionsKey(projectId: string | undefined) {
  return ['projects', projectId, 'api-collections'] as const;
}

/** The tree endpoint is the single source of truth for the sidebar — Collection -> Folder -> Request in one call. */
export function useApiCollectionsTree(projectId: string | undefined) {
  return useQuery({
    queryKey: apiCollectionsTreeKey(projectId),
    queryFn: () => apiCollectionsApi.getApiCollectionsTree(projectId as string),
    enabled: !!projectId,
  });
}

export function useApiCollections(projectId: string | undefined) {
  return useQuery({
    queryKey: apiCollectionsKey(projectId),
    queryFn: () => apiCollectionsApi.listApiCollections(projectId as string),
    enabled: !!projectId,
  });
}

function invalidateTree(
  queryClient: ReturnType<typeof useQueryClient>,
  projectId: string | undefined,
) {
  queryClient.invalidateQueries({ queryKey: apiCollectionsTreeKey(projectId) });
  queryClient.invalidateQueries({ queryKey: apiCollectionsKey(projectId) });
}

export function useCreateCollection(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ApiCollectionInput) =>
      apiCollectionsApi.createApiCollection(projectId as string, input),
    onSuccess: () => invalidateTree(queryClient, projectId),
  });
}

export function useUpdateCollection(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: ApiCollectionUpdateInput }) =>
      apiCollectionsApi.updateApiCollection(projectId as string, id, input),
    onSuccess: () => invalidateTree(queryClient, projectId),
  });
}

export function useDeleteCollection(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (collectionId: string) =>
      apiCollectionsApi.deleteApiCollection(projectId as string, collectionId),
    onSuccess: () => invalidateTree(queryClient, projectId),
  });
}

export function useCreateFolder(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ collectionId, input }: { collectionId: string; input: ApiFolderInput }) =>
      apiCollectionsApi.createApiFolder(projectId as string, collectionId, input),
    onSuccess: () => invalidateTree(queryClient, projectId),
  });
}

export function useUpdateFolder(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      collectionId,
      folderId,
      input,
    }: {
      collectionId: string;
      folderId: string;
      input: ApiFolderUpdateInput;
    }) => apiCollectionsApi.updateApiFolder(projectId as string, collectionId, folderId, input),
    onSuccess: () => invalidateTree(queryClient, projectId),
  });
}

export function useDeleteFolder(projectId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ collectionId, folderId }: { collectionId: string; folderId: string }) =>
      apiCollectionsApi.deleteApiFolder(projectId as string, collectionId, folderId),
    onSuccess: () => invalidateTree(queryClient, projectId),
  });
}
