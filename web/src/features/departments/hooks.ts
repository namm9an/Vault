import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/api";
import type { BudgetStatus, Department } from "../../types/api";

export function useDepartments() {
  return useQuery<Department[]>({
    queryKey: ["departments"],
    queryFn: async () => {
      const { data } = await api.get("/api/v1/departments");
      return data;
    },
  });
}

export function useBudgetStatus(deptId: string | undefined) {
  return useQuery<BudgetStatus>({
    queryKey: ["departments", deptId, "budget"],
    queryFn: async () => {
      const { data } = await api.get(`/api/v1/departments/${deptId}/budget-status`);
      return data;
    },
    enabled: !!deptId,
  });
}

export function useCreateDepartment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      name: string;
      monthly_budget: string;
      budget_currency?: string;
      alert_threshold_pct?: number;
      manager_id?: string;
    }) => {
      const { data } = await api.post("/api/v1/departments", payload);
      return data as Department;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["departments"] }),
  });
}

export function useUpdateDepartment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      ...payload
    }: {
      id: string;
      name?: string;
      monthly_budget?: string;
      alert_threshold_pct?: number;
    }) => {
      const { data } = await api.patch(`/api/v1/departments/${id}`, payload);
      return data as Department;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["departments"] }),
  });
}

export function useDeleteDepartment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/api/v1/departments/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["departments"] }),
  });
}
