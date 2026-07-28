/**
 * Dump the storefront menu as JSON so the backend can seed it into the database.
 *
 * Why this exists
 * ---------------
 * `src/data/menu.ts` was the original source of truth: the menu was transcribed
 * from the client's printed A4 board and compiled straight into the Worker
 * bundle. That is why chickshackg84.com shows the right menu at the right
 * prices while the database knows nothing about it.
 *
 * It cannot stay that way. `POST /public/{tenant}/orders` validates every line
 * against `menu_items.id`, which is a UUID, and this file's IDs are slugs like
 * "peri-peri-half". So the menu has to exist as rows before the storefront can
 * place a real order.
 *
 * Rather than hand-transcribe 96 items into a Python seeder and guarantee
 * drift, this exports the real objects and the seeder consumes the result.
 * `MENU_ITEMS` is assembled by helper functions, so reading the file by eye is
 * exactly how a price gets mistyped.
 *
 * Usage (from storefront/):
 *   npx esbuild scripts/export-menu.ts --bundle --format=esm --platform=node \
 *       --outfile=.tmp/export-menu.mjs
 *   node .tmp/export-menu.mjs > ../backend/app/scripts/data/chick_shack_menu.json
 *
 * Once the database is authoritative the storefront should fetch
 * `GET /public/chick-shack/menu` instead, and this script becomes the migration
 * tool that got us there rather than a thing to run every deploy.
 */

import { CATEGORIES, MENU_ITEMS, SHOP } from "../src/data/menu";

const payload = {
  _generated_by: "storefront/scripts/export-menu.ts",
  _source: "storefront/src/data/menu.ts",
  shop: SHOP,
  categories: CATEGORIES,
  items: MENU_ITEMS,
};

process.stdout.write(JSON.stringify(payload, null, 2));
