export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Typed GET request to the backend API.
 * Prefixes the path with /api automatically.
 * Builds query params safely with URLSearchParams — no string interpolation.
 */
export async function apiGet<T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined | null>,
): Promise<T> {
  const url = new URL(`/api${path}`, window.location.origin)

  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.append(key, String(value))
      }
    }
  }

  const res = await fetch(url.toString(), {
    headers: { Accept: 'application/json' },
  })

  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const body = await res.json()
      if (typeof body?.error === 'string') message = body.error
    } catch {
      // ignore parse failure, keep generic message
    }
    throw new ApiError(res.status, message)
  }

  return res.json() as Promise<T>
}
