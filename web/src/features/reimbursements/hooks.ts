import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/api";
import type { Reimbursement } from "../../types/api";

export function useReimbursements(filters: Record<string, string | undefined> = {}) {
  return useQuery<Reimbursement[]>({
    queryKey: ["reimbursements", filters],
    queryFn: async () => {
      const { data } = await api.get("/reimbursements", { params: filters });
      return data;
    },
  });
}

export function useReimbursement(id: string | undefined) {
  return useQuery<Reimbursement>({
    queryKey: ["reimbursements", id],
    queryFn: async () => {
      const { data } = await api.get(`/reimbursements/${id}`);
      return data;
    },
    enabled: !!id,
  });
}

export function useCreateReimbursement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      amount: string;
      currency: string;
      category: string;
      description: string;
      department_id?: string;
      receipt_id?: string;
    }) => {
      const { data } = await api.post("/reimbursements", payload);
      return data as Reimbursement;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reimbursements"] }),
  });
}

export function useApproveReimbursement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, reason }: { id: string; reason?: string }) => {
      const { data } = await api.post(`/reimbursements/${id}/approve`, { reason });
      return data as Reimbursement;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reimbursements"] }),
  });
}

export function useRejectReimbursement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, reason }: { id: string; reason?: string }) => {
      const { data } = await api.post(`/reimbursements/${id}/reject`, { reason });
      return data as Reimbursement;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reimbursements"] }),
  });
}

export function useMarkPaid() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await api.post(`/reimbursements/${id}/mark-paid`);
      return data as Reimbursement;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reimbursements"] }),
  });
}
