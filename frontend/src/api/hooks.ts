import { useQuery } from '@tanstack/react-query'
import { apiGet } from './client'
import type {
  PaginatedResponse,
  ProductGroup,
  ProductGroupDetail,
  Category,
  Vendor,
  Stats,
  SearchResponse,
  AutocompleteItem,
  BrowseFilters,
} from './types'

// ─── Groups (browse) ───────────────────────────────────────────────────────

export function useGroups(filters: BrowseFilters = {}) {
  const { kategorija, min_cijena, max_cijena, volumen, ducani, sortiraj, page = 1, limit = 24 } = filters

  // Build flat params; repeat kategorija as multiple values manually
  const params: Record<string, string | number | undefined> = {
    page,
    limit,
    ...(min_cijena !== undefined && { min_cijena }),
    ...(max_cijena !== undefined && { max_cijena }),
    ...(volumen !== undefined && { volumen }),
    ...(ducani !== undefined && { ducani }),
    ...(sortiraj && { sortiraj }),
  }

  // Note: multi-value kategorija is handled inside the fetch via URLSearchParams.append
  const kategorijaList = kategorija ?? []

  return useQuery<PaginatedResponse<ProductGroup>>({
    queryKey: ['groups', filters],
    queryFn: async () => {
      const url = new URL('/api/groups/', window.location.origin)
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined) url.searchParams.append(k, String(v))
      }
      for (const k of kategorijaList) {
        url.searchParams.append('kategorija', k)
      }
      const res = await fetch(url.toString(), { headers: { Accept: 'application/json' } })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    },
  })
}

// ─── Group detail (product page) ──────────────────────────────────────────

export function useGroupDetail(groupId: string) {
  return useQuery<{ success: boolean; data: ProductGroupDetail }>({
    queryKey: ['group', groupId],
    queryFn: () => apiGet(`/groups/${encodeURIComponent(groupId)}/`),
    enabled: Boolean(groupId),
  })
}

// ─── Search ────────────────────────────────────────────────────────────────

export function useSearch(
  query: string,
  filters: {
    kategorija?: string[]
    min_cijena?: number
    max_cijena?: number
    volumen?: number
    ducani?: number
    sortiraj?: string
    page?: number
    limit?: number
  } = {},
) {
  const {
    kategorija,
    min_cijena,
    max_cijena,
    volumen,
    ducani,
    sortiraj,
    page = 1,
    limit = 24,
  } = filters

  return useQuery<SearchResponse>({
    queryKey: ['search', query, filters],
    queryFn: async () => {
      const url = new URL('/api/search/', window.location.origin)
      url.searchParams.set('q', query)
      url.searchParams.set('page', String(page))
      url.searchParams.set('limit', String(limit))
      kategorija?.forEach((k) => url.searchParams.append('kategorija', k))
      if (min_cijena !== undefined) url.searchParams.set('min_cijena', String(min_cijena))
      if (max_cijena !== undefined) url.searchParams.set('max_cijena', String(max_cijena))
      if (volumen    !== undefined) url.searchParams.set('volumen',    String(volumen))
      if (ducani     !== undefined) url.searchParams.set('ducani',     String(ducani))
      if (sortiraj) url.searchParams.set('sortiraj', sortiraj)
      const res = await fetch(url.toString(), { headers: { Accept: 'application/json' } })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      return res.json()
    },
    enabled: query.length >= 2,
  })
}

export function useAutocomplete(query: string) {
  return useQuery<{ success: boolean; data: AutocompleteItem[] }>({
    queryKey: ['autocomplete', query],
    queryFn: () => apiGet('/search/autocomplete/', { q: query, limit: 4 }),
    enabled: query.length >= 2,
    staleTime: 30 * 1000, // 30 s — autocomplete can be slightly stale
  })
}

// ─── Categories ────────────────────────────────────────────────────────────

export function useCategories() {
  return useQuery<{ success: boolean; data: Category[] }>({
    queryKey: ['categories'],
    queryFn: () => apiGet('/categories/'),
    staleTime: 10 * 60 * 1000, // 10 min — categories rarely change
  })
}

// ─── Vendors ───────────────────────────────────────────────────────────────

export function useVendors() {
  return useQuery<{ success: boolean; data: Vendor[] }>({
    queryKey: ['vendors'],
    queryFn: () => apiGet('/vendors/'),
    staleTime: 10 * 60 * 1000,
  })
}

// ─── Stats ─────────────────────────────────────────────────────────────────

export function useStats() {
  return useQuery<{ success: boolean; data: Stats }>({
    queryKey: ['stats'],
    queryFn: () => apiGet('/stats/'),
    staleTime: 10 * 60 * 1000,
  })
}
