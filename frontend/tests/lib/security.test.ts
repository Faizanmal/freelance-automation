import { describe, expect, it, vi } from "vitest";
import { openSafeExternalUrl, sanitizeExternalUrl, stripHtml } from "@/lib/security";

describe("Security utilities", () => {
  describe("sanitizeExternalUrl", () => {
    it("allows valid http and https URLs", () => {
      expect(sanitizeExternalUrl("https://example.com/jobs/123")).toBe("https://example.com/jobs/123");
      expect(sanitizeExternalUrl("http://example.org/test?id=456")).toBe("http://example.org/test?id=456");
    });

    it("blocks javascript: URLs", () => {
      expect(sanitizeExternalUrl("javascript:alert(1)")).toBe("");
      expect(sanitizeExternalUrl("JAVASCRIPT:alert('xss')")).toBe("");
      expect(sanitizeExternalUrl("  javascript:void(0) ")).toBe("");
    });

    it("blocks data: and vbscript: URLs", () => {
      expect(sanitizeExternalUrl("data:text/html,<script>alert(1)</script>")).toBe("");
      expect(sanitizeExternalUrl("vbscript:msgbox(1)")).toBe("");
    });

    it("blocks relative URLs or invalid protocols", () => {
      expect(sanitizeExternalUrl("/relative/path")).toBe("");
      expect(sanitizeExternalUrl("file:///etc/passwd")).toBe("");
      expect(sanitizeExternalUrl("")).toBe("");
      expect(sanitizeExternalUrl(null)).toBe("");
      expect(sanitizeExternalUrl(undefined)).toBe("");
    });
  });

  describe("openSafeExternalUrl", () => {
    it("opens safe URLs with noopener and noreferrer", () => {
      const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
      openSafeExternalUrl("https://jobs.example.com/apply");
      expect(openSpy).toHaveBeenCalledWith("https://jobs.example.com/apply", "_blank", "noopener,noreferrer");
      openSpy.mockRestore();
    });

    it("does not call window.open for malicious URLs", () => {
      const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);
      openSafeExternalUrl("javascript:alert(1)");
      expect(openSpy).not.toHaveBeenCalled();
      openSpy.mockRestore();
    });
  });

  describe("stripHtml", () => {
    it("strips simple and nested HTML tags", () => {
      expect(stripHtml("<p>Hello <b>World</b></p>")).toBe("Hello World");
      expect(stripHtml("<div><h1>Title</h1><p>Description here</p></div>")).toBe("Title Description here");
    });

    it("strips script and iframe tags and their contents completely", () => {
      expect(stripHtml("<script>alert(1)</script>")).toBe("");
      expect(stripHtml("Job details <script type='text/javascript'>malicious();</script> - Apply now")).toBe("Job details - Apply now");
      expect(stripHtml("<iframe src='https://evil.com'>hidden</iframe>Safe text")).toBe("Safe text");
    });

    it("unescapes basic HTML entities cleanly", () => {
      expect(stripHtml("Design &amp; Development &gt; Code")).toBe("Design & Development > Code");
      expect(stripHtml("It&#39;s &quot;secure&quot;")).toBe("It's \"secure\"");
    });

    it("handles empty or null values", () => {
      expect(stripHtml("")).toBe("");
      expect(stripHtml(null)).toBe("");
      expect(stripHtml(undefined)).toBe("");
    });
  });
});
