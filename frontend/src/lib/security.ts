/**
 * Security utilities for URL validation and HTML sanitization.
 */

const ALLOWED_PROTOCOLS = new Set(["http:", "https:"]);

/**
 * Validates and sanitizes external URLs to prevent javascript:, data:, and other malicious schemes.
 * Returns the sanitized URL if valid, or an empty string if malicious/invalid.
 */
export function sanitizeExternalUrl(url?: string | null): string {
  if (!url) return "";
  const trimmed = url.trim();
  if (!trimmed) return "";

  // Reject immediate control character / javascript protocol tricks
  if (/^javascript:/i.test(trimmed) || /^data:/i.test(trimmed) || /^vbscript:/i.test(trimmed)) {
    return "";
  }

  try {
    const parsed = new URL(trimmed);
    if (!ALLOWED_PROTOCOLS.has(parsed.protocol)) {
      return "";
    }
    return parsed.href;
  } catch {
    // Relative URLs or malformed URLs
    // External links must be absolute HTTP/HTTPS URLs
    return "";
  }
}

/**
 * Safely opens an external URL in a new window/tab with noopener and noreferrer.
 * Prevents reverse tabnabbing and blocks dangerous URL schemes.
 */
export function openSafeExternalUrl(url?: string | null): void {
  const safeUrl = sanitizeExternalUrl(url);
  if (!safeUrl) {
    return;
  }
  if (typeof window !== "undefined") {
    window.open(safeUrl, "_blank", "noopener,noreferrer");
  }
}

/**
 * Robustly strips HTML tags, script/style blocks, and normalizes whitespace from external text.
 * Avoids raw HTML injection without needing heavy dependencies.
 */
export function stripHtml(value?: string | null): string {
  if (!value) return "";

  let clean = value;

  // 1. Remove script, style, and iframe tags along with their inner contents
  clean = clean.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, " ");
  clean = clean.replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, " ");
  clean = clean.replace(/<iframe\b[^>]*>[\s\S]*?<\/iframe>/gi, " ");

  // 2. Iteratively strip remaining HTML tags
  let previous = "";
  while (clean !== previous) {
    previous = clean;
    clean = clean.replace(/<[^>]*>/g, " ");
  }

  // 3. Unescape standard HTML entities
  clean = clean
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ");

  // 4. Collapse whitespace
  return clean.replace(/\s+/g, " ").trim();
}
