export type StoredAuth = {
  access: string;
  refresh: string;
};

const KEY = "vault.auth";

export function getAuth(): StoredAuth | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StoredAuth;
  } catch {
    return null;
  }
}

export function setAuth(a: StoredAuth): void {
  localStorage.setItem(KEY, JSON.stringify(a));
}

export function clearAuth(): void {
  localStorage.removeItem(KEY);
}
