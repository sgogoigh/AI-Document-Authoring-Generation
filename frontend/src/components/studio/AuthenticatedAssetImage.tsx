"use client";

import { ImageIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";

export function AuthenticatedAssetImage({
  assetId,
  caption,
}: {
  assetId: string;
  caption: string;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let revoked = false;
    let objectUrl: string | null = null;
    setFailed(false);

    api
      .fetchAssetBlobUrl(assetId)
      .then((url) => {
        if (revoked) {
          URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        setSrc(url);
      })
      .catch(() => {
        if (!revoked) setFailed(true);
      });

    return () => {
      revoked = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [assetId]);

  if (failed) {
    return (
      <div className="flex h-44 items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 text-xs text-slate-500">
        <ImageIcon className="mr-2 h-4 w-4" />
        Preview unavailable
      </div>
    );
  }

  if (!src) {
    return <div className="h-48 w-full animate-pulse rounded-xl bg-slate-100" />;
  }

  return (
    <figure className="overflow-hidden rounded-xl border border-slate-200 bg-slate-50 p-2">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={caption || "Generated visual"}
        className="mx-auto max-h-72 w-auto rounded-lg object-contain"
      />
      {caption && (
        <figcaption className="mt-2 text-center text-xs italic text-slate-500">{caption}</figcaption>
      )}
    </figure>
  );
}
