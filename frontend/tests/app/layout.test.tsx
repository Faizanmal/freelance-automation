import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import RootLayout from '@/app/layout'

test('renders layout with navigation', () => {
  render(
    <RootLayout>
      <div data-testid="child">Test Child</div>
    </RootLayout>
  )

  // Verify navigation links
  const links = ['Desk', 'Pricing', 'Jobs', 'Findings', 'Matches', 'Sources', 'Prefs', 'Alerts', 'Account']
  for (const link of links) {
    expect(screen.getByText(link)).toBeInTheDocument()
  }

  // Verify child renders
  expect(screen.getByTestId('child')).toBeInTheDocument()
})
