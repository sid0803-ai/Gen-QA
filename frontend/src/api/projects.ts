import { api } from './client';
import type {
  AddMemberInput,
  Project,
  ProjectCreateInput,
  ProjectMember,
  ProjectUpdateInput,
  ProjectWithRole,
  Role,
} from './types';

export function listProjects(): Promise<ProjectWithRole[]> {
  return api.get<ProjectWithRole[]>('/projects');
}

export function getProject(projectId: string): Promise<Project> {
  return api.get<Project>(`/projects/${projectId}`);
}

export function createProject(input: ProjectCreateInput): Promise<Project> {
  return api.post<Project>('/projects', input);
}

export function updateProject(projectId: string, input: ProjectUpdateInput): Promise<Project> {
  return api.patch<Project>(`/projects/${projectId}`, input);
}

export function deleteProject(projectId: string): Promise<void> {
  return api.delete<void>(`/projects/${projectId}`);
}

export function listMembers(projectId: string): Promise<ProjectMember[]> {
  return api.get<ProjectMember[]>(`/projects/${projectId}/members`);
}

export function addMember(projectId: string, input: AddMemberInput): Promise<ProjectMember> {
  return api.post<ProjectMember>(`/projects/${projectId}/members`, input);
}

export function updateMemberRole(
  projectId: string,
  userId: string,
  role: Role,
): Promise<ProjectMember> {
  return api.patch<ProjectMember>(`/projects/${projectId}/members/${userId}`, { role });
}

export function removeMember(projectId: string, userId: string): Promise<void> {
  return api.delete<void>(`/projects/${projectId}/members/${userId}`);
}
