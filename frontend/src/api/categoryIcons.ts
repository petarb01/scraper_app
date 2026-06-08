/**
 * Maps category slugs to display metadata (icon + gradient).
 * Shared by ProductCard, FilterSidebar, and Categories section.
 */
export interface CategoryMeta {
  icon: string
  gradient: string
}

export const CATEGORY_META: Record<string, CategoryMeta> = {
  whisky:  { icon: '🥃', gradient: 'linear-gradient(135deg, #78350f, #92400e)' },
  vodka:   { icon: '🍸', gradient: 'linear-gradient(135deg, #1e3a5f, #1e40af)' },
  gin:     { icon: '🌿', gradient: 'linear-gradient(135deg, #14532d, #166534)' },
  rum:     { icon: '🍹', gradient: 'linear-gradient(135deg, #7c2d12, #9a3412)' },
  tequila: { icon: '🌵', gradient: 'linear-gradient(135deg, #365314, #3f6212)' },
  konjak:  { icon: '🥂', gradient: 'linear-gradient(135deg, #451a03, #78350f)' },
  rakija:  { icon: '🍇', gradient: 'linear-gradient(135deg, #4a044e, #6b21a8)' },
  likeri:  { icon: '🍬', gradient: 'linear-gradient(135deg, #831843, #9d174d)' },
  vino:    { icon: '🍷', gradient: 'linear-gradient(135deg, #4c0519, #881337)' },
  pivo:    { icon: '🍺', gradient: 'linear-gradient(135deg, #713f12, #854d0e)' },
  kokteli: { icon: '🍸', gradient: 'linear-gradient(135deg, #0c4a6e, #075985)' },
}

const DEFAULT_META: CategoryMeta = {
  icon: '🥃',
  gradient: 'linear-gradient(135deg, #1a1e34, #212640)',
}

export function getCategoryMeta(slug: string | null | undefined): CategoryMeta {
  if (!slug) return DEFAULT_META
  return CATEGORY_META[slug] ?? DEFAULT_META
}

/** Helper to turn a URL path to detail page from a group_id string. */
export function groupDetailUrl(groupId: string): string {
  if (groupId.startsWith('g')) return `/proizvod/g/${groupId.slice(1)}`
  return `/proizvod/${groupId.slice(1)}`
}
