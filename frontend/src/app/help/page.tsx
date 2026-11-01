"use client";

import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import Link from "next/link";

const STEPS = [
  {
    title: "Create an account",
    body: "Sign up and verify your email so digests and security alerts can reach you.",
    href: "/auth",
    cta: "Sign up",
  },
  {
    title: "Set Hunt Rules",
    body: "Add keywords, excludes, budget, location, and freelance focus. This is what ranks your leads.",
    href: "/preferences?tab=matching",
    cta: "Open Hunt Rules",
  },
  {
    title: "Fill the pool",
    body: "Background hunters refresh on the hunt clock. On the Desk you can also refresh inventory once you’re signed in.",
    href: "/",
    cta: "Go to Desk",
  },
  {
    title: "Review Leads",
    body: "Open ranked fits, read why/risks, then pitch on the original listing. Save or skip to train your desk.",
    href: "/leads",
    cta: "Open Leads",
  },
  {
    title: "Schedule your digest",
    body: "Pick days, local time, and a lead cap in Hunt Rules. Digests follow your show clock — not scrape time.",
    href: "/preferences?tab=alerts",
    cta: "Digest settings",
  },
];

export default function HelpCenterPage() {
  const faqs = [
    {
      q: "How do hunting and digests work?",
      a: "Hunters fill a shared opportunity pool on a system schedule (hunt clock). Your email digest goes out on the show schedule you set in Hunt Rules — days, local time, and a max leads cap. Live Leads always reflect your current rules.",
    },
    {
      q: "Can I use negative keywords?",
      a: "Yes. In Hunt Rules, set exclude keywords. Listings that match those terms are filtered out of your ranked leads.",
    },
    {
      q: "Do you auto-apply or invent jobs?",
      a: "No. Every lead includes attribution and an Open original link. You pitch on the source site. Signal Desk never invents jobs or submits proposals for you.",
    },
    {
      q: "How do I upgrade to Pro?",
      a: "Open Pricing when Pro checkout is live, or start free and upgrade later. Pro raises hunt density and digest limits — it is not a marketplace bid product.",
    },
    {
      q: "Can I cancel my subscription?",
      a: "Yes. Manage or cancel from Account via the Stripe Customer Portal once you have an active subscription. Pro access lasts until the end of the billing cycle.",
    },
  ];

  return (
    <motion.main
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-1 flex-col gap-8 max-w-4xl mx-auto w-full pt-12"
    >
      <section className="text-center mb-8">
        <motion.h1
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-4xl md:text-5xl font-medium"
          style={{ fontFamily: "var(--font-display), Georgia, serif" }}
        >
          Help Center
        </motion.h1>
        <p className="mt-4 text-[var(--fog)] text-lg">
          Everything you need to know to get the most out of Signal Desk.
        </p>
      </section>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
        <Link href="#getting-started" className="block">
          <Card className="h-full p-6 text-center hover:bg-white/[0.02] transition">
            <h2 className="text-xl font-semibold text-[var(--paper)] mb-2">Getting Started</h2>
            <p className="text-sm text-[var(--mute)]">Five steps from signup to your first leads</p>
          </Card>
        </Link>
        <Link href="/status" className="block">
          <Card className="h-full p-6 text-center hover:bg-white/[0.02] transition">
            <h2 className="text-xl font-semibold text-[var(--paper)] mb-2">System Status</h2>
            <p className="text-sm text-[var(--mute)]">Check whether hunters and the desk are online</p>
          </Card>
        </Link>
        <a href="mailto:support@signaldesk.com" className="block">
          <Card className="h-full p-6 text-center hover:bg-white/[0.02] transition">
            <h2 className="text-xl font-semibold text-[var(--paper)] mb-2">Contact Support</h2>
            <p className="text-sm text-[var(--mute)]">Email support@signaldesk.com for human help</p>
          </Card>
        </a>
      </div>

      <section id="getting-started" className="scroll-mt-24">
        <h2 className="text-2xl font-semibold text-[var(--paper)] mb-6 border-b border-white/10 pb-4">
          Getting Started
        </h2>
        <ol className="grid gap-6">
          {STEPS.map((step, index) => (
            <li key={step.title} className="border-t border-white/10 pt-5">
              <p className="text-sm tracking-[0.2em] text-[var(--signal)] uppercase">
                Step {index + 1}
              </p>
              <h3 className="mt-2 text-xl text-[var(--paper)]">{step.title}</h3>
              <p className="mt-2 text-[var(--fog)] leading-relaxed">{step.body}</p>
              <Link
                href={step.href}
                className="mt-3 inline-block text-sm text-[var(--signal)] hover:underline"
              >
                {step.cta}
              </Link>
            </li>
          ))}
        </ol>
      </section>

      <h2 className="text-2xl font-semibold text-[var(--paper)] mb-6 border-b border-white/10 pb-4">
        Frequently Asked Questions
      </h2>

      <div className="grid gap-6">
        {faqs.map((faq) => (
          <motion.div
            key={faq.q}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <h3 className="text-lg font-medium text-[var(--signal)] mb-2">{faq.q}</h3>
            <p className="text-[var(--fog)] leading-relaxed">{faq.a}</p>
          </motion.div>
        ))}
      </div>
    </motion.main>
  );
}
