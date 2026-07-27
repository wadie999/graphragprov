const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "";

export function apiUrl(path: string): string {
  return `${apiBaseUrl}${path}`;
}

export async function requestJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(apiUrl(path), init);

  if (!response.ok) {
    const body = await response.text();
    throw new Error(
      `HTTP ${response.status} ${response.statusText}${body ? `: ${body}` : ""}`,
    );
  }

  return (await response.json()) as T;
}
