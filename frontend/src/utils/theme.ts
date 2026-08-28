/**
 * Tenant theming.
 *
 * A tenant may carry a `theme` in its restaurant config. When it does, the
 * matching palette in `index.css` is switched on by stamping an attribute on
 * the root element; every colour in the app is a CSS variable, so nothing else
 * has to know about themes.
 *
 * A tenant with no theme (the default, and the case for every existing tenant)
 * has NO attribute stamped, resolves the `:root` defaults, and is pixel-for-
 * pixel what it was before theming existed. That is the invariant: adding a
 * theme for one restaurant must never touch another one.
 */

/** Themes that actually have a palette in `index.css`. */
const KNOWN_THEMES = new Set(["desert-salt"]);

/**
 * Web fonts a theme needs. Loaded on demand, so a tenant that is not themed
 * never pays for a font it does not use.
 */
const THEME_FONTS: Record<string, string> = {
  "desert-salt":
    "https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Public+Sans:wght@400;500;600;700&display=swap",
};

const FONT_LINK_ID = "tenant-theme-font";

function loadThemeFont(theme: string): void {
  const href = THEME_FONTS[theme];
  if (!href) return;
  const existing = document.getElementById(FONT_LINK_ID);
  if (existing instanceof HTMLLinkElement) {
    if (existing.href !== href) existing.href = href;
    return;
  }
  const link = document.createElement("link");
  link.id = FONT_LINK_ID;
  link.rel = "stylesheet";
  link.href = href;
  document.head.appendChild(link);
}

/**
 * Apply (or clear) the tenant theme.
 *
 * An unknown or missing theme clears the attribute rather than guessing, so a
 * typo in a tenant's config degrades to the standard look instead of a
 * half-styled screen.
 */
export function setActiveTheme(theme?: string | null): void {
  const root = document.documentElement;
  const name = (theme ?? "").trim().toLowerCase();

  if (!name || !KNOWN_THEMES.has(name)) {
    delete root.dataset.tenantTheme;
    return;
  }

  root.dataset.tenantTheme = name;
  loadThemeFont(name);
}

/** The theme currently applied, or null. Exported for tests. */
export function getActiveTheme(): string | null {
  return document.documentElement.dataset.tenantTheme ?? null;
}
