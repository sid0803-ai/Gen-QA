import { api } from './client';
import type {
  ApiCollection,
  ApiCollectionInput,
  ApiCollectionTreeNode,
  ApiCollectionUpdateInput,
  ApiFolder,
  ApiFolderInput,
  ApiFolderUpdateInput,
} from './types';

/** GET /projects/{id}/api-collections/tree — Collection -> Folder (optional) -> Request, one call for the whole sidebar. */
export function getApiCollectionsTree(projectId: string): Promise<ApiCollectionTreeNode[]> {
  return api.get<ApiCollectionTreeNode[]>(`/projects/${projectId}/api-collections/tree`);
}

export function listApiCollections(projectId: string): Promise<ApiCollection[]> {
  return api.get<ApiCollection[]>(`/projects/${projectId}/api-collections`);
}

export function createApiCollection(
  projectId: string,
  input: ApiCollectionInput,
): Promise<ApiCollection> {
  return api.post<ApiCollection>(`/projects/${projectId}/api-collections`, input);
}

export function updateApiCollection(
  projectId: string,
  collectionId: string,
  input: ApiCollectionUpdateInput,
): Promise<ApiCollection> {
  return api.patch<ApiCollection>(
    `/projects/${projectId}/api-collections/${collectionId}`,
    input,
  );
}

/** Cascades: also deletes the collection's folders and requests. */
export function deleteApiCollection(projectId: string, collectionId: string): Promise<void> {
  return api.delete<void>(`/projects/${projectId}/api-collections/${collectionId}`);
}

export function listApiFolders(projectId: string, collectionId: string): Promise<ApiFolder[]> {
  return api.get<ApiFolder[]>(`/projects/${projectId}/api-collections/${collectionId}/folders`);
}

export function createApiFolder(
  projectId: string,
  collectionId: string,
  input: ApiFolderInput,
): Promise<ApiFolder> {
  return api.post<ApiFolder>(
    `/projects/${projectId}/api-collections/${collectionId}/folders`,
    input,
  );
}

export function updateApiFolder(
  projectId: string,
  collectionId: string,
  folderId: string,
  input: ApiFolderUpdateInput,
): Promise<ApiFolder> {
  return api.patch<ApiFolder>(
    `/projects/${projectId}/api-collections/${collectionId}/folders/${folderId}`,
    input,
  );
}

/** Un-files the folder's requests (their `folder_id` becomes null) rather than deleting them. */
export function deleteApiFolder(
  projectId: string,
  collectionId: string,
  folderId: string,
): Promise<void> {
  return api.delete<void>(
    `/projects/${projectId}/api-collections/${collectionId}/folders/${folderId}`,
  );
}
