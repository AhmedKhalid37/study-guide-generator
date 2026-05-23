import { Info } from "lucide-react";

export default function ImplementationNote() {
  return (
    <section className="mx-auto mt-10 max-w-5xl rounded-3xl border border-ember-500/20 bg-ember-500/10 p-5 text-sm leading-7 text-orange-100 shadow-ember backdrop-blur-xl">
      <div className="flex gap-3">
        <Info className="mt-1 h-5 w-5 shrink-0 text-ember-500" />
        <div>
          <p className="font-extrabold text-white">Option A visual-match setup</p>
          <p className="mt-1 text-orange-100/85">
            This version uses the generated mockup screens as high-fidelity visual assets, which gives you the closest possible match to the images. The shell, navigation, screen switching, responsive layout, and project structure are coded in React + Tailwind. When you are ready to make each button/input fully functional, replace each image-backed screen with live components one section at a time while keeping these same dimensions, colors, and assets as the design reference.
          </p>
        </div>
      </div>
    </section>
  );
}
