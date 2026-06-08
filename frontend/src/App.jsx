import React from "react";
import DesktopDashboard from "./components/DesktopDashboard";

// The reskin shell is a flat, full-viewport grid (#0B0B0C, no glow). The page
// background and base typography now come from design-system.css, so App just
// mounts the shell — GlowBackground is intentionally no longer rendered.
export default function App() {
  return <DesktopDashboard />;
}
