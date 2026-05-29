import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";

const menuVariants = {
  hidden: { opacity: 0, y: -8, scale: 0.98 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.18 },
  },
};

const itemVariants = (i: number) => ({
  hidden: { opacity: 0, y: -4 },
  visible: { opacity: 1, y: 0, transition: { delay: i * 0.04, duration: 0.18 } },
});

const MEGA_COLUMNS = [
  {
    title: "Card & Expense",
    items: [
      { icon: "💳", label: "Virtual Cards", desc: "Instant virtual cards with spend controls" },
      { icon: "📎", label: "Receipt Capture", desc: "AI-powered receipt matching" },
      { icon: "📊", label: "Spend Analytics", desc: "Real-time category breakdowns" },
    ],
  },
  {
    title: "Policy Engine",
    items: [
      { icon: "📋", label: "Plain-English Rules", desc: "Write policies in natural language" },
      { icon: "🤖", label: "LLM Enforcement", desc: "AI evaluates every transaction" },
      { icon: "🚨", label: "Violation Alerts", desc: "Instant notifications on breaches" },
    ],
  },
  {
    title: "Intelligence",
    items: [
      { icon: "📰", label: "Weekly Digest", desc: "Automated spend summaries" },
      { icon: "💡", label: "Recommendations", desc: "Cost-saving insights from AI" },
      { icon: "📈", label: "Trend Analysis", desc: "Month-over-month comparisons" },
    ],
  },
];

export function LandingNav() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > 10);
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <nav
      className="fixed top-0 inset-x-0 z-50 transition-colors duration-200"
      style={{
        height: "62px",
        background: scrolled ? "#f4f2f0" : "rgba(244, 242, 240, 0.85)",
        backdropFilter: scrolled ? "blur(12px)" : "none",
        borderBottom: scrolled ? "1px solid #d2cecb" : "1px solid transparent",
      }}
    >
      <div className="max-w-7xl mx-auto px-6 h-full flex items-center justify-between">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 no-underline">
          <div className="w-7 h-7 bg-solar rounded-md flex items-center justify-center">
            <span className="text-[#0c0a08] font-bold text-xs">V</span>
          </div>
          <span className="font-semibold text-[#0c0a08] text-base">vault</span>
        </Link>

        {/* Center nav */}
        <div className="hidden md:flex items-center gap-6" ref={menuRef}>
          {/* Products mega-menu */}
          <div className="relative">
            <button
              onClick={() => setMenuOpen((v) => !v)}
              className="text-sm text-[#0c0a08] hover:text-[#6e6a68] transition-colors flex items-center gap-1"
            >
              Products
              <svg
                className={`w-3 h-3 transition-transform ${menuOpen ? "rotate-180" : ""}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.5}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            <AnimatePresence>
              {menuOpen && (
                <motion.div
                  variants={menuVariants}
                  initial="hidden"
                  animate="visible"
                  exit="hidden"
                  className="absolute top-8 left-1/2 -translate-x-1/2 bg-white border border-[#d2cecb] rounded-xl shadow-xl p-6 w-[640px]"
                >
                  <div className="grid grid-cols-3 gap-6">
                    {MEGA_COLUMNS.map((col, ci) => (
                      <div key={col.title}>
                        <p className="text-[10px] font-semibold text-[#6e6a68] uppercase tracking-wider mb-3">
                          {col.title}
                        </p>
                        <div className="space-y-3">
                          {col.items.map((item, ii) => (
                            <motion.div
                              key={item.label}
                              variants={itemVariants(ci * 3 + ii)}
                              initial="hidden"
                              animate="visible"
                              className="flex items-start gap-2 cursor-pointer group"
                            >
                              <span className="text-base leading-none mt-0.5">{item.icon}</span>
                              <div>
                                <p className="text-sm font-semibold text-[#0c0a08] group-hover:text-[#6e6a68] transition-colors">
                                  {item.label}
                                </p>
                                <p className="text-xs text-[#6e6a68] mt-0.5">{item.desc}</p>
                              </div>
                            </motion.div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <a href="#features" className="text-sm text-[#0c0a08] hover:text-[#6e6a68] transition-colors">
            Features
          </a>
          <a href="#pricing" className="text-sm text-[#0c0a08] hover:text-[#6e6a68] transition-colors">
            Pricing
          </a>
          <a href="#about" className="text-sm text-[#0c0a08] hover:text-[#6e6a68] transition-colors">
            About
          </a>
        </div>

        {/* CTAs */}
        <div className="flex items-center gap-4">
          <Link
            to="/login"
            className="text-sm text-[#0c0a08] hover:text-[#6e6a68] transition-colors"
          >
            Sign in
          </Link>
          <Link
            to="/signup"
            className="bg-solar text-[#0c0a08] text-sm font-semibold px-4 py-2 rounded-[6px] hover:bg-solar-light transition-colors"
          >
            Get started free
          </Link>
        </div>
      </div>
    </nav>
  );
}
