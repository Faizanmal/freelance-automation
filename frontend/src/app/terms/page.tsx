export default function TermsPage() {
  return (
    <main className="max-w-3xl mx-auto py-8">
      <h1 className="text-3xl font-bold font-display mb-6 text-[var(--signal)]">Terms and Conditions</h1>
      
      <div className="space-y-6 text-[var(--fog)] leading-relaxed">
        <section>
          <h2 className="text-xl font-semibold mb-3">1. Acceptance of Terms</h2>
          <p>By accessing or using Signal Desk, you agree to be bound by these Terms and Conditions. If you do not agree, you must not use our service.</p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-3">2. Description of Service</h2>
          <p>Signal Desk provides an intelligence platform that aggregates freelance and remote jobs and delivers matches based on user preferences. We do not guarantee the availability, quality, or success of any job listed on our platform.</p>
        </section>
        
        <section>
          <h2 className="text-xl font-semibold mb-3">3. User Accounts</h2>
          <p>You are responsible for safeguarding your password. You agree to provide accurate and complete information when registering an account.</p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-3">4. Usage Limits and API Abuse</h2>
          <p>Users must comply with all rate limits and usage restrictions. Automated scraping of our platform, unauthorized API access, and DDoS attempts are strictly prohibited and will result in immediate account suspension.</p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-3">5. Subscriptions and Payments</h2>
          <p>Paid subscriptions are billed in advance on a recurring basis. You may cancel your subscription at any time. Refunds are provided solely at our discretion and as required by law.</p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-3">6. Modifications to Service</h2>
          <p>We reserve the right to modify or discontinue, temporarily or permanently, the Service with or without notice.</p>
        </section>
        
        <section>
          <h2 className="text-xl font-semibold mb-3">7. Contact Information</h2>
          <p>If you have any questions about these Terms, please contact us via our Support channel.</p>
        </section>
      </div>
    </main>
  );
}
