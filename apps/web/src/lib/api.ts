export type {Version, Project, Binding, Feedback, Card, Demo, Metrics, Analytics, Review} from "../../../../packages/contracts/types";
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch("/api" + path, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Request could not be completed",
    );
  }
  return response.json();
}
export const post = <T>(path: string, body: unknown = {}) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export async function upload<T>(path: string, file: File) {
  const data = new FormData();
  data.append("file", file);
  return api<T>(path, { method: "POST", body: data });
}
export function message(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong";
}
