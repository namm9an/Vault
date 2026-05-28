import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import type { DashboardSummary, TimeseriesPoint } from "../../types/api";

export function useDashboardSummary(fromDate: string, toDate: string) {
  return useQuery<DashboardSummary>({
    queryKey: ["dashboard", "summary", fromDate, toDate],
    queryFn: async () => {
      const { data } = await api.get("/dashboard/summary", {
        params: { from_date: fromDate, to_date: toDate },
      });
      return data;
    },
    staleTime: 5 * 60 * 1000, // 5 min matches server cache TTL
  });
}

export function useDashboardTimeseries(fromDate: string, toDate: string, bucket = "day") {
  return useQuery<TimeseriesPoint[]>({
    queryKey: ["dashboard", "timeseries", fromDate, toDate, bucket],
    queryFn: async () => {
      const { data } = await api.get("/dashboard/timeseries", {
        params: { from_date: fromDate, to_date: toDate, bucket },
      });
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}
