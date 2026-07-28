/// <reference types="vite/client" />

/**
 * Build-time configuration.
 *
 * The storefront is a static bundle on Cloudflare with no server of its own, so
 * these are baked in at `vite build` time. There is no runtime config file to
 * edit: changing either of these means rebuilding and redeploying.
 */
interface ImportMetaEnv {
  /**
   * Base URL of the POS API, including `/api/v1` and no trailing slash.
   * Defaults to the production host. Point it at `http://localhost:8090/api/v1`
   * for local work.
   */
  readonly VITE_API_URL?: string;
  /** Tenant slug in the public routes. Defaults to `chick-shack`. */
  readonly VITE_TENANT_SLUG?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
