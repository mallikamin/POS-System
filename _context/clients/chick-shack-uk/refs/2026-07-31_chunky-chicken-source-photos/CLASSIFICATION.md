# Chunky Chicken source photos — classification and proposed mapping

**Source:** URLs supplied by Malik 2026-07-31, from `www.chunky-chicken.uk` (homepage) and
`chunkychicken.orderyoyo.co.uk` (their live ordering platform — accessible directly, unlike
`chunkychicken.app4food.co.uk` which is behind a Cloudflare bot challenge and was NOT
scraped/bypassed).

**Decision, 2026-07-31 (Malik, via AskUserQuestion, informed choice after seeing the full
classification below):** use all of these **except the one branded image**
(`menuitem-10.jpg`, which has "CHUNKY CHICKEN" printed into the pixels — never usable
regardless of the broader call). That is **15 of 16** images to integrate.

⚠️ Malik was told 8 of these are the restaurant's own custom commissioned photography (not
generic stock) before deciding — flagged once, decision stands, not to be re-argued.

## Classification

| File | Source URL (query string omitted) | Type |
|---|---|---|
| `hero-picture.jpg` | chunky-chicken.uk/wp-content/uploads/2022/07/Hero-picture.jpg | Custom — loaded fried chicken burger, onion rings, cheese, mayo |
| `dsc-5685.jpg` | .../DSC_5685-768x512.jpg | Custom — near-duplicate frame of hero-picture, same shoot |
| `dsc-5702.jpg` | .../DSC_5702-768x512.jpg | Custom — double beef patty, cheese, hashbrown-style topping |
| `dsc-5773.jpg` | .../DSC_5773-768x512.jpg | Custom — sauced/glazed fried wings on parchment |
| `menuitem-1.jpg` | orderyoyo `57374_9d2731683be7378ca55ae6a0835f735f.jpg` | **Generic/stock** — a 3-in-1 collage: "Juicy Chicken Strips" banner, a chicken-nuggets promo shot, a popcorn-chicken bucket. NOT a single clean photo — needs cropping into pieces if used at all |
| `menuitem-2.jpg` | orderyoyo `..._4a32fe5a92692773f4cee45df42a0bdf.jpg` | Custom — chicken wrap, same dark-wood shoot as hero-picture |
| `menuitem-3.jpg` | orderyoyo `..._cc89d6678dfe33aba7834bc4e0264b63.jpg` | Ambiguous — chicken over rice/noodles in a takeaway box with salad + coleslaw. Not the studio style, not obviously stock either; possibly a real customer/staff phone photo |
| `menuitem-4.jpg` | orderyoyo `..._cc214658e362d65f03d3ca191f522567.jpg` | Custom — chicken wrap, different angle, same shoot as menuitem-2 |
| `menuitem-5.jpg` | orderyoyo `..._057de5750b45ceed235d760b5409a5c3.jpg` | Custom — plain beef cheeseburger, lettuce, same shoot style |
| `menuitem-6.jpg` | orderyoyo `..._e1ca15c9e8b35ec1daea2462e9239ff7.jpg` | **Generic/stock** — fried chicken + fries basket + a Coca-Cola can, blue backdrop (different style entirely; branded third-party product placement is a stock-photo tell) |
| `menuitem-7.jpg` | orderyoyo `..._697de8af763851bd2950d3e03cc077e3.jpg` | Custom — plain single chicken fillet burger, same shoot style |
| `menuitem-8.jpg` | orderyoyo `..._f1173c179ea2de809ae3dea559f48721.jpg` | **Generic/stock** — fried chicken + 3 fries bags + a Pepsi bottle, in front of a **fake "Chicken ___" branded box with a rooster logo that is not Chunky Chicken's real branding** — clear stock-photo tell |
| `menuitem-9.jpg` | orderyoyo `..._2abe9c7803ade19f2a3d9b2771517100.jpg` | **Generic/stock** — 2 burgers + fries + gravy cup + a large Pepsi bottle, grey/dark-wood backdrop, same stock family as menuitem-8 |
| `menuitem-10.jpg` | orderyoyo `..._4a2a3bed6905b8fbe6cedcf9a05b751d.jpg` | **EXCLUDED — has "CHUNKY CHICKEN" text baked into the image itself.** Never use, regardless of the broader decision |
| `menuitem-11.jpg` | orderyoyo `..._0c2568d00782e6fdf22801d7c399f641.jpg` | **Generic/stock** — popcorn chicken, ketchup dip, parsley garnish on a wooden board — classic stock food-photography styling |
| `menuitem-12.jpg` | orderyoyo `..._5bdc70a0b02a90763ae3e0db98c68d1d.jpg` | **Generic/stock** — chicken nuggets stack on a **plain white cutout background** — textbook stock/catalog product photo. ⚠️ White background will look inconsistent against the site's dark `ink` theme — worth a plain colour swap or vignette before use, or padding/matting it, not a straight drop-in |

## Proposed item mapping — NOT YET EXECUTED, verify each one before wiring in

Cross-check every row below against `storefront/src/data/menu.ts` (item names, categories)
before assigning — this is a live site and Malik was explicit: **"make sure products and
pictures match, don't want a screwup."** Treat this table as a first-pass proposal, not a
final answer — several are inexact fits (no item on this menu literally has onion rings, for
instance) and deserve a second look, ideally cross-checked against the item's own
`description` string in `menu.ts`, not just a first impression.

| Image | Proposed target | Why | Confidence |
|---|---|---|---|
| `hero-picture.jpg` | Burgers category fallback image (replaces current `burger-chicken.webp`) | Best generic "loaded burger" representative; no exact item match (onion rings aren't on any Chick Shack item) | Medium |
| `dsc-5685.jpg` | `b-double-chicken` "Double Chicken Burger" | Near-duplicate of hero-picture; stacked chicken visual fits a "double" item loosely | Low — reconsider |
| `dsc-5702.jpg` | `b-big-shack` "The Big Shack Burger" | Beef patty + cheese + hashbrown-like topping is the closest match to this item's actual description (beef patty, fried chicken fillet, hashbrown, cheese) | Medium |
| `dsc-5773.jpg` | `spicy-wings` "Spicy Fried Wings" | Sauced/glazed wings fit "spicy" better than the peri (grilled, not fried-and-glazed) items | Medium |
| `menuitem-2.jpg` | Wraps category fallback (replaces current `wraps.webp`) | Clean generic wrap shot | Medium |
| `menuitem-4.jpg` | `w-hot-chick` "The Hot Chick Wrap" | Second angle of the same wrap shoot, needs its own item rather than duplicating menuitem-2's category-fallback role | Low — reconsider |
| `menuitem-5.jpg` | `b-quarter-cheese` "¼ Cheese Burger" | Plain beef + cheese matches this item's actual description closely | Medium-High |
| `menuitem-7.jpg` | `b-chicken-fillet` "Chicken Fillet Burger" | Single plain chicken fillet burger — direct visual match to this item's description | High |
| `menuitem-1.jpg` | Not assigned — needs cropping into 3 separate sub-images first (chicken strips / nuggets / popcorn chicken) or skip entirely | Composite image, unusable as a single item photo without editing | — |
| `menuitem-6.jpg` | `fried-combo` "Combo Fried Chicken with 2 Wings" | Generic fried-chicken-plus-fries combo shot | Low-Medium |
| `menuitem-8.jpg` | `fried-chicken` "Fried Chicken" (main item) | Generic fried chicken combo shot; fake box branding is prominent though — check it doesn't read oddly up close | Low |
| `menuitem-9.jpg` | `b-fillet-tower` "Chick Shack Fillet Tower Burger" | Leftover generic burger+fries combo slot; weak match, reconsider | Low |
| `menuitem-11.jpg` | `k-popcorn` "Popcorn Chicken" (Kids) | Direct match — this literally IS popcorn chicken | High |
| `menuitem-12.jpg` | `k-nuggets` "Nuggets" (Kids) | Direct match — this literally IS nuggets, but fix the white background first | High (pending bg fix) |
| `menuitem-3.jpg` | `peri-breast-2` "2 Boneless Breast" | Chicken-over-rice-and-salad loosely resembles a peri-grilled "with Rice" variant; boneless-looking pieces fit "Boneless Breast" better than an on-the-bone item | Low — reconsider, or leave unassigned |

## Technical integration plan (not yet executed)

1. For each assigned image: center-crop to match target aspect, then scale — **thumb is
   240×180 (4:3)**, **hero is 720×480 (3:2)** — these are DIFFERENT aspect ratios, crop each
   size separately, don't scale one from the other.
   `ffmpeg -i in.jpg -vf "scale=W:H:force_original_aspect_ratio=increase,crop=W:H" out.webp`
   (confirmed installed: ffmpeg with `libwebp` at `C:\ffmpeg-8.0.1-essentials_build\...\bin`)
2. Add a new basename per assigned image to the `ImageName` union in `storefront/src/types.ts`.
3. Drop files at `storefront/public/img/thumb/<name>.webp` and `storefront/public/img/hero/<name>.webp`.
4. Wire in via `menu.ts` — either a `CATEGORIES[].image` override or a per-item `image` field,
   matching the existing convention already used for every current stock photo.
5. `npx tsc --noEmit` in `storefront/`, then `cd storefront && npm run deploy` (Cloudflare —
   remember this is a SEPARATE deploy from `git push`, see `docs/DEPLOYMENT_PLAYBOOK.md`).
6. Verify the LIVE bundle, not the deploy log — fetch `chickshackg84.com`, extract the hashed
   JS asset URL, confirm the new image basenames appear in it, and spot-check the actual
   `/img/thumb/*.webp` and `/img/hero/*.webp` URLs return 200 with the right content.
