import type { QueryRun } from "../api/runTypes";

function bindings(run?: QueryRun | null): Record<string, unknown>[] {
  const results = run?.result?.results;
  if (!results || typeof results !== "object") return [];
  const rows = (results as { bindings?: unknown }).bindings;
  return Array.isArray(rows) ? (rows as Record<string, unknown>[]) : [];
}

export function answerValues(run?: QueryRun | null): string[] {
  return bindings(run).map((row) => {
    const value = row.answer ?? Object.values(row)[0];
    if (!value || typeof value !== "object") return String(value ?? "");
    const lexical = (value as { value?: unknown }).value;
    return typeof lexical === "string" ? displayTerm(lexical) : JSON.stringify(value);
  });
}

export function displayTerm(value: string): string {
  const prefix = "urn:graphragprov:entity:";
  if (value.startsWith(prefix)) return decodeURIComponent(value.slice(prefix.length));
  return value;
}
