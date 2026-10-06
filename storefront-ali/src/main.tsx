import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { captureClickId } from "./lib/clickId";
import "./index.css";

// F34. Before the first render, and outside the component tree so StrictMode's
// deliberate double-invoke cannot run it twice. The click id has to be taken
// off the URL while it is still there: a card payer leaves the domain for
// Stripe and returns to a fixed success_url with the parameter gone, and
// `stripReturnParams` rewrites the query string on the way back.
//
// Never throws, and nothing below depends on it. A visitor who did not come
// from an ad is unaffected.
captureClickId();

const root = document.getElementById("root");
if (!root) throw new Error("#root missing from index.html");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
