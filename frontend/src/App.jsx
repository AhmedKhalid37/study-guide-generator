import React from "react";
import GlowBackground from "./components/GlowBackground";
import DesktopDashboard from "./components/DesktopDashboard";

export default function App() {
  return (
    <div className="min-h-screen bg-navy-950 font-sans text-white">
      <GlowBackground />
      <main className="relative z-10 px-3 py-4 sm:px-5 lg:px-7 lg:py-7">
        <DesktopDashboard />
      </main>
    </div>
  );
}
