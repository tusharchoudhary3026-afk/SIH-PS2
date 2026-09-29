import { useEffect, useRef, useState } from "react";

const BALL_SIZE = 380;

type Metric = {
  label: string;
  value: string;
  tone: "default" | "warning" | "verified";
};

type SonarDashboardIntroProps = {
  title: string;
  description: string;
  metrics: ReadonlyArray<Metric>;
  actionLabel: string;
  dataStatus?: string;
};

export default function SonarDashboardIntro({
  title,
  description,
  metrics,
  actionLabel,
  dataStatus = "DEMO DATA",
}: SonarDashboardIntroProps) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const heroRef = useRef<HTMLElement>(null);
  const [scrollY, setScrollY] = useState(0);
  const [geometry, setGeometry] = useState({
    scrollHeight: 0,
    heroWidth: 0,
    heroHeight: 0,
  });
  const [reducedMotion, setReducedMotion] = useState(false);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updatePreference = () => setReducedMotion(media.matches);
    updatePreference();
    media.addEventListener("change", updatePreference);
    return () => media.removeEventListener("change", updatePreference);
  }, []);

  useEffect(() => {
    const viewportElement = viewportRef.current;
    const heroElement = heroRef.current;
    if (!viewportElement || !heroElement || reducedMotion) return;

    const measure = () => {
      const scrollHeight = window.innerHeight;
      const heroWidth = heroElement.clientWidth;
      const heroHeight = heroElement.clientHeight;
      if (scrollHeight > 0 && heroWidth > 0 && heroHeight > 0) {
        setGeometry({ scrollHeight, heroWidth, heroHeight });
      }
    };
    const sectionTop = viewportElement.getBoundingClientRect().top + window.scrollY;
    const updateScroll = () => setScrollY(Math.max(0, window.scrollY - sectionTop));

    measure();
    updateScroll();

    let observer: ResizeObserver | undefined;
    const hasResizeObserver = typeof ResizeObserver !== "undefined";
    if (hasResizeObserver) {
      observer = new ResizeObserver(measure);
      observer.observe(viewportElement);
      observer.observe(heroElement);
    } else {
      window.addEventListener("resize", measure);
    }
    window.addEventListener("scroll", updateScroll, { passive: true });

    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", measure);
      window.removeEventListener("scroll", updateScroll);
    };
  }, [reducedMotion]);

  useEffect(() => {
    const viewportElement = viewportRef.current;
    const resultElement = viewportElement?.querySelector<HTMLElement>(".sonar-result");
    if (!viewportElement || !resultElement) return;

    if (reducedMotion || !("IntersectionObserver" in window)) {
      setRevealed(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setRevealed(true);
      },
      { threshold: 0.1 },
    );
    observer.observe(resultElement);
    return () => observer.disconnect();
  }, [reducedMotion]);

  const hasGeometry = geometry.scrollHeight > 0 && geometry.heroWidth > 0 && geometry.heroHeight > 0;
  const staticFallback = reducedMotion || !hasGeometry;
  const scrollHeight = hasGeometry ? geometry.scrollHeight : 600;
  const heroHeight = hasGeometry ? geometry.heroHeight : 600;
  const heroWidth = hasGeometry ? geometry.heroWidth : 800;
  const phaseOne = clamp(scrollY / scrollHeight);
  const phaseTwo = clamp((scrollY - scrollHeight) / scrollHeight);
  const easedTravel =
    phaseOne < 0.5
      ? 8 * phaseOne ** 4
      : 1 - ((-2 * phaseOne + 2) ** 4) / 2;
  const easedExpansion = phaseTwo ** 2;
  const circleOffset = (1 - easedTravel) * (heroHeight / 2 + BALL_SIZE / 2);
  const circleSize =
    BALL_SIZE + easedExpansion * (Math.max(heroWidth, heroHeight) * 2.8 - BALL_SIZE);
  const circleX = heroWidth / 2;
  const circleY = heroHeight / 2 + circleOffset;

  return (
    <div
      ref={viewportRef}
      className={`sonar-scrollport${reducedMotion ? " is-reduced" : ""}${!hasGeometry && !reducedMotion ? " is-measuring" : ""}`}
    >
      <div className="sonar-track">
        <section ref={heroRef} className="sonar-hero" aria-label="Marine debris intelligence dashboard">
          {!staticFallback && (
            <div
              aria-hidden="true"
              className="sonar-orb"
              style={{
                width: circleSize,
                height: circleSize,
                transform: `translate(-50%, calc(-50% + ${circleOffset}px))`,
              }}
            />
          )}
          <div className="sonar-copy sonar-copy-base">
            <span className="eyebrow"><span className="status-dot" /> Ocean intelligence platform</span>
            <h1>{title}</h1>
            <p>{description}</p>
            <span className="hero-caption">SCAN <i /> DETECT <i /> CLASSIFY <i /> PRIORITIZE</span>
          </div>
          {!staticFallback && (
            <div
              aria-hidden="true"
              className="sonar-copy sonar-copy-inverse"
              style={{ clipPath: `circle(${circleSize / 2}px at ${circleX}px ${circleY}px)` }}
            >
              <span className="eyebrow"><span className="status-dot" /> Ocean intelligence platform</span>
              <h1>{title}</h1>
              <p>{description}</p>
              <span className="hero-caption">SCAN <i /> DETECT <i /> CLASSIFY <i /> PRIORITIZE</span>
            </div>
          )}
          {!reducedMotion && (
            <div className="scroll-cue" aria-hidden="true">
              <span /> Scroll to explore
            </div>
          )}
        </section>
      </div>

      <section className={`sonar-result${revealed || staticFallback ? " is-visible" : ""}`}>
        <div className="result-inner">
          <div className="result-heading">
            <div>
              <span className="eyebrow result-eyebrow">Mission overview <span className="live-indicator">{dataStatus}</span></span>
              <h2>From sonar data<br /><span>to actionable insight.</span></h2>
            </div>
            <p className="result-description">
              Surface priority debris, review scan quality, and move from a survey to a clearer picture of the seafloor.
            </p>
          </div>

          <div className="metrics-grid" aria-label="Demo survey statistics">
            {metrics.map((metric, index) => (
              <article className={`metric-card tone-${metric.tone}`} key={metric.label}>
                <div className="metric-topline">
                  <span className="metric-index">0{index + 1}</span>
                  <span className="metric-mark" aria-hidden="true" />
                </div>
                <p>{metric.label}</p>
                <strong>{metric.value}</strong>
              </article>
            ))}
          </div>

          <div className="workspace-row">
            <div className="workspace-copy">
              <span className="workspace-kicker">NEXT · SONAR ANALYSIS</span>
              <h3>Inspect a survey</h3>
              <p>Upload a side-scan sonar survey to review detections and acoustic evidence.</p>
            </div>
            <a className="primary-action" href="#sonar-analysis">
              {actionLabel}<span aria-hidden="true">↗</span>
            </a>
          </div>

          <div className="result-footer">
            <span>MARINE DEBRIS INTELLIGENCE</span>
            <span>DETECT WITH CLARITY <i /> PROTECT THE SEAFLOOR</span>
          </div>
        </div>
      </section>
    </div>
  );
}

const clamp = (value: number) => Math.min(1, Math.max(0, value));
