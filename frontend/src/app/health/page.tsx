import { redirect } from "next/navigation";

/** Alias for older /health links — status UI lives at /status. */
export default function HealthPage() {
  redirect("/status");
}
