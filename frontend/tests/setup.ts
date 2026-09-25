import '@testing-library/jest-dom/vitest'
import { vi } from 'vitest'

vi.mock('next/font/google', () => ({
  Fraunces: () => ({
    style: { fontFamily: 'mocked' },
    className: 'mocked',
    variable: '--font-display',
  }),
  Manrope: () => ({
    style: { fontFamily: 'mocked' },
    className: 'mocked',
    variable: '--font-body',
  }),
}))
