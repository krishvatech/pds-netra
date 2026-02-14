function _extractApiDetailFromMessage(message: string): string | null {
  // api.ts throws errors in this format: "API <status>: <text>"
  const idx = message.indexOf("API ");
  if (idx === -1) return null;
  const sep = message.indexOf(": ");
  if (sep === -1) return null;
  const raw = message.slice(sep + 2).trim();
  if (!raw) return null;

  try {
    const parsed = JSON.parse(raw);
    const detail = parsed?.detail;
    if (typeof detail === "string" && detail.trim()) return detail.trim();
    if (Array.isArray(detail) && detail.length) {
      // FastAPI validation errors are often an array of objects.
      const first = detail[0];
      if (first?.msg) return String(first.msg);
    }
  } catch {
    // non-JSON body; fall back to plain text
  }

  return raw;
}

export function friendlyErrorMessage(error: unknown, fallback: string, context?: string) {
  console.error(context ?? fallback, error);

  if (error instanceof Error) {
    const detail = _extractApiDetailFromMessage(error.message);
    if (detail) return detail;
  }
  if (typeof error === "string" && error.trim()) return error.trim();
  return fallback;
}
