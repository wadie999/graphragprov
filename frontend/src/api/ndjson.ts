import { apiUrl } from "./client";

export async function* streamNdjson<T>(
  path: string,
  init: RequestInit,
): AsyncGenerator<T> {
  const response = await fetch(apiUrl(path), init);

  if (!response.ok) {
    const body = await response.text();
    throw new Error(
      `HTTP ${response.status} ${response.statusText}${body ? `: ${body}` : ""}`,
    );
  }

  if (response.body === null) {
    throw new Error("The response does not contain a readable stream.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      while (true) {
        const newlineIndex = buffer.indexOf("\n");

        if (newlineIndex < 0) {
          break;
        }

        const line = buffer.slice(0, newlineIndex).trim();
        buffer = buffer.slice(newlineIndex + 1);

        if (line) {
          yield JSON.parse(line) as T;
        }
      }
    }

    buffer += decoder.decode();

    const finalLine = buffer.trim();

    if (finalLine) {
      yield JSON.parse(finalLine) as T;
    }
  } finally {
    reader.releaseLock();
  }
}
