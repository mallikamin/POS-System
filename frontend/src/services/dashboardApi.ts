import api from "@/lib/axios";
import type { DashboardKpis, LiveOperations } from "@/types/order";

export async function fetchDashboardKpis(): Promise<DashboardKpis> {
  const { data } = await api.get<DashboardKpis>("/dashboard/kpis");
  return data;
}

export async function fetchLiveOperations(): Promise<LiveOperations> {
  const { data } = await api.get<LiveOperations>("/dashboard/live");
  return data;
}
