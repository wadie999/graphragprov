interface CodeBlockProps {
  value?: string;
  emptyMessage?: string;
}

export function CodeBlock({
  value,
  emptyMessage = "Not available.",
}: CodeBlockProps) {
  return (
    <pre className="code-block">
      <code>{value?.trim() || emptyMessage}</code>
    </pre>
  );
}
