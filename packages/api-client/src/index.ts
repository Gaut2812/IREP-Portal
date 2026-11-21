/**
 * @irep/api-client — types generated from apps/api/openapi.json.
 *
 * Regenerate after any API change (CI fails when this is stale):
 *   cd packages/api-client && npm run generate
 *
 * Use type-only imports from the web app:
 *   import type { RequestBody, JsonResponse } from "@irep/api-client";
 *   type NewCollege = RequestBody<"/api/v1/admin/colleges", "post">;
 */
import type { components, paths } from "./schema";

export type { components, paths };
export type Schemas = components["schemas"];
export type Method = "get" | "post" | "put" | "delete" | "patch";

/** JSON request body of an operation (never if it takes none). */
export type RequestBody<P extends keyof paths, M extends Method> =
  paths[P][M] extends { requestBody?: { content: { "application/json": infer B } } } ? B : never;

/** JSON body of the 200/201 response (unknown for endpoints without a response model). */
export type JsonResponse<P extends keyof paths, M extends Method> =
  paths[P][M] extends { responses: { 200: { content: { "application/json": infer R } } } } ? R
    : paths[P][M] extends { responses: { 201: { content: { "application/json": infer R } } } } ? R
      : never;

/** Query parameters of an operation. */
export type QueryParams<P extends keyof paths, M extends Method> =
  paths[P][M] extends { parameters: { query?: infer Q } } ? Q : never;
