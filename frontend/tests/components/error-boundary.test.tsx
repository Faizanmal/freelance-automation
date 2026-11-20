import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "@/components/error-boundary";

function Boom(): never {
  throw new Error("render boom");
}

describe("ErrorBoundary", () => {
  it("shows recovery actions instead of a blank shell", async () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    spy.mockRestore();
  });
});
