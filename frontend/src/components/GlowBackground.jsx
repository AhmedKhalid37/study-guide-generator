import React from "react";

export default function GlowBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden">
      <div className="absolute -top-36 left-[18%] h-96 w-96 rounded-full bg-blue-600/20 blur-3xl" />
      <div className="absolute right-[8%] top-[20%] h-[28rem] w-[28rem] rounded-full bg-ember-500/10 blur-3xl" />
      <div className="absolute bottom-[-8rem] left-[34%] h-96 w-96 rounded-full bg-cyan-500/10 blur-3xl" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,rgba(255,255,255,0.1)_1px,transparent_0)] [background-size:30px_30px] opacity-[0.12]" />
    </div>
  );
}
