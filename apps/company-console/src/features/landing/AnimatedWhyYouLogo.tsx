const LOGO_SOURCE = "/brand-motion/logo.svg";

const logoPartClass =
  "absolute inset-0 size-full object-contain will-change-[transform,opacity,clip-path] motion-reduce:!animate-none motion-reduce:!opacity-100 motion-reduce:!transform-none";

export function AnimatedWhyYouLogo() {
  return (
    <div
      className="relative aspect-[1364/533] w-full"
      role="img"
      aria-label="WhyYou"
    >
      <img
        className={`${logoPartClass} [animation:landing-logo-dark_4200ms_both_infinite] [clip-path:inset(0_54%_0_0)]`}
        src={LOGO_SOURCE}
        alt=""
        width="1364"
        height="533"
      />
      <img
        className={`${logoPartClass} [animation:landing-logo-question_4200ms_both_infinite] [clip-path:polygon(43%_0,62%_0,62%_72%,43%_72%)]`}
        src={LOGO_SOURCE}
        alt=""
        width="1364"
        height="533"
      />
      <img
        className={`${logoPartClass} [animation:landing-logo-dot_4200ms_both_infinite] [clip-path:polygon(43%_66%,62%_66%,62%_100%,43%_100%)]`}
        src={LOGO_SOURCE}
        alt=""
        width="1364"
        height="533"
      />
      <img
        className={`${logoPartClass} [animation:landing-logo-you_4200ms_55ms_both_infinite] [clip-path:inset(0_0_0_60%)]`}
        src={LOGO_SOURCE}
        alt=""
        width="1364"
        height="533"
      />
    </div>
  );
}
