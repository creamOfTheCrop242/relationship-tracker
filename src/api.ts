export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    credentials: 'include', ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  })
  if (!response.ok) {
    if (response.status === 401) throw new Error('Your session has expired. Please sign out and sign in again.')
    if (response.status === 422) throw new Error('Please check the fields and try again.')
    const body = await response.json().catch(() => null)
    throw new Error(typeof body?.detail === 'string' ? body.detail : 'Could not complete the request. Please try again.')
  }
  return response.status === 204 ? undefined as T : response.json()
}
