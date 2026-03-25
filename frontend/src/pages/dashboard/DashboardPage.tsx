import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { UtensilsCrossed, ShoppingBag, Phone } from "lucide-react";
import { useUIStore } from "@/stores/uiStore";
import type { OrderType } from "@/types";

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

function DashboardPage() {
  const navigate = useNavigate();
  const { setCurrentChannel } = useUIStore();

  /* Preload all POS channel chunks on mount so navigation is instant */
  useEffect(() => {
    preloadDineIn();
    preloadTakeaway();
    preloadCallCenter();
  }, []);

  const handleChannelSelect = (channel: ChannelCard) => {
    setCurrentChannel(channel.type);
    navigate(channel.route);
  };

  return (
    <div className="flex h-full flex-col items-center justify-center p-8">
      <h2 className="mb-2 text-pos-2xl font-bold text-secondary-800">
        Select Order Channel
      </h2>
      <p className="mb-10 text-pos-base text-secondary-500">
        Choose how you would like to take the order
      </p>

      <div className="grid w-full max-w-4xl grid-cols-1 gap-6 sm:grid-cols-3">
        {channels.map((channel) => (
          <button
            key={channel.type}
            onClick={() => handleChannelSelect(channel)}
            className={`touch-feedback group flex flex-col items-center justify-center rounded-2xl p-10 text-white shadow-lg transition-all ${channel.bgClass} ${channel.hoverClass} focus:outline-none focus:ring-4 focus:ring-white/30`}
            aria-label={`Open ${channel.label} channel`}
          >
            <channel.icon className="mb-4 h-16 w-16 opacity-90 transition-transform group-hover:scale-110" />
            <span className="text-pos-2xl font-bold">{channel.label}</span>
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
