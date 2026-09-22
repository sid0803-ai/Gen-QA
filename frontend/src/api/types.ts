// Types mirroring the backend API contract exactly (see project spec).
// Do not add fields the backend doesn't send; do not rename fields.

export type Role = 'admin' | 'member' | 'viewer';

export interface User {
  id: string;
  email: string;
  full_name: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}

/** Shape returned by GET /projects — includes the current user's role. */
export interface ProjectWithRole extends Project {
  role: Role;
}

export interface ProjectCreateInput {
  name: string;
  description?: string;
}

export interface ProjectUpdateInput {
  name?: string;
  description?: string;
}

export interface ProjectMember {
  user_id: string;
  email: string;
  full_name: string;
  role: Role;
}

export interface AddMemberInput {
  email: string;
  role: Role;
}
