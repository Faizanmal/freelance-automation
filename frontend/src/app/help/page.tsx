"use client";

import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import Link from "next/link";

export default function HelpCenterPage() {
  const faqs = [
    {
      q: "How do hunting and digests work?",
      a: "Hunters fill a shared opportunity pool on a system schedule (hunt clock). Your email digest goes out on the show schedule you set in Hunt Rules — days, local time, and a max leads cap. Live Leads always reflect your current rules."
    },
    {
      q: "Can I use negative keywords?",
      a: "Yes. In Hunt Rules, set exclude keywords. Listings that match those terms are filtered out of your ranked leads."
    },
    {
      q: "Do you auto-apply or invent jobs?",
      a: "No. Every lead includes attribution and an Open original link. You pitch on the source site. Signal Desk never invents jobs or submits proposals for you."
    },
    {
      q: "How do I upgrade to Pro?",
      a: "Open Pricing and subscribe via Stripe. Pro raises hunt density and digest limits for the discovery desk — it is not a marketplace bid product."
    },
    {
      q: "Can I cancel my subscription?",
      a: "Yes. Manage or cancel from Account via the Stripe Customer Portal. If you cancel, Pro access lasts until the end of the billing cycle."
    }
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
        <Card className="p-6 text-center hover:bg-white/[0.02] transition cursor-pointer">
          <h2 className="text-xl font-semibold text-[var(--paper)] mb-2">Getting Started</h2>
          <p className="text-sm text-[var(--mute)]">Learn how to configure your first job alert</p>
        </Card>
        <Card className="p-6 text-center hover:bg-white/[0.02] transition cursor-pointer">
          <Link href="/status">
            <h2 className="text-xl font-semibold text-[var(--paper)] mb-2">System Status</h2>
            <p className="text-sm text-[var(--mute)]">Check if our scrapers are currently operational</p>
          </Link>
        </Card>
        <Card className="p-6 text-center hover:bg-white/[0.02] transition cursor-pointer">
          <a href="mailto:support@signaldesk.com">
            <h2 className="text-xl font-semibold text-[var(--paper)] mb-2">Contact Support</h2>
            <p className="text-sm text-[var(--mute)]">Email us directly for human help</p>
          </a>
        </Card>
      </div>

      <h2 className="text-2xl font-semibold text-[var(--paper)] mb-6 border-b border-white/10 pb-4">
        Frequently Asked Questions
      </h2>
      
      <div className="grid gap-6">
        {faqs.map((faq, i) => (
          <motion.div 
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
          >
            <h3 className="text-lg font-medium text-[var(--signal)] mb-2">{faq.q}</h3>
            <p className="text-[var(--fog)] leading-relaxed">{faq.a}</p>
          </motion.div>
        ))}
      </div>
    </motion.main>
  );
}
