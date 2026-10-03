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

/** The counter screen. The QR fields are null while no paid bill is waiting (D-106). */
export interface CounterDisplay {
  loyalty_code: string | null;
  order_number: string | null;
  total: number | null;
  reward_label: string;
  visits_required: number;
}

export interface PublicClaimInfo {
  /** pending: a number is on this unpaid bill; the visit counts when it is paid. */
  status: "open" | "counted" | "linked" | "pending" | "expired" | "disabled";
  restaurant_name: string;
  visits_required: number;
  reward_label: string;
  order_number: string;
  /** D-106: the shop, so the page can show its own logo. */
  tenant_slug: string;
  /** This restaurant's card can be added to Google Wallet. Absent from older servers. */
  google_wallet?: boolean;
}

export interface PublicClaimResult {
  /** pending: scanned before paying (dine-in); counted at payment. */
  result: "counted" | "daily_limit" | "pending";
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
  // idle=1: the rule comes back even with no bill waiting (null QR fields).
  const { data } = await api.get<CounterDisplay | null>("/loyalty/display", { params: { idle: 1 } });
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

/** The "Add to Google Wallet" link for the guest whose number is on this bill. */
export async function fetchGoogleWalletUrl(code: string, phone: string): Promise<string> {
  const { data } = await api.post<{ url: string }>(
    `/public/loyalty/${encodeURIComponent(code)}/google-wallet`,
    { phone }
  );
  return data.url;
}
