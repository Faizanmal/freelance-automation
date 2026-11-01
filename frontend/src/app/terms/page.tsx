export default function TermsPage() {
  return (
    <main className="mx-auto max-w-3xl py-8">
      <h1 className="mb-6 font-display text-3xl font-bold text-[var(--signal)]">
        Terms and Conditions
      </h1>

      <div className="space-y-6 leading-relaxed text-[var(--fog)]">
        <p className="text-sm text-[var(--mute)]">
          Last updated: October 31, 2026. Operator: Signal Desk (contact{" "}
          <a className="text-[var(--signal)]" href="mailto:support@signaldesk.com">
            support@signaldesk.com
          </a>
          ). Replace this operator line with your legal entity name when incorporated.
        </p>

        <section>
          <h2 className="mb-3 text-xl font-semibold">1. Acceptance of Terms</h2>
          <p>
            By accessing or using Signal Desk, you agree to be bound by these Terms. If you do not
            agree, do not use the service.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold">2. Description of Service</h2>
          <p>
            Signal Desk is a freelance discovery desk. You set Hunt Rules; background hunters
            collect public listings and company/ATS openings; we rank them as Leads and may email
            a digest. Primary action is <strong>Open original</strong> on the source page. We show
            excerpts with attribution and links — we do not fully republish third-party boards, invent
            jobs, or auto-apply on your behalf as the default product.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold">3. Third-party listings</h2>
          <p>
            Listings originate from third-party sites and APIs. Accuracy, availability, legality, and
            hiring outcomes are outside our control. Always verify terms and authenticity on the
            original page before pitching or contracting.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold">4. User accounts</h2>
          <p>
            You are responsible for safeguarding credentials and for accurate registration details.
            Email verification may be required before hunters or digests run for your account.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold">5. Plans, usage limits, and fair use</h2>
          <p>
            Free and Pro plans include different hunt density, digest caps, and alert channels as
            described on the Pricing page. Manual hunt quotas and source allowlists are enforced in
            product. Automated abuse of our API, scraping our service, or circumventing plan limits
            may result in suspension.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold">6. Subscriptions and payments</h2>
          <p>
            Paid subscriptions (Pro) are billed in advance on a recurring basis via Stripe. You may
            cancel anytime through the billing portal; access continues through the paid period
            unless otherwise stated by Stripe. Refunds are provided as required by law or at our
            discretion. Failed or past-due payments may revert the account to Free limits.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold">7. Account deletion</h2>
          <p>
            You may delete your account from Account settings (API:{" "}
            <code className="text-[var(--paper)]">DELETE /users/me</code>
            ). Deletion removes your profile, preferences, and lead actions subject to legal
            retention needs (e.g. billing records).
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold">8. Modifications</h2>
          <p>
            We may modify or discontinue features with or without notice. Continued use after
            material Terms changes constitutes acceptance of the updated Terms.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold">9. Disclaimer and liability</h2>
          <p>
            The service is provided “as is.” We do not guarantee matches, income, or uninterrupted
            uptime. To the fullest extent permitted by law, Signal Desk is not liable for indirect or
            consequential damages arising from use of third-party job listings or the service.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold">10. Contact</h2>
          <p>
            Questions:{" "}
            <a className="text-[var(--signal)]" href="mailto:support@signaldesk.com">
              support@signaldesk.com
            </a>
            .
          </p>
        </section>
      </div>
    </main>
  );
}
