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
