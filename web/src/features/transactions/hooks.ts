import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  Transaction,
  TransactionEvent,
  TransactionWithEvents,
  SpendCategory,
  TransactionState,
} from "@/types/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type TransactionFilters = {
  from_date?: string;
  to_date?: string;
  category?: SpendCategory;
  state?: TransactionState;
  card_id?: string;
  department_id?: string;
  user_id?: string;
};

export type TransactionCreatePayload = {
  card_id: string;
  amount: string;
  merchant: string;
  category: SpendCategory;
  currency?: string;
  description?: string;
  department_id?: string | null;
  occurred_at?: string;
  receipt_id?: string;
};

// ---------------------------------------------------------------------------
// Keys
// ---------------------------------------------------------------------------

const TXNS_KEY = ["transactions"] as const;
const txnKey = (id: string) => [...TXNS_KEY, id] as const;
const txnEventsKey = (id: string) => [...TXNS_KEY, id, "events"] as const;

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

export function useTransactions(filters?: TransactionFilters) {
  return useQuery({
    queryKey: [...TXNS_KEY, filters],
    queryFn: async (): Promise<Transaction[]> => {
      const params = new URLSearchParams();
      if (filters?.from_date) params.set("from_date", filters.from_date);
      if (filters?.to_date) params.set("to_date", filters.to_date);
      if (filters?.category) params.set("category", filters.category);
      if (filters?.state) params.set("state", filters.state);
      if (filters?.card_id) params.set("card_id", filters.card_id);
      if (filters?.department_id) params.set("department_id", filters.department_id);
      if (filters?.user_id) params.set("user_id", filters.user_id);
      const { data } = await api.get<Transaction[]>(`/transactions?${params}`);
      return data;
    },
  });
}

export function useTransaction(id: string | null) {
  return useQuery({
    queryKey: txnKey(id ?? ""),
    queryFn: async (): Promise<TransactionWithEvents> => {
      const { data } = await api.get<TransactionWithEvents>(`/transactions/${id}`);
      return data;
    },
    enabled: !!id,
    // Auto-poll every 2 s while the ARQ policy engine is still running
    refetchInterval: (query) =>
      query.state.data?.state === "POLICY_CHECKED" ? 2000 : false,
  });
}

export function useTransactionEvents(id: string | null) {
  return useQuery({
    queryKey: txnEventsKey(id ?? ""),
    queryFn: async (): Promise<TransactionEvent[]> => {
      const { data } = await api.get<TransactionEvent[]>(`/transactions/${id}/events`);
      return data;
    },
    enabled: !!id,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export function useCreateTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: TransactionCreatePayload): Promise<Transaction> => {
      const { data } = await api.post<Transaction>("/transactions", payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: TXNS_KEY }),
  });
}

export function useApproveTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, reason }: { id: string; reason: string }): Promise<Transaction> => {
      const { data } = await api.post<Transaction>(`/transactions/${id}/approve`, { reason });
      return data;
    },
    onSuccess: (_data, { id }) => {
      qc.invalidateQueries({ queryKey: TXNS_KEY });
      qc.invalidateQueries({ queryKey: txnKey(id) });
    },
  });
}

export function useRejectTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, reason }: { id: string; reason: string }): Promise<Transaction> => {
      const { data } = await api.post<Transaction>(`/transactions/${id}/reject`, { reason });
      return data;
    },
    onSuccess: (_data, { id }) => {
      qc.invalidateQueries({ queryKey: TXNS_KEY });
      qc.invalidateQueries({ queryKey: txnKey(id) });
    },
  });
}
