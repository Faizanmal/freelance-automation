export default function PrivacyPage() {
  return (
    <main className="max-w-3xl mx-auto py-8">
      <h1 className="text-3xl font-bold font-display mb-6 text-[var(--signal)]">Privacy Policy</h1>
      
      <div className="space-y-6 text-[var(--fog)] leading-relaxed">
        <section>
          <h2 className="text-xl font-semibold mb-3">1. Information We Collect</h2>
          <p>We collect information you provide directly to us, such as when you create an account, subscribe to our service, or communicate with us. This includes your email address, preferences, and payment information.</p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-3">2. How We Use Your Information</h2>
          <p>We use the information we collect to provide, maintain, and improve our services, to process transactions, and to send you job alerts and notifications as per your preferences.</p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-3">3. Data Sharing and Disclosure</h2>
          <p>We do not sell your personal data. We may share your information with third-party service providers (like payment processors and email delivery services) only to the extent necessary to operate our platform.</p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-3">4. Data Retention and Deletion</h2>
          <p>We retain your information as long as your account is active. You may request the permanent deletion of your account and all associated data at any time via your account settings.</p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-3">5. Cookies and Tracking</h2>
          <p>We use cookies and similar tracking technologies to track activity on our service and hold certain information to improve and analyze our service.</p>
        </section>

        <section>
          <h2 className="text-xl font-semibold mb-3">6. Your Rights (GDPR/CCPA)</h2>
          <p>Depending on your location, you may have the right to access, update, or delete your personal information. Please contact us to exercise these rights.</p>
        </section>
      </div>
    </main>
  );
}
