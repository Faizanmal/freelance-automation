import { render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import RootLayout from '@/app/layout'

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
  usePathname: () => '/',
}))

vi.mock('@/lib/api', () => ({
  getToken: vi.fn(() => null),
  subscribeAuth: () => () => {},
  getAuthSnapshot: vi.fn(() => false),
  getAuthServerSnapshot: vi.fn(() => false),
}))

vi.mock('@/components/theme-provider', () => ({
  ThemeProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

vi.mock('@/components/theme-toggle', () => ({
  ThemeToggle: () => <div data-testid="theme-toggle" />,
}))

vi.mock('@/components/cookie-consent', () => ({
  CookieConsent: () => <div data-testid="cookie-consent" />,
  Analytics: () => <div data-testid="analytics" />,
  ClientErrorReporter: () => <div data-testid="error-reporter" />,
}))

vi.mock('@/components/onboarding-wizard', () => ({
  OnboardingWizard: () => <div data-testid="onboarding-wizard" />,
}))

test('renders layout with primary navigation', () => {
  render(
    <RootLayout>
      <div data-testid="child">Test Child</div>
    </RootLayout>
  )

  const links = ['Desk', 'Pricing', 'Leads', 'Account']
  for (const link of links) {
    expect(screen.getByText(link)).toBeInTheDocument()
  }

  expect(screen.queryByText('Findings')).not.toBeInTheDocument()
  expect(screen.queryByText('Matches')).not.toBeInTheDocument()
  expect(screen.queryByText('Prefs')).not.toBeInTheDocument()
  expect(screen.queryByText('Sources')).not.toBeInTheDocument()

  expect(screen.getByTestId('child')).toBeInTheDocument()
  expect(screen.getByTestId('theme-toggle')).toBeInTheDocument()
  expect(screen.getByTestId('cookie-consent')).toBeInTheDocument()
}, 10000)

test('renders authenticated nav with Hunt Rules instead of Sources', async () => {
  const api = await import('@/lib/api')
  vi.mocked(api.getAuthSnapshot).mockReturnValue(true)
  vi.mocked(api.getToken).mockReturnValue('fake-token')

  render(
    <RootLayout>
      <div data-testid="child">Test Child</div>
    </RootLayout>
  )

  // Auth chrome waits until client mount to avoid hydration mismatch.
  expect(await screen.findByText('Hunt Rules')).toBeInTheDocument()
  expect(screen.getByText('Leads')).toBeInTheDocument()
  expect(screen.queryByText('Sources')).not.toBeInTheDocument()
  expect(screen.queryByText('Pricing')).not.toBeInTheDocument()
}, 10000)
