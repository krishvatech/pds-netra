export function friendlyErrorMessage(error: unknown, fallback: string, context?: string) {
  console.error(context ?? fallback, error);
  return fallback;
}
