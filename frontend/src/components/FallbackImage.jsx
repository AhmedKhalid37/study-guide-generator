import React, { useState } from "react";
import { BookOpen, Monitor } from "lucide-react";

export default function FallbackImage({
  src,
  alt,
  className = "",
  fallbackType = "mobile",
  title,
  loading = "lazy"
}) {
  const [hasError, setHasError] = useState(false);

  if (!hasError) {
    return (
      <img
        src={src}
        alt={alt}
        loading={loading}
        className={className}
        draggable="false"
        onError={() => setHasError(true)}
      />
    );
  }

  const Icon = fallbackType === "desktop" ? Monitor : BookOpen;
  const aspectClass = fallbackType === "desktop" ? "aspect-video" : "aspect-[390/820] rounded-[1.95rem]";

  return (
    <div className={`${aspectClass} grid w-full place-items-center bg-gradient-to-br from-navy-850 via-navy-800 to-navy-950 p-8 text-center`}>
      <div>
        <Icon className="mx-auto h-14 w-14 text-ember-500" />
        <p className="mt-5 text-xl font-extrabold text-white">{title}</p>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          Image asset missing. Make sure the PNG exists inside <code className="text-ember-500">public/mockups</code>.
        </p>
      </div>
    </div>
  );
}
