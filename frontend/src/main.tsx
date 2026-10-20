import React from "react";
import ReactDOM from "react-dom/client";
import AuthGate from "./components/AuthGate";
import "./style.css";\nimport { registerPwa } from "./services/pwa";
registerPwa();\n\nReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthGate />
  </React.StrictMode>,
);
