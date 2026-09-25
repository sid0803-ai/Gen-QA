import type { ApiRequestMethod } from '../api/types';

/**
 * Single source of truth for HTTP method display across the app — the API
 * Performer's builder/tree and the planned Performance Testing module both
 * import from here rather than defining method colors inline per-page.
 *
 * Color scheme (Ant Design `Tag` color names), chosen to mirror Postman's
 * conventions while staying inside Ant Design's named palette:
 *  - GET     = blue    (safe, read-only)
 *  - POST    = green   (creates something)
 *  - PUT     = orange  (replaces/overwrites)
 *  - PATCH   = purple  (partial mutation — distinct from PUT despite both
 *              being "updates", since they have different semantics)
 *  - DELETE  = red     (destructive)
 *  - HEAD    = default (rare, read-only, no body — kept neutral)
 *  - OPTIONS = default (rare, metadata-only — kept neutral)
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
  GET: 'blue',
  POST: 'green',
  PUT: 'orange',
  PATCH: 'purple',
  DELETE: 'red',
  HEAD: 'default',
  OPTIONS: 'default',
};

/** Falls back to 'default' for any value that isn't a recognized method (defensive against loose `string` fields from the API). */
export function methodColor(method: string): string {
  return HTTP_METHOD_COLORS[method as ApiRequestMethod] ?? 'default';
}
