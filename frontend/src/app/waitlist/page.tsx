"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getMyMarketplaceWaitlist, joinMarketplaceWaitlist, leaveMarketplaceWaitlist, me, type MarketplaceWaitlistEntry } from "@/lib/api";
import { useRouter } from "next/navigation";

export default function MarketplaceWaitlistPage() {
  const router = useRouter();
  const [entries, setEntries] = useState<MarketplaceWaitlistEntry[]>([]);
  const [persona, setPersona] = useState<"client" | "freelancer">("client");
  const [waitlistConsent, setWaitlistConsent] = useState(false);
  const [conciergeConsent, setConciergeConsent] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = async () => setEntries((await getMyMarketplaceWaitlist()).items);
  useEffect(() => {
    me().then(refresh).catch(() => router.push("/auth"));
  }, [router]);

  const join = async () => {
    if (!waitlistConsent) return;
    setBusy(true); setMessage("");
    try {
      await joinMarketplaceWaitlist(persona, true, conciergeConsent);
      setWaitlistConsent(false); setConciergeConsent(false);
      setMessage("Your opt-in was saved. This is a waitlist, not a promise of a project, shortlist, or launch date.");
      await refresh();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to save your opt-in."); }
    finally { setBusy(false); }
  };

  const leave = async (id: string) => {
    setBusy(true); setMessage("");
    try { await leaveMarketplaceWaitlist(id); await refresh(); setMessage("You opted out. Concierge contact consent was withdrawn too."); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Unable to opt out."); }
    finally { setBusy(false); }
  };

  return <main className="mx-auto w-full max-w-3xl px-5 py-16">
    <h1 className="text-4xl" style={{ fontFamily: "var(--font-display), Georgia, serif" }}>Marketplace waitlist</h1>
    <p className="mt-3 text-sm text-[var(--fog)]">We are validating an AI, software, and automation contracting pilot. Joining does not claim that clients or projects are available.</p>
    <Card className="mt-8 space-y-5 border-white/10 bg-white/[0.02] p-5">
      <label className="block text-sm">I am joining as
        <select value={persona} onChange={(event) => setPersona(event.target.value as "client" | "freelancer")} className="mt-2 block w-full rounded-md border border-white/10 bg-black/40 p-2 text-[var(--paper)]">
          <option value="client">A hiring client</option><option value="freelancer">A freelancer</option>
        </select>
      </label>
      <label className="flex items-start gap-3 text-sm text-[var(--fog)]">
        <input type="checkbox" checked={waitlistConsent} onChange={(event) => setWaitlistConsent(event.target.checked)} />
        <span>I consent to storing this waitlist preference so I can be considered for future pilot updates. I can opt out below.</span>
      </label>
      <label className="flex items-start gap-3 text-sm text-[var(--fog)]">
        <input type="checkbox" checked={conciergeConsent} onChange={(event) => setConciergeConsent(event.target.checked)} />
        <span>Separately, I consent to one-to-one concierge follow-up about pilot research. This does not authorize bulk outreach.</span>
      </label>
      <Button disabled={busy || !waitlistConsent} onClick={join}>{busy ? "Saving…" : "Join waitlist"}</Button>
      {message && <p role="status" className="text-sm text-[var(--fog)]">{message}</p>}
    </Card>
    <section className="mt-8 space-y-3">
      <h2 className="text-xl">Your entries</h2>
      {entries.length === 0 ? <p className="text-sm text-[var(--mute)]">No waitlist entries.</p> : entries.map((entry) => <Card key={entry.id} className="flex items-center justify-between gap-4 p-4">
        <span className="text-sm">{entry.persona} · {entry.status} · concierge follow-up {entry.concierge_consent ? "allowed" : "not allowed"}</span>
        {entry.status !== "opted_out" && <Button variant="outline" disabled={busy} onClick={() => leave(entry.id)}>Opt out</Button>}
      </Card>)}
    </section>
  </main>;
}
