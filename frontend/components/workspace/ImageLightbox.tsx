"use client";

export function ImageLightbox({
  src,
  alt,
  open,
  onClose,
}: {
  src: string;
  alt?: string;
  open: boolean;
  onClose: () => void;
}) {
  if (!open || !src) return null;
  return (
    <div className="image-lightbox" onClick={onClose} role="button" tabIndex={0}>
      <button
        type="button"
        className="lightbox-close"
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
      >
        Закрыть
      </button>
      <img
        src={src}
        alt={alt || "preview"}
        className="lightbox-image"
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  );
}

