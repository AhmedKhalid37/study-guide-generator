import { useMemo, useState } from "react";
import GlowBackground from "./components/GlowBackground";
import TopBar from "./components/TopBar";
import PhoneMockup from "./components/PhoneMockup";
import DesktopMockup from "./components/DesktopMockup";
import MobileScreenPicker from "./components/MobileScreenPicker";
import ImplementationNote from "./components/ImplementationNote";
import RecentJobsPanel from "./components/RecentJobsPanel";
import { mobileScreens } from "./data/mockups";

export default function App() {
  const [view, setView] = useState("mobile");
  const [activeScreenId, setActiveScreenId] = useState("home");

  const activeScreen = useMemo(
    () => mobileScreens.find((screen) => screen.id === activeScreenId) ?? mobileScreens[0],
    [activeScreenId]
  );

  return (
    <div className="min-h-screen bg-navy-950 font-sans text-white">
      <GlowBackground />
      <TopBar view={view} setView={setView} />

      <main className="relative z-10 px-4 py-8 sm:px-6 lg:py-10">
        {view === "mobile" && (
          <section>
            <MobileScreenPicker
              screens={mobileScreens}
              activeScreenId={activeScreenId}
              setActiveScreenId={setActiveScreenId}
            />
            <PhoneMockup screen={activeScreen} priority />
            <ImplementationNote />
          </section>
        )}

        {view === "desktop" && (
          <section>
            <DesktopMockup />
            <RecentJobsPanel />
            <ImplementationNote />
          </section>
        )}

        {view === "all" && (
          <section className="mx-auto max-w-[1800px]">
            <div className="grid gap-8 xl:grid-cols-4">
              {mobileScreens.map((screen, index) => (
                <PhoneMockup key={screen.id} screen={screen} priority={index === 0} />
              ))}
            </div>
            <div className="mt-12">
              <DesktopMockup />
            </div>
            <RecentJobsPanel />
            <ImplementationNote />
          </section>
        )}
      </main>
    </div>
  );
}
