import { Monitor, Smartphone, Layers3 } from "lucide-react";
import BrandMark from "./BrandMark";

const viewOptions = [
  { id: "mobile", label: "Mobile", icon: Smartphone },
  { id: "desktop", label: "Desktop", icon: Monitor },
  { id: "all", label: "All screens", icon: Layers3 }
];

export default function TopBar({ view, setView }) {
  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-navy-950/75 px-4 py-4 backdrop-blur-2xl sm:px-6">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <BrandMark />
        <div className="flex w-full rounded-2xl border border-white/10 bg-white/[0.04] p-1 sm:w-auto">
          {viewOptions.map((option) => {
            const Icon = option.icon;
            return (
              <button
                key={option.id}
                onClick={() => setView(option.id)}
                className={`flex flex-1 items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold transition sm:flex-none ${
                  view === option.id
                    ? "bg-gradient-to-r from-ember-500 to-ember-700 text-white shadow-ember"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <Icon className="h-4 w-4" />
                {option.label}
              </button>
            );
          })}
        </div>
      </div>
    </header>
  );
}
