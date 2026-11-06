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

const SAFE_EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;

/**
 * Validates and normalizes an email address to prevent CRLF / header injection.
 */
export function sanitizeEmailAddress(email?: string | null): string {
  if (!email) return "";
  const trimmed = email.trim();
  if (!trimmed || trimmed.length > 254 || !SAFE_EMAIL_RE.test(trimmed)) {
    return "";
  }
  return trimmed;
}

/**
 * Builds a safe Gmail compose URL with optional recipient, subject, and body.
 */
export function buildGmailComposeUrl(params: {
  to?: string | null;
  subject?: string | null;
  body?: string | null;
}): string {
  const url = new URL("https://mail.google.com/mail/");
  url.searchParams.set("view", "cm");
  url.searchParams.set("fs", "1");
  const safeTo = sanitizeEmailAddress(params.to);
  if (safeTo) {
    url.searchParams.set("to", safeTo);
  }
  if (params.subject?.trim()) {
    url.searchParams.set("su", params.subject.trim().slice(0, 200));
  }
  if (params.body?.trim()) {
    url.searchParams.set("body", params.body.trim().slice(0, 6000));
  }
  return url.toString();
}

/**
 * Builds a safe mailto: URI with URI-encoded subject and body.
 */
export function buildSafeMailtoUrl(params: {
  to?: string | null;
  subject?: string | null;
  body?: string | null;
}): string {
  const safeTo = sanitizeEmailAddress(params.to);
  const queryParts: string[] = [];
  if (params.subject?.trim()) {
    queryParts.push(`subject=${encodeURIComponent(params.subject.trim().slice(0, 200))}`);
  }
  if (params.body?.trim()) {
    queryParts.push(`body=${encodeURIComponent(params.body.trim().slice(0, 6000))}`);
  }
  const query = queryParts.length > 0 ? `?${queryParts.join("&")}` : "";
  return `mailto:${safeTo}${query}`;
}
