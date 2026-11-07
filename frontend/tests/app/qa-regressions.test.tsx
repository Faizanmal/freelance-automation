import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { SecuritySettings } from "@/components/security-settings";
import * as api from "@/lib/api";

vi.mock("@/lib/api", () => ({
  setup2fa: vi.fn(),
  enable2fa: vi.fn(),
  disable2fa: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

test("SecuritySettings 2FA setup and enable flow works on a test account", async () => {
  vi.mocked(api.setup2fa).mockResolvedValue({
    secret: "JBSWY3DPEHPK3PXP",
    provisioning_uri:
      "otpauth://totp/Freelance%20Intelligence:qa@example.com?secret=JBSWY3DPEHPK3PXP",
  });
  vi.mocked(api.enable2fa).mockResolvedValue({ detail: "2FA successfully enabled" });

  const onUpdate = vi.fn();
  render(
    <SecuritySettings
      user={{ id: "qa-1", email: "qa@example.com", is_totp_enabled: false }}
      onUpdate={onUpdate}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: /Set up 2FA/i }));

  await waitFor(() => {
    expect(screen.getByPlaceholderText("123456")).toBeTruthy();
  });

  fireEvent.change(screen.getByPlaceholderText("123456"), { target: { value: "654321" } });
  fireEvent.click(screen.getByRole("button", { name: /Verify & Enable/i }));

  await waitFor(() => {
    expect(api.enable2fa).toHaveBeenCalledWith("654321");
    expect(onUpdate).toHaveBeenCalled();
  });
});
