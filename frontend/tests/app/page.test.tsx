import { render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi, beforeEach } from 'vitest'
import HomePage from '@/app/page'
import * as api from '@/lib/api'

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}))

vi.mock('@/lib/api', () => ({
  getApiBase: vi.fn(() => 'http://localhost:8000'),
  getToken: vi.fn(() => 'fake-token'),
  subscribeAuth: (onStoreChange: () => void) => {
    void onStoreChange
    return () => {}
  },
  getAuthSnapshot: vi.fn(() => true),
  getAuthServerSnapshot: vi.fn(() => false),
  healthLive: vi.fn(),
  listJobs: vi.fn(),
  scrapeJobs: vi.fn(),
}))

vi.mock('@/components/activation-checklist', () => ({
  ActivationChecklist: () => <div data-testid="activation-checklist" />,
}))

beforeEach(() => {
  vi.clearAllMocks()
})

test('renders authenticated desk and fetches jobs', async () => {
  vi.mocked(api.getToken).mockReturnValue('fake-token')
  vi.mocked(api.getAuthSnapshot).mockReturnValue(true)
  vi.mocked(api.healthLive).mockResolvedValue({ status: 'ok' })
  vi.mocked(api.listJobs).mockResolvedValue({
    items: [
      {
        id: 1,
        title: 'Software Engineer',
        url: 'https://example.com/1',
        source_name: 'remoteok',
        source_id: 'remoteok-1',
        company: 'Tech Corp',
        location: 'Remote',
        description: '...',
        budget_min: null,
        budget_max: null,
        posted_at: '2026-06-20T10:00:00Z',
        created_at: '2026-06-20T10:00:00Z',
        analysis_summary: null,
      }
    ],
    total: 1,
  })

  render(<HomePage />)

  expect(screen.getAllByText('Signal Desk').length).toBeGreaterThanOrEqual(1)

  await waitFor(() => {
    expect(screen.getByText('Software Engineer')).toBeInTheDocument()
  })
  expect(screen.getByText('Tech Corp · Remote')).toBeInTheDocument()
  expect(screen.getByText('1 opportunities stored')).toBeInTheDocument()
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /refresh inventory/i })).toBeInTheDocument()
  })
  expect(screen.getByRole('link', { name: /hunt rules/i })).toBeInTheDocument()
  expect(screen.getByTestId('activation-checklist')).toBeInTheDocument()
  expect(screen.getByText(/1 opportunities stored/i)).toBeInTheDocument()
})

test('renders marketing hero without scrape when logged out', async () => {
  vi.mocked(api.getToken).mockReturnValue(null)
  vi.mocked(api.getAuthSnapshot).mockReturnValue(false)
  vi.mocked(api.listJobs).mockResolvedValue({ items: [], total: 0 })

  render(<HomePage />)

  expect(screen.getByRole('link', { name: /see pricing/i })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /start free/i })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /refresh inventory/i })).not.toBeInTheDocument()
  expect(screen.getByText(/outside crowded marketplaces/i)).toBeInTheDocument()
})
