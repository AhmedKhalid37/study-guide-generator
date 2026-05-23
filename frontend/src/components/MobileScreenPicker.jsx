export default function MobileScreenPicker({ screens, activeScreenId, setActiveScreenId }) {
  return (
    <div className="mx-auto mb-8 flex max-w-3xl flex-wrap justify-center gap-2">
      {screens.map((screen) => (
        <button
          key={screen.id}
          onClick={() => setActiveScreenId(screen.id)}
          className={`rounded-full border px-4 py-2 text-sm font-bold transition ${
            activeScreenId === screen.id
              ? "border-ember-500 bg-ember-500 text-white shadow-ember"
              : "border-white/10 bg-white/[0.04] text-slate-400 hover:text-white"
          }`}
        >
          {screen.label}
        </button>
      ))}
    </div>
  );
}
