import React from "react";
import { BookOpen, Sparkles } from "lucide-react";

export default function BrandMark({ compact = false }) {
  return (
    <div className="flex items-center gap-3">
      <div className="relative grid h-11 w-11 place-items-center rounded-2xl bg-gradient-to-br from-ember-500 to-ember-700 shadow-ember">
        <BookOpen className="h-6 w-6 text-white" />
        <Sparkles className="absolute -right-1 -top-1 h-3.5 w-3.5 text-white" />
      </div>
      {!compact && (
        <div className="leading-tight">
          <p className="text-base font-extrabold tracking-tight text-white">Study Guide</p>
          <p className="text-sm font-bold text-ember-500">Generator</p>
        </div>
      )}
    </div>
  );
}
