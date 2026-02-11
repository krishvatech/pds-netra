import { Button } from './button';

export function ErrorBanner({
  message,
  onRetry
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="alert-toast flex flex-wrap items-center justify-between gap-3 px-4 py-3 mb-4">
      <div className="text-xs text-red-400">{message}</div>
      {onRetry && (
        <Button variant="outline" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}
