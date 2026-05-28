import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { clearAuth, getAuth, setAuth } from "@/lib/auth";
import type { MeResponse, TokenPair } from "@/types/api";

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async (): Promise<MeResponse> => {
      const { data } = await api.get<MeResponse>("/auth/me");
      return data;
    },
    enabled: !!getAuth(),
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { email: string; password: string }): Promise<TokenPair> => {
      const { data } = await api.post<TokenPair>("/auth/login", vars);
      return data;
    },
    onSuccess: (data) => {
      setAuth({ access: data.access_token, refresh: data.refresh_token });
      qc.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

export function useSignup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: {
      org_name: string;
      email: string;
      password: string;
      full_name: string;
    }): Promise<TokenPair> => {
      const { data } = await api.post<TokenPair>("/auth/signup", vars);
      return data;
    },
    onSuccess: (data) => {
      setAuth({ access: data.access_token, refresh: data.refresh_token });
      qc.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const auth = getAuth();
      if (auth?.refresh) {
        try {
          await api.post("/auth/logout", { refresh_token: auth.refresh });
        } catch {
          // ignore
        }
      }
      clearAuth();
    },
    onSuccess: () => {
      qc.clear();
    },
  });
}
