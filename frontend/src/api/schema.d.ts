/**
 * Generated from app.main FastAPI OpenAPI snapshot.
 * Run `npm run gen:api` to regenerate with openapi-typescript.
 */

export interface paths {
  "/scans": {
    parameters: { query?: never; header?: never; path?: never; cookie?: never };
    get?: never;
    put?: never;
    post: operations["create_scan_scans_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/scans/{scan_id}": {
    parameters: { query?: never; header?: never; path?: never; cookie?: never };
    get: operations["get_scan_scans__scan_id__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/": {
    parameters: { query?: never; header?: never; path?: never; cookie?: never };
    get: operations["home__get"];
    put?: never;
    post?: never;
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/results": {
    parameters: { query?: never; header?: never; path?: never; cookie?: never };
    get?: never;
    put?: never;
    post: operations["results_results_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
  "/api/scan": {
    parameters: { query?: never; header?: never; path?: never; cookie?: never };
    get?: never;
    put?: never;
    post: operations["api_scan_api_scan_post"];
    delete?: never;
    options?: never;
    head?: never;
    patch?: never;
    trace?: never;
  };
}

export type webhooks = Record<string, never>;

export interface components {
  schemas: {
    "Body_api_scan_api_scan_post": { "url"?: string | null; "files"?: string[] };
    "Body_results_results_post": { "url"?: string | null; "files"?: string[] };
    "HTTPValidationError": { "detail"?: components["schemas"]["ValidationError"][] };
    "RepoScanCreate": { "repo_url": string };
    "ScanAccepted": { "scan_id": string; "status": components["schemas"]["ScanStatus"] };
    "ScanRead": { "scan_id": string; "status": components["schemas"]["ScanStatus"]; "repo_url"?: string | null; "component_count"?: number; "created_at"?: string | null; "completed_at"?: string | null; "error_message"?: string | null };
    "ScanStatus": 'queued' | 'cloning' | 'scanning' | 'normalizing' | 'persisting' | 'completed' | 'failed';
    "ValidationError": { "loc": (string | number)[]; "msg": string; "type": string; "input"?: unknown; "ctx"?: Record<string, unknown> };
  };
  responses: never;
  parameters: never;
  requestBodies: never;
  headers: never;
  pathItems: never;
}

export type $defs = Record<string, never>;

export interface operations {
  "create_scan_scans_post": {
    parameters: { query?: never; header?: never; path?: never; cookie?: never };
    requestBody: {
      content: {
        "application/json": components["schemas"]["RepoScanCreate"];
      };
    };
    responses: {
      202: {
        headers: { [name: string]: unknown };
        content: {
          "application/json": components["schemas"]["ScanAccepted"];
        };
      };
      422: {
        headers: { [name: string]: unknown };
        content?: never;
      };
      503: {
        headers: { [name: string]: unknown };
        content?: never;
      };
    };
  };
  "get_scan_scans__scan_id__get": {
    parameters: {
      query?: never;
      header?: never;
      path: {
        "scan_id": string;
      };
      cookie?: never;
    };
    requestBody?: never;
    responses: {
      200: {
        headers: { [name: string]: unknown };
        content: {
          "application/json": components["schemas"]["ScanRead"];
        };
      };
      404: {
        headers: { [name: string]: unknown };
        content?: never;
      };
      422: {
        headers: { [name: string]: unknown };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  "home__get": {
    parameters: { query?: never; header?: never; path?: never; cookie?: never };
    requestBody?: never;
    responses: {
      200: {
        headers: { [name: string]: unknown };
        content: {
          "application/json": unknown;
        };
      };
    };
  };
  "results_results_post": {
    parameters: { query?: never; header?: never; path?: never; cookie?: never };
    requestBody?: {
      content: {
        "multipart/form-data": components["schemas"]["Body_results_results_post"];
      };
    };
    responses: {
      200: {
        headers: { [name: string]: unknown };
        content: {
          "application/json": unknown;
        };
      };
      422: {
        headers: { [name: string]: unknown };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
  "api_scan_api_scan_post": {
    parameters: { query?: never; header?: never; path?: never; cookie?: never };
    requestBody?: {
      content: {
        "multipart/form-data": components["schemas"]["Body_api_scan_api_scan_post"];
      };
    };
    responses: {
      200: {
        headers: { [name: string]: unknown };
        content: {
          "application/json": unknown;
        };
      };
      422: {
        headers: { [name: string]: unknown };
        content: {
          "application/json": components["schemas"]["HTTPValidationError"];
        };
      };
    };
  };
}
