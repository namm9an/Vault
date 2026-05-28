import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Card, SpendCategory } from "@/types/api";

type CardCreatePayload = {
  user_id: string;
  nickname: string;
  department_id?: string | null;
  daily_limit: string;
  monthly_limit: string;
  total_limit: string;
  category_restrictions: SpendCategory[];
  currency?: string;
};

type CardUpdatePayload = Partial<Omit<CardCreatePayload, "user_id">>;

const CARDS_KEY = ["cards"] as const;

export function useCards() {
  return useQuery({
    queryKey: CARDS_KEY,
    queryFn: async (): Promise<Card[]> => {
      const { data } = await api.get<Card[]>("/cards");
      return data;
    },
  });
}

export function useCard(id: string) {
  return useQuery({
    queryKey: [...CARDS_KEY, id],
    queryFn: async (): Promise<Card> => {
      const { data } = await api.get<{ card: Card }>(`/cards/${id}`);
      return data.card;
    },
  });
}

export function useCreateCard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CardCreatePayload): Promise<Card> => {
      const { data } = await api.post<{ card: Card }>("/cards", payload);
      return data.card;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: CARDS_KEY }),
  });
}

export function useUpdateCard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, ...payload }: { id: string } & CardUpdatePayload): Promise<Card> => {
      const { data } = await api.patch<{ card: Card }>(`/cards/${id}`, payload);
      return data.card;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: CARDS_KEY }),
  });
}

function useCardAction(action: "freeze" | "unfreeze" | "cancel") {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string): Promise<Card> => {
      const { data } = await api.post<{ card: Card }>(`/cards/${id}/${action}`);
      return data.card;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: CARDS_KEY }),
  });
}

export function useFreezeCard() { return useCardAction("freeze"); }
export function useUnfreezeCard() { return useCardAction("unfreeze"); }
export function useCancelCard() { return useCardAction("cancel"); }
