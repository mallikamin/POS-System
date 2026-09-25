/**
 * Per-restaurant logo and display name for the screens a client sees first.
 *
 * Keyed by tenant slug and shipped as static files in `public/tenant-logos/`,
 * so a logo needs no database change and costs other tenants no request. A
 * tenant with no entry keeps today's plain-text screens.
 *
 * Danny's (D-01, 2026-09-25): the logo is the 160px JPG the client supplied.
 * Swap the file for a larger or vector version when they send one.
 */

import { useEffect } from "react";

export interface TenantBrand {
  logo: string;
  /** Shown on the login screen in place of "POS System". */
  name: string;
}

const BRANDS: Record<string, TenantBrand> = {
  dannys: { logo: "/tenant-logos/dannys.jpg", name: "Danny's Restaurant" },
};

export function tenantBrand(slug: string | null | undefined): TenantBrand | null {
  if (!slug) return null;
  return BRANDS[slug.trim().toLowerCase()] ?? null;
}

const DEFAULT_TITLE = "POS System";

/**
 * The browser tab: the shop's name and logo instead of "POS System" and a
 * blank globe (Danny's D-59). A tenant with no brand keeps the default title
 * and no icon, exactly as before.
 */
export function useTenantTab(slug: string | null | undefined): void {
  const brand = tenantBrand(slug);
  useEffect(() => {
    document.title = brand ? brand.name : DEFAULT_TITLE;
    let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    if (!brand) {
      link?.remove();
      return;
    }
    if (!link) {
      link = document.createElement("link");
      link.rel = "icon";
      document.head.appendChild(link);
    }
    link.href = brand.logo;
  }, [brand]);
}
