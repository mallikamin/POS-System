import { useEffect } from "react";
import { MapPin, Route } from "lucide-react";

import { useSaleAttributionStore } from "@/stores/saleAttributionStore";

/**
 * Which site made this sale, and which channel it came through.
 *
 * Renders nothing at all for a tenant with no locations and no channels, which
 * is every single-site tenant. Their cart panel is unchanged.
 *
 * Why it belongs on the cart and not in a settings screen: the site is fixed
 * per till, but the channel changes order by order. A Talabat order and a
 * walk-in are rung up on the same screen a minute apart, and the commission
 * difference between them is the entire point of the profitability report.
 */
export function SaleAttributionPicker() {
  const locations = useSaleAttributionStore((s) => s.locations);
  const channels = useSaleAttributionStore((s) => s.channels);
  const locationId = useSaleAttributionStore((s) => s.locationId);
  const channelId = useSaleAttributionStore((s) => s.channelId);
  const loaded = useSaleAttributionStore((s) => s.loaded);
  const load = useSaleAttributionStore((s) => s.load);
  const setLocationId = useSaleAttributionStore((s) => s.setLocationId);
  const setChannelId = useSaleAttributionStore((s) => s.setChannelId);

  useEffect(() => {
    if (!loaded) void load();
  }, [loaded, load]);

  if (locations.length === 0 && channels.length === 0) return null;

  const selectClass =
    "w-full h-11 rounded-md border border-secondary-200 bg-white px-2 text-sm " +
    "text-secondary-900 focus:outline-none focus:ring-2 focus:ring-primary-500";

  return (
    <div className="grid grid-cols-2 gap-2">
      {locations.length > 0 && (
        <label className="space-y-1">
          <span className="flex items-center gap-1 text-xs font-medium text-secondary-500">
            <MapPin className="h-3 w-3" />
            Site
          </span>
          <select
            className={selectClass}
            value={locationId ?? ""}
            onChange={(e) => setLocationId(e.target.value || null)}
          >
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.name}
              </option>
            ))}
          </select>
        </label>
      )}

      {channels.length > 0 && (
        <label className="space-y-1">
          <span className="flex items-center gap-1 text-xs font-medium text-secondary-500">
            <Route className="h-3 w-3" />
            Channel
          </span>
          <select
            className={selectClass}
            value={channelId ?? ""}
            onChange={(e) => setChannelId(e.target.value || null)}
          >
            {/* Deliberately offered: a sale that genuinely came through no
                channel must be recordable as such, rather than silently
                inheriting whatever the last order used. */}
            <option value="">No channel</option>
            {channels.map((channel) => (
              <option key={channel.id} value={channel.id}>
                {channel.name}
                {channel.commission_bps > 0
                  ? ` (${(channel.commission_bps / 100).toFixed(2)}%)`
                  : ""}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}
