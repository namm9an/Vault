import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import Lenis from "lenis";
import { LandingNav } from "@/components/landing/LandingNav";

gsap.registerPlugin(ScrollTrigger);

// ---------------------------------------------------------------------------
// Hero Section
// ---------------------------------------------------------------------------

const heroWords = ["Control", "every", "rupee.", "Automatically."];

function HeroSection() {
  return (
    <section
      className="min-h-screen bg-[#f4f2f0] pt-[62px] flex flex-col items-center justify-center"
      style={{
        backgroundImage: "radial-gradient(circle, #d2cecb 1px, transparent 1px)",
        backgroundSize: "24px 24px",
      }}
    >
      <div className="max-w-4xl mx-auto px-8 flex flex-col items-center text-center">
        {/* Eyebrow */}
        <motion.p
          className="text-xs font-medium tracking-[0.15em] text-[#6e6a68] uppercase mb-6"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          AI-Native Corporate Spend Platform
        </motion.p>

        {/* H1 word-by-word */}
        <h1
          className="font-normal tracking-tight text-[#0c0a08] leading-[1.1]"
          style={{ fontSize: "clamp(48px, 8vw, 72px)" }}
        >
          {heroWords.map((word, i) => (
            <motion.span
              key={i}
              className="inline-block mr-3"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06, duration: 0.5, ease: "easeOut" }}
            >
              {word}
            </motion.span>
          ))}
        </h1>

        {/* Subheadline */}
        <motion.p
          className="text-xl text-[#6e6a68] mt-6 max-w-xl leading-relaxed"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.5 }}
        >
          Vault gives finance teams AI-powered cards, policy enforcement, and spend intelligence — all in one platform.
        </motion.p>

        {/* CTA row */}
        <motion.div
          className="mt-10 flex gap-4"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.55, duration: 0.5 }}
        >
          <Link
            to="/signup"
            className="bg-solar text-[#0c0a08] font-semibold px-6 py-3 rounded-[6px] hover:bg-solar-light transition-colors text-sm"
          >
            Get started free
          </Link>
          <Link
            to="/login"
            className="border border-[#d2cecb] text-[#0c0a08] font-medium px-6 py-3 rounded-[6px] hover:bg-white transition-colors text-sm"
          >
            Sign in
          </Link>
        </motion.div>

      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Metrics Ticker
// ---------------------------------------------------------------------------

const TICKER_ITEMS = [
  { label: "TRANSACTIONS PROCESSED", value: "12,847" },
  { label: "POLICIES ENFORCED", value: "3,291" },
  { label: "RECEIPTS REVIEWED", value: "8,104" },
  { label: "VIOLATIONS CAUGHT", value: "247" },
  { label: "AI ACTIONS TODAY", value: "1,476" },
];

function MetricsTicker() {
  const tickerRef = useRef<HTMLDivElement>(null);
  const ctxRef = useRef<gsap.Context | null>(null);

  useEffect(() => {
    if (!tickerRef.current) return;
    ctxRef.current = gsap.context(() => {
      gsap.to(tickerRef.current, {
        x: "-50%",
        duration: 20,
        ease: "none",
        repeat: -1,
      });
    });
    return () => ctxRef.current?.revert();
  }, []);

  const items = [...TICKER_ITEMS, ...TICKER_ITEMS];

  return (
    <div className="bg-[#1a1919] h-12 overflow-hidden flex items-center">
      <div ref={tickerRef} className="flex gap-16 items-center whitespace-nowrap">
        {items.map((item, i) => (
          <span key={i} className="flex items-center gap-2">
            <span className="text-white/30 text-sm">·</span>
            <span className="text-white/60 text-xs tracking-wider uppercase">{item.label}</span>
            <span className="text-solar font-mono text-sm font-semibold">{item.value}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Feature Section (reusable)
// ---------------------------------------------------------------------------

type FeatureSectionProps = {
  label: string;
  heading: React.ReactNode;
  body: string;
  visual: React.ReactNode;
  visualRight?: boolean;
};

function FeatureSection({ label, heading, body, visual, visualRight = true }: FeatureSectionProps) {
  const sectionRef = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    gsap.from(".feature-text > *", {
      scrollTrigger: {
        trigger: sectionRef.current,
        start: "top 75%",
        once: true,
      },
      y: 40,
      opacity: 0,
      stagger: 0.12,
      duration: 0.7,
      ease: "power3.out",
    });
    gsap.from(".feature-visual", {
      scrollTrigger: {
        trigger: sectionRef.current,
        start: "top 75%",
        once: true,
      },
      x: visualRight ? 40 : -40,
      opacity: 0,
      duration: 0.8,
      ease: "power3.out",
      delay: 0.2,
    });
  }, { scope: sectionRef, dependencies: [visualRight] });

  const textEl = (
    <div className="feature-text flex flex-col justify-center">
      <p className="text-[10px] font-semibold text-[#6e6a68] uppercase tracking-[0.15em] mb-4">
        {label}
      </p>
      <h2 className="text-4xl font-semibold tracking-tight leading-tight text-[#0c0a08] mb-4">
        {heading}
      </h2>
      <p className="text-base text-[#6e6a68] leading-relaxed max-w-md">{body}</p>
    </div>
  );

  const visualEl = (
    <div className="feature-visual">{visual}</div>
  );

  return (
    <div ref={sectionRef} className="py-32 px-8">
      <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-16 items-center">
        {visualRight ? (
          <>
            {textEl}
            {visualEl}
          </>
        ) : (
          <>
            {visualEl}
            {textEl}
          </>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Feature visuals (mock cards)
// ---------------------------------------------------------------------------

function CardsMockup() {
  return (
    <div className="bg-white rounded-2xl border border-[#d2cecb] shadow-lg p-5">
      <p className="text-xs font-semibold text-[#6e6a68] uppercase tracking-wide mb-3">
        Recent Transaction
      </p>
      <div className="flex items-center justify-between py-3 border-b border-[#d2cecb]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#f4f2f0] flex items-center justify-center text-sm">
            ☁️
          </div>
          <div>
            <p className="text-sm font-semibold text-[#0c0a08]">Amazon Web Services</p>
            <p className="text-xs text-[#6e6a68]">SAAS · May 28, 2026</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm font-semibold font-mono text-[#0c0a08]">₹12,400</p>
          <span className="inline-flex items-center gap-1 bg-emerald-100 text-emerald-800 text-xs font-medium px-2 py-0.5 rounded-full border border-emerald-200">
            Receipt Attached
          </span>
        </div>
      </div>
      <div className="flex items-center justify-between py-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#f4f2f0] flex items-center justify-center text-sm">
            ✈️
          </div>
          <div>
            <p className="text-sm font-semibold text-[#0c0a08]">IndiGo Airlines</p>
            <p className="text-xs text-[#6e6a68]">TRAVEL · May 27, 2026</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm font-semibold font-mono text-[#0c0a08]">₹8,900</p>
          <span className="inline-flex items-center gap-1 bg-amber-100 text-amber-800 text-xs font-medium px-2 py-0.5 rounded-full border border-amber-200">
            Pending Review
          </span>
        </div>
      </div>
    </div>
  );
}

function PolicyMockup() {
  return (
    <div className="bg-white rounded-2xl border border-[#d2cecb] shadow-lg p-5">
      <p className="text-xs font-semibold text-[#6e6a68] uppercase tracking-wide mb-3">
        Policy Evaluation
      </p>
      <div className="bg-[#f4f2f0] rounded-xl border border-[#d2cecb] p-4 mb-4">
        <p className="text-xs text-[#6e6a68] mb-1">Policy rule</p>
        <p className="text-sm text-[#0c0a08] leading-relaxed">
          No single transaction may exceed ₹50,000 without Finance Manager approval.
        </p>
      </div>
      <div className="flex items-start gap-3">
        <div className="flex-1">
          <p className="text-xs text-[#6e6a68] mb-1">AI Verdict</p>
          <p className="text-sm text-[#0c0a08]">Transaction exceeds ₹50,000 threshold. Escalation required before clearing.</p>
        </div>
        <span className="inline-flex items-center bg-orange-100 text-orange-800 text-xs font-semibold px-2 py-1 rounded-full border border-orange-200 whitespace-nowrap">
          FLAGGED
        </span>
      </div>
    </div>
  );
}

function DigestMockup() {
  return (
    <div className="bg-white rounded-2xl border border-[#d2cecb] shadow-lg p-5">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-[#6e6a68] uppercase tracking-wide">
          Weekly Digest · May 20–26
        </p>
        <span className="bg-emerald-100 text-emerald-800 text-xs font-medium px-2 py-0.5 rounded-full border border-emerald-200">
          Completed
        </span>
      </div>
      <p className="text-base font-semibold text-[#0c0a08] mb-3">
        Spend up 12% — SaaS and Travel driving growth
      </p>
      <p className="text-xs font-semibold text-[#6e6a68] uppercase tracking-wide mb-2">
        Recommendations
      </p>
      <ul className="space-y-2">
        {[
          "Consider consolidating AWS and GCP billing under a single team card.",
          "3 travel bookings were made within 24h — bulk booking may reduce costs.",
          "MEALS category over budget by 18% this week.",
        ].map((rec, i) => (
          <li key={i} className="flex gap-2 text-sm text-[#0c0a08]">
            <span className="text-solar font-bold flex-shrink-0 text-xs mt-0.5">{i + 1}.</span>
            <span className="text-[#6e6a68] text-xs leading-relaxed">{rec}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Footer
// ---------------------------------------------------------------------------

function Footer() {
  return (
    <footer className="bg-[#1a1919] text-white py-16 px-8">
      <div className="max-w-7xl mx-auto">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-8">
          {/* Logo + tagline */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <div className="w-7 h-7 bg-solar rounded-md flex items-center justify-center">
                <span className="text-[#0c0a08] font-bold text-xs">V</span>
              </div>
              <span className="font-semibold text-white text-base">vault</span>
            </div>
            <p className="text-white/60 text-sm mt-2 leading-relaxed">
              AI-native corporate spend management for modern finance teams.
            </p>
          </div>

          {/* Product */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-white/40 mb-3">
              Product
            </p>
            <ul className="space-y-2">
              {["Cards", "Transactions", "Policies", "Digest"].map((item) => (
                <li key={item}>
                  <a href="#" className="text-sm text-white/60 hover:text-white transition-colors">
                    {item}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Built on */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-white/40 mb-3">
              Infrastructure
            </p>
            <a
              href="https://e2enetworks.com"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 bg-solar text-[#0c0a08] text-xs font-semibold px-3 py-1.5 rounded-md hover:bg-solar-light transition-colors"
            >
              <span>⚡</span>
              Built on E2E Cloud
            </a>
            <p className="text-white/40 text-xs mt-2 leading-relaxed">
              Powered by E2E Networks TIR infrastructure.
            </p>
          </div>
        </div>

        {/* Copyright row */}
        <div className="border-t border-white/10 mt-12 pt-8 flex items-center justify-between">
          <p className="text-white/40 text-xs">
            © {new Date().getFullYear()} Vault. All rights reserved.
          </p>
          <div className="flex gap-4">
            <a href="#" className="text-white/40 text-xs hover:text-white/60 transition-colors">
              Privacy
            </a>
            <a href="#" className="text-white/40 text-xs hover:text-white/60 transition-colors">
              Terms
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}

// ---------------------------------------------------------------------------
// LandingPage
// ---------------------------------------------------------------------------

export function LandingPage() {
  // Lenis smooth scroll — initialized here, destroyed on unmount
  useEffect(() => {
    const lenis = new Lenis({ lerp: 0.1 });
    lenis.on("scroll", ScrollTrigger.update);
    gsap.ticker.add((time) => lenis.raf(time * 1000));
    gsap.ticker.lagSmoothing(0);
    return () => {
      lenis.off("scroll", ScrollTrigger.update);
      gsap.ticker.remove((time) => lenis.raf(time * 1000));
      lenis.destroy();
    };
  }, []);

  return (
    <div className="min-h-screen bg-[#f4f2f0]">
      <LandingNav />
      <HeroSection />
      <MetricsTicker />

      <div id="features">
        <FeatureSection
          label="Card & Expense"
          heading={
            <>
              <span className="text-[#0c0a08]">Cards & Expenses</span>{" "}
              <span className="text-[#6e6a68]">that handle themselves</span>
            </>
          }
          body="AI automatically captures and matches receipts to every transaction. Spend policies are enforced in real-time — no manual review required."
          visual={<CardsMockup />}
          visualRight={true}
        />

        <FeatureSection
          label="Policy Engine"
          heading={
            <>
              <span className="text-[#0c0a08]">Policies written</span>{" "}
              <span className="text-[#6e6a68]">in plain English.</span>
            </>
          }
          body="Write spend rules in natural language and our LLM engine enforces them on every transaction. No code, no configuration — just your policy, exactly as intended."
          visual={<PolicyMockup />}
          visualRight={false}
        />

        <FeatureSection
          label="AI Intelligence"
          heading={
            <>
              <span className="text-[#0c0a08]">Weekly spend digest.</span>{" "}
              <span className="text-[#6e6a68]">Zero effort.</span>
            </>
          }
          body="Vault automatically generates a weekly spend digest with AI-powered insights and actionable recommendations. Know exactly where your money is going."
          visual={<DigestMockup />}
          visualRight={true}
        />
      </div>

      <Footer />
    </div>
  );
}
