import axios, { AxiosError, type AxiosRequestConfig } from "axios";
import { clearAuth, getAuth, setAuth } from "./auth";

const baseURL = (import.meta.env.VITE_API_BASE_URL ?? "") + "/api/v1";

export const api = axios.create({ baseURL });

api.interceptors.request.use((cfg) => {
  const auth = getAuth();
  if (auth?.access) {
    cfg.headers = cfg.headers ?? {};
    cfg.headers.Authorization = `Bearer ${auth.access}`;
  }
  return cfg;
});

let refreshing: Promise<string | null> | null = null;

async function tryRefresh(): Promise<string | null> {
  if (refreshing) return refreshing;
  refreshing = (async () => {
    const auth = getAuth();
    if (!auth?.refresh) return null;
    try {
      const { data } = await axios.post(`${baseURL}/auth/refresh`, { refresh_token: auth.refresh });
      setAuth({ access: data.access_token, refresh: data.refresh_token });
      return data.access_token as string;
    } catch {
      clearAuth();
      return null;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as AxiosRequestConfig & { _retry?: boolean };
    if (error.response?.status === 401 && original && !original._retry && !original.url?.endsWith("/auth/refresh")) {
      original._retry = true;
      const newAccess = await tryRefresh();
      if (newAccess) {
        original.headers = { ...(original.headers ?? {}), Authorization: `Bearer ${newAccess}` };
        return api.request(original);
      }
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);
