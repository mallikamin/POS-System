/**
 * Danny's D-99: a bill's loyalty QR. Rendered to a PNG data URL so it prints
 * on the 80mm receipt exactly like it shows on screen.
 */
import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { loyaltyUrl } from "@/services/loyaltyApi";

interface LoyaltyQRProps {
  code: string;
  /** Rendered size in CSS pixels. */
  size?: number;
  className?: string;
}

export function LoyaltyQR({ code, size = 120, className }: LoyaltyQRProps) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    QRCode.toDataURL(loyaltyUrl(code), { margin: 1, width: size * 2, errorCorrectionLevel: "M" })
      .then((url) => alive && setSrc(url))
      .catch(() => alive && setSrc(null));
    return () => {
      alive = false;
    };
  }, [code, size]);

  if (!src) return null;
  return (
    <img
      src={src}
      width={size}
      height={size}
      alt={`Loyalty code ${code}`}
      className={className}
    />
  );
}
