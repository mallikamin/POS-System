/** Danny's D-99: visit loyalty. */
import api from "@/lib/axios";

export interface LoyaltyProgress {
  customer_id: string;
  customer_name: string;
  phone: string;
  total_visits: number;
  visits_required: number;
  toward_next: number;
  rewards_earned: number;
  rewards_redeemed: number;
  rewards_available: number;
  reward_label: string;
  last_visit: string | null;
}

export interface OrderLoyaltyStatus {
  enabled: boolean;
  loyalty_code: string | null;
  reward_label: string;
  progress: LoyaltyProgress | null;
  reward_on_bill: boolean;
  redeemed_on_this_bill: boolean;
  can_redeem: boolean;
}

export interface CounterDisplay {
  loyalty_code: string;
  order_number: string;
  total: number;
  reward_label: string;
  visits_required: number;
}

export interface PublicClaimInfo {
  status: "open" | "counted" | "linked" | "unpaid" | "expired" | "disabled";
  restaurant_name: string;
  visits_required: number;
  reward_label: string;
  order_number: string;
}

export interface PublicClaimResult {
  result: "counted" | "daily_limit";
  phone: string;
  total_visits: number;
  toward_next: number;
  visits_required: number;
  rewards_available: number;
  reward_label: string;
}

/** Where a bill's QR points. Same host the till runs on. */
export function loyaltyUrl(code: string): string {
  return `${window.location.origin}/v/${code}`;
}

export async function fetchOrderLoyalty(orderId: string): Promise<OrderLoyaltyStatus> {
  const { data } = await api.get<OrderLoyaltyStatus>(`/loyalty/orders/${orderId}`);
  return data;
}

export async function redeemReward(orderId: string): Promise<LoyaltyProgress> {
  const { data } = await api.post<LoyaltyProgress>(`/loyalty/orders/${orderId}/redeem`);
  return data;
}

export async function fetchCounterDisplay(): Promise<CounterDisplay | null> {
  const { data } = await api.get<CounterDisplay | null>("/loyalty/display");
  return data;
}

export async function fetchMembers(): Promise<LoyaltyProgress[]> {
  const { data } = await api.get<LoyaltyProgress[]>("/loyalty/members");
  return data;
}

export async function fetchClaimInfo(code: string): Promise<PublicClaimInfo> {
  const { data } = await api.get<PublicClaimInfo>(`/public/loyalty/${encodeURIComponent(code)}`);
  return data;
}

export async function submitClaim(
  code: string,
  body: { phone: string; name?: string; consent: boolean }
): Promise<PublicClaimResult> {
  const { data } = await api.post<PublicClaimResult>(
    `/public/loyalty/${encodeURIComponent(code)}`,
    body
  );
  return data;
}
