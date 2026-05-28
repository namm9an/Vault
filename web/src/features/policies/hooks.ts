import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Policy } from "@/types/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type PolicyCreatePayload = {
  text: string;
  is_active?: boolean;
};

export type PolicyUpdatePayload = {
  text?: string;
  is_active?: boolean;
};

// ---------------------------------------------------------------------------
// Keys
// ---------------------------------------------------------------------------

const POLICIES_KEY = ["policies"] as const;
const policyKey = (id: string) => [...POLICIES_KEY, id] as const;

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

export function usePolicies() {
  return useQuery({
    queryKey: POLICIES_KEY,
    queryFn: async (): Promise<Policy[]> => {
      const { data } = await api.get<Policy[]>("/policies");
      return data;
    },
  });
}

export function usePolicy(id: string | null) {
  return useQuery({
    queryKey: policyKey(id ?? ""),
    queryFn: async (): Promise<Policy> => {
      const { data } = await api.get<Policy>(`/policies/${id}`);
      return data;
    },
    enabled: !!id,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export function useCreatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: PolicyCreatePayload): Promise<Policy> => {
      const { data } = await api.post<Policy>("/policies", payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: POLICIES_KEY }),
  });
}

export function useUpdatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      ...payload
    }: PolicyUpdatePayload & { id: string }): Promise<Policy> => {
      const { data } = await api.patch<Policy>(`/policies/${id}`, payload);
      return data;
    },
    onSuccess: (_data, { id }) => {
      qc.invalidateQueries({ queryKey: POLICIES_KEY });
      qc.invalidateQueries({ queryKey: policyKey(id) });
    },
  });
}

export function useDeletePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      await api.delete(`/policies/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: POLICIES_KEY }),
  });
}
