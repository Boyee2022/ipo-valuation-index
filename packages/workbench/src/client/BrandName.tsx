/**
 * Sidebar brand-name occupant: replaces the shell's baked-in brand text
 * with this instance's product name.
 */

import type { ReactNode } from 'react'

export function BrandName(): ReactNode {
  return (
    <span style={{ fontWeight: 600, fontSize: 14, letterSpacing: 0.1, color: 'inherit' }}>
      ValuationSystem
    </span>
  )
}
