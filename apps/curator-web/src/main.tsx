import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { createAppRouter } from "./app/router";
import { RootApplication } from "./app/RootApplication";
import "./styles.css";

const rootElement = document.getElementById("root");
if (rootElement === null) {
  throw new Error("Curator Web root element is missing");
}

createRoot(rootElement).render(
  <StrictMode>
    <RootApplication environment={import.meta.env} router={createAppRouter()} />
  </StrictMode>,
);
