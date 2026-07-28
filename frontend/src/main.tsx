import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { rememberTenantFromUrl } from "./lib/tenant";
import "./index.css";

// Capture ?shop=<slug> before the router has a chance to drop it. A shop
// bookmarks /online-orders?shop=chick-shack; reopening the tablet redirects
// through the login page, and without this the slug would be lost exactly when
// the login needs it.
rememberTenantFromUrl();

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element not found. Ensure index.html contains <div id='root'></div>");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>
);
