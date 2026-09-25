import { render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi, beforeEach } from 'vitest'
import HomePage from '@/app/page'
import * as api from '@/lib/api'

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}))

// Mock API
vi.mock('@/lib/api', () => ({
  getApiBase: vi.fn(() => 'http://localhost:8000'),
  getToken: vi.fn(() => 'fake-token'),
  healthLive: vi.fn(),
  listJobs: vi.fn(),
  scrapeJobs: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

test('renders homepage and fetches jobs', async () => {
  // Setup API mocks
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

  // Verify main heading
  expect(screen.getByText('Signal Desk')).toBeInTheDocument()

  // Verify API call is made and jobs are rendered
  await waitFor(() => {
    expect(screen.getByText('Software Engineer')).toBeInTheDocument()
  })
  expect(screen.getByText('Tech Corp · Remote')).toBeInTheDocument()
  expect(screen.getByText('1 jobs stored')).toBeInTheDocument()
})
