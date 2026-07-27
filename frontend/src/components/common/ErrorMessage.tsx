interface ErrorMessageProps {
  message: string | null;
  onRetry?: () => void;
}

export function ErrorMessage({
  message,
  onRetry,
}: ErrorMessageProps) {
  if (!message) {
    return null;
  }

  return (
    <div className="error-message" role="alert">
      <strong>Error</strong>
      <p>{message}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}
