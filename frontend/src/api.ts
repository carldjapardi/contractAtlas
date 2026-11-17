export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const data: { detail?: unknown } = await response.json();
      if (typeof data.detail === 'string') message = data.detail;
    } catch { /* Keep the HTTP error if no JSON was returned. */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
