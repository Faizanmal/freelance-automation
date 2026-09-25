import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'

test('frontend test setup works', () => {
  render(<div>Test Setup Successful</div>)
  expect(screen.getByText('Test Setup Successful')).toBeInTheDocument()
})
