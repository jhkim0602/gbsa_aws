import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

export type ProductTourSlide = Readonly<{
  label: string;
  src: string;
  alt: string;
}>;

export function ProductTourGallery({
  slides,
  interval = 3600,
  ariaLabel = "채용 설정 화면 갤러리",
  inset = false,
}: {
  slides: readonly ProductTourSlide[];
  interval?: number;
  ariaLabel?: string;
  inset?: boolean;
}) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const activeSlide = slides[activeIndex];

  useEffect(() => {
    if (slides.length < 2 || paused) return;

    const timer = window.setInterval(() => {
      setActiveIndex((current) => (current + 1) % slides.length);
    }, interval);

    return () => window.clearInterval(timer);
  }, [interval, paused, slides.length]);

  function move(step: number) {
    setActiveIndex(
      (current) => (current + step + slides.length) % slides.length,
    );
  }

  return (
    <div
      className={`relative aspect-[1.6/1] overflow-hidden bg-[radial-gradient(circle_at_50%_46%,rgb(126_145_255/18%),transparent_42%),linear-gradient(145deg,#f8faff,#eef3ff)] ${
        inset ? "p-3 sm:p-4" : ""
      }`}
      role="region"
      aria-roledescription="carousel"
      aria-label={ariaLabel}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget))
          setPaused(false);
      }}
    >
      <p className="sr-only" aria-live="polite">
        {activeSlide.label} 화면
      </p>
      <img
        className={`h-full w-full object-contain object-center [animation:landing-screen-in_.78s_cubic-bezier(.22,.75,.2,1)] motion-reduce:animate-none ${
          inset
            ? "rounded-[10px] border border-white/80 bg-white shadow-[0_16px_38px_rgb(37_55_105/12%)]"
            : ""
        }`}
        key={activeSlide.src}
        src={activeSlide.src}
        alt={activeSlide.alt}
        width="1440"
        height="900"
        loading="lazy"
        decoding="async"
      />
      <button
        className="absolute top-1/2 left-4 z-[2] grid size-10 -translate-y-1/2 place-items-center rounded-full border border-[#dce2ef] bg-white/92 text-[#315dff] shadow-[0_12px_30px_rgb(24_39_88/16%)] backdrop-blur transition hover:-translate-x-0.5 hover:border-[#315dff] max-sm:left-2 max-sm:size-9"
        type="button"
        aria-label={`이전 ${ariaLabel}`}
        onClick={() => move(-1)}
      >
        <ChevronLeft size={18} aria-hidden="true" />
      </button>
      <button
        className="absolute top-1/2 right-4 z-[2] grid size-10 -translate-y-1/2 place-items-center rounded-full border border-[#dce2ef] bg-white/92 text-[#315dff] shadow-[0_12px_30px_rgb(24_39_88/16%)] backdrop-blur transition hover:translate-x-0.5 hover:border-[#315dff] max-sm:right-2 max-sm:size-9"
        type="button"
        aria-label={`다음 ${ariaLabel}`}
        onClick={() => move(1)}
      >
        <ChevronRight size={18} aria-hidden="true" />
      </button>
    </div>
  );
}
