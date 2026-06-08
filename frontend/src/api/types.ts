// ─── Pagination ────────────────────────────────────────────────────────────

export interface Pagination {
  page: number
  limit: number
  total: number
  pages: number
}

export interface PaginatedResponse<T> {
  success: boolean
  data: T[]
  pagination: Pagination
}

// ─── Category ──────────────────────────────────────────────────────────────

export interface Category {
  id: number
  name: string
  display_name: string
  slug: string
  icon?: string
  product_count: number
}

// ─── Store / Vendor ────────────────────────────────────────────────────────

export interface Vendor {
  id: number
  name: string
  display_name: string
  website_url: string
  logo_url?: string
  is_active: boolean
  product_count: number
}

// ─── Product Group (browse / search card) ─────────────────────────────────

export interface ProductGroup {
  group_id: string         // "g{match_id}" or "p{product_id}"
  match_id: number | null
  singleton_id: number | null
  display_title: string
  display_image_url: string | null
  volume_ml: number | null
  category_slug: string
  category_name: string
  min_price: number
  max_price: number
  store_count: number
  usteda: number           // max_price - min_price
}

// ─── Product Group Detail (product page) ──────────────────────────────────

export interface StorePrice {
  store_name: string
  store_display_name: string
  store_url: string
  product_title: string
  price: number
  price_original: string
  product_url: string
  image_url: string | null
  is_cheapest: boolean
}

export interface ProductGroupDetail {
  group_id: string
  display_title: string
  volume_ml: number | null
  category_slug: string
  category_name: string
  stores: StorePrice[]
  min_price: number
  max_price: number
  usteda: number
  usteda_posto: number
}

// ─── Search ────────────────────────────────────────────────────────────────

export interface SearchResponse extends PaginatedResponse<ProductGroup> {
  query: string
}

export interface AutocompleteItem {
  group_id: string
  display_title: string
  category_name: string
  min_price: number
}

// ─── Stats ─────────────────────────────────────────────────────────────────

export interface Stats {
  products_total: number
  groups_total: number
  categories_total: number
  stores_total: number
  matched_groups: number
}

// ─── Browse filters (mirrors URL query params) ─────────────────────────────

export interface BrowseFilters {
  kategorija?: string[]   // can filter by multiple slugs
  min_cijena?: number
  max_cijena?: number
  volumen?: number
  ducani?: number         // min store count (2 = only matched groups)
  sortiraj?: 'cijena_rast' | 'cijena_pad' | 'naziv_rast' | 'naziv_pad' | 'usteda_pad'
  page?: number
  limit?: number
}
