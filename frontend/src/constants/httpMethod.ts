import type { ApiRequestMethod } from '../api/types';

/**
 * Single source of truth for HTTP method display across the app — the API
 * Performer's builder/tree/breadcrumb and the planned Performance Testing
 * module both import from here rather than defining method colors inline
 * per-component.
 *
 * Color scheme (hex, since Ant Design's `Tag` `color` prop accepts either a
 * named preset or a raw hex, and hex lets us match Postman's actual palette
 * instead of settling for the nearest named preset):
 *  - GET     = teal/green  (#00a879) — safe, read-only
 *  - POST    = amber/orange (#e8912d) — creates something
 *  - PUT     = blue        (#3b82f6) — replaces/overwrites
 *  - PATCH   = purple/violet (#8b5cf6) — partial mutation, distinct from PUT
 *  - DELETE  = red/pink    (#f5365c) — destructive
 *  - HEAD    = teal        (#0ea5a5) — rare, read-only, no body
 *  - OPTIONS = pink        (#d6336c) — rare, metadata-only
 */
export const HTTP_METHODS: ApiRequestMethod[] = [
  'GET',
  'POST',
  'PUT',
  'PATCH',
  'DELETE',
  'HEAD',
  'OPTIONS',
];

export const HTTP_METHOD_COLORS: Record<ApiRequestMethod, string> = {
  GET: '#00a879',
  POST: '#e8912d',
  PUT: '#3b82f6',
  PATCH: '#8b5cf6',
  DELETE: '#f5365c',
  HEAD: '#0ea5a5',
  OPTIONS: '#d6336c',
};

/** Falls back to 'default' for any value that isn't a recognized method (defensive against loose `string` fields from the API). */
export function methodColor(method: string): string {
  return HTTP_METHOD_COLORS[method as ApiRequestMethod] ?? 'default';
}
