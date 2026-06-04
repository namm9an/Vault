import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Digest } from "@/types/api";

export function useDigests() {
  return useQuery<Digest[]>({
    queryKey: ["digests"],
    queryFn: async () => {
      const { data } = await api.get("/digest");
      return data;
    },
    refetchInterval: (query) =>
      query.state.data?.some((d) => d.status === "PENDING") ? 3000 : false,
  });
}

export function useDigest(id: string | undefined) {
  return useQuery<Digest>({
    queryKey: ["digests", id],
    queryFn: async () => {
      const { data } = await api.get(`/digest/${id}`);
      return data;
    },
    enabled: !!id,
  });
}

export function useDeleteDigest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/digest/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["digests"] }),
  });
}

export function useGenerateDigest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { period_start: string; period_end: string }) => {
      const { data } = await api.post("/digest/generate", payload);
      return data as Digest;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["digests"] }),
  });
}
