interface JsonBlockProps {
  value: unknown;
  emptyMessage?: string;
}

export function JsonBlock({
  value,
  emptyMessage = "Not available.",
}: JsonBlockProps) {
  if (value === undefined || value === null) {
    return <pre className="code-block">{emptyMessage}</pre>;
  }

  return (
    <pre className="code-block">
      <code>{JSON.stringify(value, null, 2)}</code>
    </pre>
  );
}
