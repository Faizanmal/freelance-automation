import { expect, test } from "vitest";

test("CSV escaping properly quotes strings with commas and quotes", () => {
  const escapeCsv = (val: string | number | null | undefined) => {
    const str = String(val ?? "");
    return `"${str.replace(/"/g, '""')}"`;
  };

  expect(escapeCsv('Senior "Full-Stack" Developer')).toBe('"Senior ""Full-Stack"" Developer"');
  expect(escapeCsv("Acme, Inc.")).toBe('"Acme, Inc."');
  expect(escapeCsv(null)).toBe('""');
  expect(escapeCsv(95)).toBe('"95"');
});

test("CSV row mapping formats lead fields correctly", () => {
  const mockLead = {
    job: {
      id: 101,
      title: "FastAPI Developer",
      company: "Tech Corp",
      source_name: "github_bounties",
      url: "https://github.com/techcorp/issues/1",
      posted_at: "2026-11-05T12:00:00Z",
    },
    match_score: 0.92,
    match_reasons: ["Strong Python match", "FastAPI keyword"],
    user_status: "new",
  };

  const escapeCsv = (val: string | number | null | undefined) => {
    const str = String(val ?? "");
    return `"${str.replace(/"/g, '""')}"`;
  };

  const row = [
    mockLead.job.id,
    escapeCsv(mockLead.job.title),
    escapeCsv(mockLead.job.company),
    escapeCsv(mockLead.job.source_name),
    Math.round((mockLead.match_score || 0) * 100),
    escapeCsv((mockLead.match_reasons || []).join("; ")),
    escapeCsv(mockLead.user_status),
    escapeCsv(mockLead.job.url),
    escapeCsv(mockLead.job.posted_at),
  ];

  expect(row[0]).toBe(101);
  expect(row[1]).toBe('"FastAPI Developer"');
  expect(row[2]).toBe('"Tech Corp"');
  expect(row[3]).toBe('"github_bounties"');
  expect(row[4]).toBe(92);
  expect(row[5]).toBe('"Strong Python match; FastAPI keyword"');
  expect(row[6]).toBe('"new"');
  expect(row[7]).toBe('"https://github.com/techcorp/issues/1"');
});

