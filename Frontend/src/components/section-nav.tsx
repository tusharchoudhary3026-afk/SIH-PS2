import { useCallback, useEffect, useLayoutEffect, useRef, useState, type MouseEvent } from "react";
import { motion, useMotionValue, useReducedMotion, useSpring } from "framer-motion";

const sections = [
  { id: "dashboard", label: "Overview" },
  { id: "sonar-analysis", label: "Sonar Analysis" },
  { id: "detections", label: "Detections" },
  { id: "detection-map", label: "Map" },
  { id: "survey-comparison", label: "Comparison" },
  { id: "analytics", label: "Analytics" },
  { id: "reports", label: "Reports" },
  { id: "settings", label: "Settings" },
] as const;
const initialSections = sections.slice(0, 2);

export default function SectionNav({ analysisAvailable = true }: { analysisAvailable?: boolean }) {
  const visibleSections = analysisAvailable ? sections : initialSections;
  const [activeSection, setActiveSection] = useState<string>(sections[0].id);
  const [isScrolled, setIsScrolled] = useState(false);
  const [cursorReady, setCursorReady] = useState(false);
  const navRef = useRef<HTMLElement>(null);
  const tabRefs = useRef(new Map<string, HTMLAnchorElement>());
  const cursorInitializedRef = useRef(false);
  const isClickScrollingRef = useRef(false);
  const clickUnlockRef = useRef<number | undefined>(undefined);
  const cursorX = useMotionValue(0);
  const cursorWidth = useMotionValue(0);
  const reduceMotion = useReducedMotion();
  const spring = { stiffness: reduceMotion ? 10000 : 450, damping: reduceMotion ? 1000 : 32 };
  const springX = useSpring(cursorX, spring);
  const springWidth = useSpring(cursorWidth, spring);

  const updateScrollState = useCallback(() => {
    setIsScrolled(window.scrollY > 20);
    if (isClickScrollingRef.current) return;

    const lastSection = visibleSections.at(-1);
    if (lastSection && window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 3) {
      setActiveSection(lastSection.id);
      return;
    }

    const line = window.scrollY + (navRef.current?.getBoundingClientRect().height ?? 62) + 28;
    let current: string = sections[0].id;
    for (const { id } of visibleSections) {
      const element = document.getElementById(id);
      if (element && element.getBoundingClientRect().top + window.scrollY <= line) current = id;
    }
    setActiveSection(current);
  }, [visibleSections]);

  const unlockClickScroll = useCallback(() => {
    if (!isClickScrollingRef.current) return;
    isClickScrollingRef.current = false;
    if (clickUnlockRef.current !== undefined) window.clearTimeout(clickUnlockRef.current);
    clickUnlockRef.current = undefined;
    updateScrollState();
  }, [updateScrollState]);

  useEffect(() => {
    let frame = 0;
    const onScroll = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        frame = 0;
        updateScrollState();
      });
    };
    const onManualScroll = () => unlockClickScroll();
    updateScrollState();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    window.addEventListener("wheel", onManualScroll, { passive: true });
    window.addEventListener("touchstart", onManualScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      window.removeEventListener("wheel", onManualScroll);
      window.removeEventListener("touchstart", onManualScroll);
      if (frame) window.cancelAnimationFrame(frame);
      if (clickUnlockRef.current !== undefined) window.clearTimeout(clickUnlockRef.current);
    };
  }, [unlockClickScroll, updateScrollState]);

  // Keep the sliding indicator tied to the current section, never to pointer hover.
  const cursorTarget = activeSection;
  useLayoutEffect(() => {
    const moveCursor = () => {
      const nav = navRef.current;
      const tab = tabRefs.current.get(cursorTarget);
      if (!nav || !tab) return;
      const x = tab.offsetLeft;
      const width = tab.offsetWidth;
      cursorX.set(x);
      cursorWidth.set(width);
      if (!cursorInitializedRef.current) {
        springX.jump(x);
        springWidth.jump(width);
        cursorInitializedRef.current = true;
      }
      setCursorReady(true);
    };
    moveCursor();
    const observer = typeof ResizeObserver === "undefined" ? undefined : new ResizeObserver(moveCursor);
    if (navRef.current) observer?.observe(navRef.current);
    tabRefs.current.forEach((tab) => observer?.observe(tab));
    window.addEventListener("resize", moveCursor);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", moveCursor);
    };
  }, [cursorTarget, cursorX, cursorWidth, springX, springWidth]);

  const navigateTo = (event: MouseEvent<HTMLAnchorElement>, id: string) => {
    event.preventDefault();
    const target = document.getElementById(id);
    if (!target) return;

    isClickScrollingRef.current = true;
    setActiveSection(id);
    if (clickUnlockRef.current !== undefined) window.clearTimeout(clickUnlockRef.current);
    clickUnlockRef.current = window.setTimeout(() => {
      isClickScrollingRef.current = false;
      clickUnlockRef.current = undefined;
      updateScrollState();
    }, 1000);
    window.history.replaceState(null, "", `#${id}`);
    target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  };

  return <header className={`section-nav-wrap${isScrolled ? " is-scrolled" : ""}`}>
    <a className="section-nav-brand" href="#dashboard" onClick={(event) => navigateTo(event, "dashboard")} aria-label="SEVORA mission overview">
      <img className="section-nav-logo-image" src="/sevora-logo.jpg" alt="SEVORA — underwater sonar intelligence" />
    </a>
    <div className="section-nav-clip">
      <nav ref={navRef} className="section-nav" aria-label="Page sections">
        {cursorReady && <motion.span aria-hidden="true" className="section-nav-cursor" style={{ x: springX, width: springWidth }} />}
        {visibleSections.map(({ id, label }) => <a
          key={id}
          ref={(element) => { if (element) tabRefs.current.set(id, element); else tabRefs.current.delete(id); }}
          href={`#${id}`}
          aria-current={activeSection === id ? "location" : undefined}
          className={activeSection === id ? "is-active" : undefined}
          onClick={(event) => navigateTo(event, id)}
        >{label}</a>)}
      </nav>
    </div>
  </header>;
}
