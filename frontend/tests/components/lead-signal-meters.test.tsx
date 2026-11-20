import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LeadSignalMeters } from "@/components/lead-signal-meters";

describe("LeadSignalMeters", () => {
  it("exposes separate meters for fit, trust, and freshness", () => {
    render(<LeadSignalMeters fit={0.8} trust={0.5} freshness={0.2} />);
    expect(screen.getByRole("meter", { name: /fit 80 percent/i })).toBeInTheDocument();
    expect(screen.getByRole("meter", { name: /trust 50 percent/i })).toBeInTheDocument();
    expect(screen.getByRole("meter", { name: /fresh 20 percent/i })).toBeInTheDocument();
  });
});
