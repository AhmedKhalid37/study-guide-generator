import { motion } from "framer-motion";
import { desktopMockup } from "../data/mockups";
import FallbackImage from "./FallbackImage";

export default function DesktopMockup() {
  return (
    <motion.figure
      initial={{ opacity: 0, y: 18, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="mx-auto w-full max-w-[1536px]"
    >
      <div className="overflow-hidden rounded-[1.75rem] border border-white/15 bg-black/50 shadow-navy">
        <FallbackImage
          src={desktopMockup.image}
          alt={desktopMockup.title}
          title={desktopMockup.title}
          className="block w-full select-none"
          fallbackType="desktop"
        />
      </div>
      <figcaption className="mx-auto mt-5 max-w-3xl rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-center backdrop-blur-xl">
        <p className="font-bold text-white">{desktopMockup.title}</p>
        <p className="mt-1 text-sm leading-6 text-slate-400">{desktopMockup.notes}</p>
      </figcaption>
    </motion.figure>
  );
}
