import { useEffect } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { UtensilsCrossed, ShoppingBag, Phone, Loader2, Route } from "lucide-react";
import { useUIStore } from "@/stores/uiStore";
import { useConfigStore } from "@/stores/configStore";
import { useSaleAttributionStore } from "@/stores/saleAttributionStore";
import { isModuleHidden, type UiModule } from "@/lib/modules";
import { cn } from "@/lib/utils";
import type { OrderType } from "@/types";
import type { SalesChannel } from "@/types/location";

/** Channel to module slug. Kept next to the cards so the two cannot drift. */
const CHANNEL_MODULES: Record<OrderType, UiModule> = {
  dine_in: "dine-in",
  takeaway: "takeaway",
  call_center: "call-center",
};

/* Preload POS-critical chunks so navigation is instant */
const preloadDineIn = () => import("@/pages/dine-in/DineInPage");
const preloadTakeaway = () => import("@/pages/takeaway/TakeawayPage");
const preloadCallCenter = () => import("@/pages/call-center/CallCenterPage");

interface ChannelCard {
  type: OrderType;
  label: string;
  description: string;
  icon: React.ElementType;
  route: string;
  bgClass: string;
  hoverClass: string;
  /** A sales channel tile (Careem, Deliveroo...) rather than an order type. */
  salesChannel?: SalesChannel;
}

const channels: ChannelCard[] = [
  {
    type: "dine_in",
    label: "Dine-In",
    description: "Manage tables and dine-in orders",
    icon: UtensilsCrossed,
    route: "/dine-in",
    bgClass: "bg-primary-500",
    hoverClass: "hover:bg-primary-600",
  },
  {
    type: "takeaway",
    label: "Takeaway",
    description: "Quick takeaway and pickup orders",
    icon: ShoppingBag,
    route: "/takeaway",
    bgClass: "bg-success-500",
    hoverClass: "hover:bg-success-600",
  },
  {
    type: "call_center",
    label: "Call Center",
    description: "Phone orders and delivery",
    icon: Phone,
    route: "/call-center",
    bgClass: "bg-accent-500",
    hoverClass: "hover:bg-accent-600",
  },
];

/*
 * Aggregator tiles cycle through a few colours so six of them do not read as
 * one block. Purely cosmetic; the channel's identity is its name.
 */
const SALES_CHANNEL_COLOURS: Array<[string, string]> = [
  ["bg-orange-500", "hover:bg-orange-600"],
  ["bg-emerald-600", "hover:bg-emerald-700"],
  ["bg-sky-600", "hover:bg-sky-700"],
  ["bg-yellow-500", "hover:bg-yellow-600"],
  ["bg-rose-500", "hover:bg-rose-600"],
  ["bg-violet-500", "hover:bg-violet-600"],
];

function DashboardPage() {
  const navigate = useNavigate();
  const { setCurrentChannel } = useUIStore();
  const config = useConfigStore((s) => s.config);
  const configLoading = useConfigStore((s) => s.isLoading);
  const onlineOnly = config?.online_ordering_only === true;
  const salesChannels = useSaleAttributionStore((s) => s.channels);
  const attributionLoaded = useSaleAttributionStore((s) => s.loaded);
  const loadAttribution = useSaleAttributionStore((s) => s.load);
  const setChannelId = useSaleAttributionStore((s) => s.setChannelId);

  /* Preload all POS channel chunks on mount so navigation is instant */
  useEffect(() => {
    if (onlineOnly) return;
    preloadDineIn();
    preloadTakeaway();
    preloadCallCenter();
  }, [onlineOnly]);

  /* The sales channels decide how many tiles there are, so load them here
     rather than waiting for the cart panel to ask. */
  useEffect(() => {
    if (!onlineOnly && !attributionLoaded) void loadAttribution();
  }, [onlineOnly, attributionLoaded, loadAttribution]);

  /*
   * A website-only shop (OI-54): every one of the three channel tiles is a
   * dead end, so land on the online-orders queue instead. Per-tenant via
   * config — the core POS keeps the channel selector for everyone else.
   */
  if (onlineOnly) {
    return <Navigate to="/online-orders" replace />;
  }

  /*
   * Don't flash the channel selector before the config has answered whether
   * this tenant should even see it. If the fetch errors, config stays null
   * and we fall through to the selector rather than trapping everyone here.
   */
  if (!config && configLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary-400" />
      </div>
    );
  }

  const handleChannelSelect = (channel: ChannelCard) => {
    setCurrentChannel(channel.type);
    /*
     * A sales-channel tile (Careem, Deliveroo, ...) is a takeaway-shaped
     * order rung up under that channel: no table, no phone lookup, and the
     * commission attributed from the first tap. A plain order-type tile
     * clears the remembered channel so a walk-in is never silently booked
     * under whatever aggregator the last order used. The picker on the cart
     * can still change it before the order is sent.
     */
    setChannelId(channel.salesChannel?.id ?? null);
    navigate(channel.route);
  };

  /*
   * Only the channels this restaurant actually operates.
   *
   * Found in UAT on 2026-08-27: a bakery with no tables at all was shown
   * "Dine-In" as the largest and left-most action on the first screen after
   * signing in. Offering a client a channel they do not have is not a neutral
   * default, it reads as a system built for somebody else.
   *
   * Empty hidden list means all three, which is every existing tenant, so this
   * changes nothing for anyone until a slug is set. Grid columns are derived
   * from the count rather than fixed at three, or hiding one would leave a hole.
   */
  const orderTypeTiles = channels
    .filter((channel) => !isModuleHidden(config, CHANNEL_MODULES[channel.type]))
    .map((channel) =>
      /*
       * Martin (FZ LLC, 2026-09-02): "there should be pick up / call center /
       * deliveroo / careem / keeta / noon". The walk-in tile takes the
       * tenant's own word for it; the order_type underneath stays `takeaway`.
       */
      channel.type === "takeaway" && config?.takeaway_label
        ? {
            ...channel,
            label: config.takeaway_label,
            description: "Walk-in and collection orders",
          }
        : channel,
    );

  /*
   * One tile per sales channel flagged for the POS (Sales Channels screen).
   * A tenant with no channels, which is every tenant but FZ LLC, sees exactly
   * the tiles it saw before.
   */
  const salesChannelTiles: ChannelCard[] = salesChannels
    .filter((channel) => channel.is_active && channel.pos_visible !== false)
    .map((channel, index) => {
      const [bgClass, hoverClass] =
        SALES_CHANNEL_COLOURS[index % SALES_CHANNEL_COLOURS.length]!;
      return {
        type: "takeaway",
        label: channel.name,
        description:
          channel.commission_bps > 0
            ? `${(channel.commission_bps / 100).toFixed(channel.commission_bps % 100 === 0 ? 0 : 2)}% commission`
            : "No commission",
        icon: Route,
        route: "/takeaway",
        bgClass,
        hoverClass,
        salesChannel: channel,
      };
    });

  const visibleChannels = [...orderTypeTiles, ...salesChannelTiles];

  return (
    <div className="flex h-full flex-col items-center justify-center overflow-y-auto p-4 sm:p-8">
      <h2 className="mb-2 text-pos-2xl font-bold text-secondary-800">
        Select Order Channel
      </h2>
      <p className="mb-6 text-pos-base text-secondary-500 sm:mb-10">
        Choose how you would like to take the order
      </p>

      <div
        className={cn(
          "grid w-full max-w-5xl grid-cols-1 gap-4 sm:gap-6",
          visibleChannels.length === 1 && "sm:max-w-sm sm:grid-cols-1",
          visibleChannels.length === 2 && "sm:max-w-2xl sm:grid-cols-2",
          visibleChannels.length >= 3 && "sm:grid-cols-3",
          visibleChannels.length >= 4 && "lg:grid-cols-4",
        )}
      >
        {visibleChannels.map((channel) => (
          <button
            key={channel.salesChannel?.id ?? channel.type}
            onClick={() => handleChannelSelect(channel)}
            className={cn(
              "touch-feedback group flex flex-col items-center justify-center rounded-2xl p-6 text-white shadow-lg transition-all focus:outline-none focus:ring-4 focus:ring-white/30",
              visibleChannels.length <= 3 ? "sm:p-10" : "sm:p-8",
              channel.bgClass,
              channel.hoverClass,
            )}
            aria-label={`Open ${channel.label} channel`}
          >
            <channel.icon
              className={cn(
                "mb-4 opacity-90 transition-transform group-hover:scale-110",
                visibleChannels.length <= 3 ? "h-16 w-16" : "h-12 w-12",
              )}
            />
            <span className={visibleChannels.length <= 3 ? "text-pos-2xl font-bold" : "text-pos-xl font-bold"}>
              {channel.label}
            </span>
            <span className="mt-2 text-pos-sm opacity-80">
              {channel.description}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

export default DashboardPage;
