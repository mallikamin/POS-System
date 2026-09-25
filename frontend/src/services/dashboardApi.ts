import api from "@/lib/axios";
import type { ActivityFeed, DashboardKpis, LiveOperations } from "@/types/order";

/** Today's owner feed, newest first (D-57). Admin only. */
export async function fetchActivityFeed(): Promise<ActivityFeed> {
  const { data } = await api.get<ActivityFeed>("/dashboard/activity");
  return data;
}

export async function fetchDashboardKpis(): Promise<DashboardKpis> {
  const { data } = await api.get<DashboardKpis>("/dashboard/kpis");
  return data;
}

export async function fetchLiveOperations(): Promise<LiveOperations> {
  const { data } = await api.get<LiveOperations>("/dashboard/live");
  return data;
}
