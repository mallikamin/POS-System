import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { hasPersistedSession, rememberTenantFromUrl } from "./lib/tenant";
import "./index.css";

// Capture ?shop=<slug> before the router has a chance to drop it. A shop
// bookmarks /online-orders?shop=chick-shack; reopening the tablet redirects
// through the login page, and without this the slug would be lost exactly when
// the login needs it.
//
// 🔴 Only when nobody is signed in. Persisting it unconditionally let any URL
// silently repoint an authenticated device at another restaurant, with no
// authentication involved -- see `rememberTenantFromUrl`. The session is read
// straight out of the persisted auth store rather than through the React tree,
// because this has to run before the first render, which is the entire reason
// the call is here and not in a component.
rememberTenantFromUrl(hasPersistedSession());

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element not found. Ensure index.html contains <div id='root'></div>");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>
);
