import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { User, UserInviteResponse, UserListResponse, UserRole } from "@/types/api";

const USERS_KEY = ["users"] as const;

export function useUsers() {
  return useQuery({
    queryKey: USERS_KEY,
    queryFn: async (): Promise<User[]> => {
      const { data } = await api.get<UserListResponse>("/users");
      return data.items;
    },
  });
}

export function useInviteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      email: string;
      full_name: string;
      role: UserRole;
      password: string;
      department_id?: string | null;
    }): Promise<UserInviteResponse> => {
      const { data } = await api.post<UserInviteResponse>("/users", payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: USERS_KEY }),
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      id: string;
      role?: UserRole;
      is_active?: boolean;
      department_id?: string | null;
    }): Promise<User> => {
      const { id, ...rest } = payload;
      const { data } = await api.patch<{ user: User }>(`/users/${id}`, rest);
      return data.user;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: USERS_KEY }),
  });
}
