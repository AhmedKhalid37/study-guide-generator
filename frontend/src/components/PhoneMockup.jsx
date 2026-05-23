import { motion } from "framer-motion";
import FallbackImage from "./FallbackImage";

export default function PhoneMockup({ screen, priority = false }) {
  return (
    <motion.figure
      initial={{ opacity: 0, y: 16, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
      className="mx-auto w-full max-w-[406px]"
    >
      <div className="rounded-[2.25rem] border border-white/15 bg-black/40 p-1.5 shadow-navy">
        <FallbackImage
          src={screen.image}
          alt={screen.title}
          title={screen.title}
          loading={priority ? "eager" : "lazy"}
          className="block w-full rounded-[1.95rem] select-none"
          fallbackType="mobile"
        />
      </div>
      <figcaption className="mt-4 rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-center backdrop-blur-xl">
        <p className="font-bold text-white">{screen.title}</p>
        <p className="mt-1 text-sm leading-6 text-slate-400">{screen.notes}</p>
      </figcaption>
    </motion.figure>
  );
}
