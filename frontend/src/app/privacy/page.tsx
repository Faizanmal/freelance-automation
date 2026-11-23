export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl py-8">
      <h1 className="mb-6 font-display text-3xl font-bold text-[var(--signal)]">Privacy Policy</h1>

      <div className="space-y-6 leading-relaxed text-[var(--fog)]">
        <p className="text-sm text-[var(--mute)]">
          Last updated: October 31, 2026. Contact{" "}
          <a className="text-[var(--signal)]" href="mailto:support@signaldesk.com">
            support@signaldesk.com
          </a>
          .
        </p>

        <section>
          <h2 className="mb-3 text-xl font-semibold">1. Information we collect</h2>
          <p>
            Account data (email, password hash, optional 2FA), Hunt Rules and alert destinations,
            lead Save/Skip actions, billing identifiers via Stripe (we do not store full card
            numbers), and technical logs (IP, user agent) needed to operate and secure the service.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold">2. How we use information</h2>
          <p>
            We use your data to authenticate you, match public listings to Hunt Rules, send digests
            and alerts you configure, process subscriptions, prevent abuse, and improve reliability.
            We do not sell personal data.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold">3. Job inventory and attribution</h2>
          <p>
            Shared job inventory is gathered from public sources and licensed APIs. We store
            excerpts, metadata, attribution, and original URLs so we can rank Leads for users. We do
            not claim ownership of third-party listing content.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold">4. Processors and sharing</h2>
          <p>
            Depending on the features enabled for your account, service providers may process data
            for hosting, databases, email delivery, public-source discovery, subscription billing,
            site analytics, and error monitoring. The active provider list, processing locations,
            and applicable transfer terms must be confirmed for the deployment before public
            enrollment.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold">5. Retention and deletion</h2>
          <p>
            We retain account and preference data while your account is active. You may delete your
            account anytime from Account settings; associated preferences and lead actions are
            removed. Billing records may be retained as required for tax and fraud prevention.
            Operational logs are rotated on a routine schedule.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold">6. Analytics and browser storage</h2>
          <p>
            Sign-in uses a Bearer token stored in your browser (local storage), not an HttpOnly
            session cookie. Optional site analytics load only after you accept the site analytics
            banner. Product outcome events (currently lead save, skip, and external apply click)
            require separate analytics consent in the account privacy center. These events do not
            include prompts, private messages, listing identifiers, or financial amounts. Revoking
            consent stops new product events; account deletion removes associated events. See the
            in-app controls. The precise retention period and active provider list must be confirmed
            before public enrollment.
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold">7. Your rights</h2>
          <p>
            Depending on your location (e.g. GDPR/CCPA), you may request access, correction, or
            deletion of personal data. Email{" "}
            <a className="text-[var(--signal)]" href="mailto:support@signaldesk.com">
              support@signaldesk.com
            </a>{" "}
            or use account deletion in the product.
          </p>
        </section>
      </div>
    </div>
  );
}
