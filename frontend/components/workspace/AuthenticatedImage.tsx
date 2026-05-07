"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function AuthenticatedImage({
  artifactId,
  alt,
  className,
}: {
  artifactId: string;
  alt: string;
  className?: string;
}) {
  const [src, setSrc] = useState("");

  useEffect(() => {
    let active = true;
    let objectUrl = "";

    (async () => {
      try {
        const resp = await api.fetchArtifactPreview(artifactId);
        if (!resp.ok) return;
        const blob = await resp.blob();
        objectUrl = URL.createObjectURL(blob);
        if (active) setSrc(objectUrl);
      } catch {
        if (active) setSrc("");
      }
    })();

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [artifactId]);

  if (!src) return <span className="muted">Загрузка превью...</span>;
  return <img className={className} src={src} alt={alt} />;
}

