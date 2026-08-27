import { create } from "zustand";
import { persist } from "zustand/middleware";

import { fetchChannels, fetchLocations } from "@/services/locationsApi";
import type { Location, SalesChannel } from "@/types/location";

/**
 * Which site made this sale, and which channel it came through.
 *
 * Both are optional capabilities. A tenant that has never configured
 * locations (which is every tenant except the multi-site one) loads empty
 * lists here, the selector never renders, and the POS behaves exactly as it
 * did before locations existed.
 *
 * The choice is remembered per device rather than per session, because a till
 * lives at one site and a tablet is used by one team. Asking on every order
 * would be answered wrongly within a day.
 */
interface SaleAttributionState {
  locations: Location[];
  channels: SalesChannel[];
  locationId: string | null;
  channelId: string | null;
  loaded: boolean;
}

interface SaleAttributionActions {
  load: () => Promise<void>;
  setLocationId: (id: string | null) => void;
  setChannelId: (id: string | null) => void;
  /** True only when there is a real choice for the cashier to make. */
  isAvailable: () => boolean;
}

type SaleAttributionStore = SaleAttributionState & SaleAttributionActions;

export const useSaleAttributionStore = create<SaleAttributionStore>()(
  persist(
    (set, get) => ({
      locations: [],
      channels: [],
      locationId: null,
      channelId: null,
      loaded: false,

      load: async () => {
        try {
          const [locations, channels] = await Promise.all([
            fetchLocations(),
            fetchChannels(),
          ]);
          const active = locations.filter((l) => l.is_active);
          const activeChannels = channels.filter((c) => c.is_active);

          // A remembered id that no longer exists must not be sent: the server
          // refuses an unknown location rather than substituting the default,
          // which would otherwise block every sale on this till after someone
          // deactivates a site.
          const keptLocation =
            get().locationId && active.some((l) => l.id === get().locationId)
              ? get().locationId
              : (active.find((l) => l.is_default)?.id ?? null);
          const keptChannel =
            get().channelId && activeChannels.some((c) => c.id === get().channelId)
              ? get().channelId
              : null;

          set({
            locations: active,
            channels: activeChannels,
            locationId: keptLocation,
            channelId: keptChannel,
            loaded: true,
          });
        } catch {
          // A tenant without the locations module returns an error or an empty
          // list. Either way the selector stays hidden and orders still send.
          set({ locations: [], channels: [], loaded: true });
        }
      },

      setLocationId: (id) => set({ locationId: id }),
      setChannelId: (id) => set({ channelId: id }),
      isAvailable: () => {
        const { locations, channels } = get();
        return locations.length > 0 || channels.length > 0;
      },
    }),
    {
      name: "pos-sale-attribution",
      // Only the choice is remembered. The lists are re-fetched, so a site
      // renamed or retired in admin is never served from a stale cache.
      partialize: (state) => ({
        locationId: state.locationId,
        channelId: state.channelId,
      }),
    },
  ),
);
