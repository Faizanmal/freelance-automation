export function getErrorMessage(error: unknown, fallback = "Request failed"): string {
  return error instanceof Error && error.message ? error.message : fallback;
}
