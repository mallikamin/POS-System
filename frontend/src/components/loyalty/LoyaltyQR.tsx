/**
 * Danny's D-99: a bill's loyalty QR. Rendered to a PNG data URL so it prints
 * on the 80mm receipt exactly like it shows on screen.
 */
import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { loyaltyUrl } from "@/services/loyaltyApi";

interface QRImageProps {
  /** What the QR encodes (a full URL). */
  value: string;
  alt: string;
  /** Rendered size in CSS pixels. */
  size?: number;
  className?: string;
}

/** Any link as a QR image. Always dark on light: what every phone camera reads best. */
export function QRImage({ value, alt, size = 120, className }: QRImageProps) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    QRCode.toDataURL(value, { margin: 1, width: size * 2, errorCorrectionLevel: "M" })
      .then((url) => alive && setSrc(url))
      .catch(() => alive && setSrc(null));
    return () => {
      alive = false;
    };
  }, [value, size]);

  if (!src) return null;
  return <img src={src} width={size} height={size} alt={alt} className={className} />;
}

interface LoyaltyQRProps {
  code: string;
  size?: number;
  className?: string;
}

export function LoyaltyQR({ code, size = 120, className }: LoyaltyQRProps) {
  return <QRImage value={loyaltyUrl(code)} alt={`Loyalty code ${code}`} size={size} className={className} />;
}
