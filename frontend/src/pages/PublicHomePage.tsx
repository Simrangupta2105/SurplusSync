import React, { useState, useEffect } from 'react';
import {
  Sun,
  Moon,
  ArrowRight,
  CheckCircle2,
  Package,
  Layers,
  Truck,
  Building2,
  HeartHandshake,
  ShieldCheck,
  QrCode,
  FileSpreadsheet,
  CalendarCheck,
  TrendingUp,
  Sparkles,
  ChevronDown,
  Menu,
  X,
  Mail,
} from 'lucide-react';
import { usePublicHomeTotals } from '../hooks/useData';
import { Button } from '../components/ui/Button';

export interface PublicHomePageProps {
  onNavigateToLogin: () => void;
  onNavigateToRegister: (role?: 'BUSINESS' | 'NGO') => void;
  isDark: boolean;
  onToggleDark: () => void;
  isDemo?: boolean;
}

// Hook for count-up animation that respects prefers-reduced-motion
function useCountUp(target: number, durationMs = 1100): number {
  const prefersReducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const [val, setVal] = useState<number>(() => (prefersReducedMotion ? target : 0));

  useEffect(() => {
    if (prefersReducedMotion || target === 0) {
      return;
    }

    let start: number | null = null;
    let animId: number;

    const tick = (now: number) => {
      if (!start) start = now;
      const progress = Math.min((now - start) / durationMs, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      setVal(ease * target);
      if (progress < 1) {
        animId = requestAnimationFrame(tick);
      } else {
        setVal(target);
      }
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [target, durationMs, prefersReducedMotion]);

  return prefersReducedMotion ? target : val;
}

interface CounterCardProps {
  label: string;
  value: number;
  unit?: string;
  isDecimal?: boolean;
}

const CounterCard: React.FC<CounterCardProps> = ({ label, value, unit, isDecimal = false }) => {
  const animatedValue = useCountUp(value);
  const formatted = isDecimal
    ? animatedValue.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })
    : Math.round(animatedValue).toLocaleString();

  const isLong = formatted.length > 6;

  return (
    <div className="flex flex-col items-center justify-center p-2.5 sm:p-3 rounded-[12px] bg-[var(--surface)] border border-[var(--border)] shadow-xs transition-transform duration-200 hover:-translate-y-0.5 min-h-[96px] overflow-hidden">
      <div className="flex items-baseline gap-1 justify-center max-w-full">
        <span
          className={`font-extrabold tracking-tight text-[var(--text)] tabular-nums leading-tight ${
            isLong ? 'text-lg sm:text-xl' : 'text-xl sm:text-2xl'
          }`}
        >
          {formatted}
        </span>
        {unit && <span className="text-[11px] sm:text-xs font-semibold text-[var(--muted)] shrink-0">{unit}</span>}
      </div>
      <div className="mt-1 text-[11px] sm:text-xs font-medium text-[var(--muted)] text-center leading-tight truncate max-w-full px-1">
        {label}
      </div>
    </div>
  );
};

export const PublicHomePage: React.FC<PublicHomePageProps> = ({
  onNavigateToLogin,
  onNavigateToRegister,
  isDark,
  onToggleDark,
  isDemo = false,
}) => {
  const { data: publicTotals, isLoading: isTotalsLoading } = usePublicHomeTotals();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [expandedFaqIndex, setExpandedFaqIndex] = useState<number | null>(null);

  // Set document title and SEO metadata on mount
  useEffect(() => {
    const prevTitle = document.title;
    document.title = 'SurplusSync - Turn Surplus Food into Community Meals';
    return () => {
      document.title = prevTitle;
    };
  }, []);

  const contactEmail = import.meta.env.VITE_CONTACT_EMAIL || 'support@surplussync.org';
  const currentYear = new Date().getFullYear();

  // Check if all metrics are zero
  const isAllZero =
    !isTotalsLoading &&
    (!publicTotals ||
      (Number(publicTotals.kg_redistributed || 0) === 0 &&
        Number(publicTotals.meals || 0) === 0 &&
        Number(publicTotals.co2e || 0) === 0 &&
        Number(publicTotals.verified_donors || 0) === 0 &&
        Number(publicTotals.verified_ngos || 0) === 0 &&
        Number(publicTotals.completed_donations || 0) === 0));

  const toggleFaq = (index: number) => {
    setExpandedFaqIndex((prev) => (prev === index ? null : index));
  };

  const scrollToSection = (e: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    e.preventDefault();
    setMobileMenuOpen(false);
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const faqItems = [
    {
      question: 'Who can join SurplusSync?',
      answer:
        'SurplusSync is designed for licensed commercial food businesses (supermarkets, bakeries, restaurants, catering facilities) seeking to redistribute surplus stock, and registered non-profit organizations or food rescue charities that provide food assistance to community members.',
    },
    {
      question: 'How are NGOs verified?',
      answer:
        'Every non-profit organization is manually reviewed and approved by platform administrators prior to claiming food. Administrators verify official registration credentials, designated operational facilities, and authorized liaison contact details.',
    },
    {
      question: 'Is SurplusSync free to use?',
      answer:
        'Yes. SurplusSync provides core inventory shelf-life tracking, surplus listing management, automated matching, and donation logistics coordination free of charge for participating food donors and verified charitable organizations.',
    },
    {
      question: 'How do pickups and logistics work?',
      answer:
        'When an NGO requests an available surplus listing, the donor approves the request and confirms an agreeable pickup window. The NGO dispatches their designated team, updates transit progress in the app, and both parties record completed handoff upon collection.',
    },
    {
      question: 'How is food safety maintained?',
      answer:
        'Donors must specify exact storage conditions (ambient, chilled, or frozen), allergen declarations, and strict consume-by deadlines. Cooked food items require preparation timestamps and short safe-until windows. Rescues must be completed before expiry.',
    },
    {
      question: 'How is organizational data kept private?',
      answer:
        'SurplusSync enforces multi-tenant database isolation. Each organization’s internal inventory, cost records, and operational notes are restricted strictly to authenticated members of that organization. Public totals represent anonymous platform-wide aggregates only.',
    },
  ];

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)] transition-colors duration-200">
      {/* 1. Navigation Bar */}
      <header className="sticky top-0 z-50 w-full border-b border-[var(--border)] bg-[var(--surface)]/90 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center space-x-3">
            <div className="h-9 w-9 rounded-[8px] bg-gradient-to-tr from-[var(--primary)] to-[var(--accent)] flex items-center justify-center shadow-xs">
              <Package className="h-5 w-5 text-white" aria-hidden="true" />
            </div>
            <span className="font-extrabold text-xl tracking-tight text-[var(--text)]">SurplusSync</span>
          </div>

          {/* Desktop Navigation Links */}
          <nav className="hidden md:flex items-center space-x-7 text-sm font-medium" aria-label="Main Navigation">
            <a
              href="#how-it-works"
              onClick={(e) => scrollToSection(e, 'how-it-works')}
              className="text-[var(--muted)] hover:text-[var(--text)] transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[var(--primary)] rounded-xs py-1 px-1.5"
            >
              How it works
            </a>
            <a
              href="#for-businesses"
              onClick={(e) => scrollToSection(e, 'for-businesses')}
              className="text-[var(--muted)] hover:text-[var(--text)] transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[var(--primary)] rounded-xs py-1 px-1.5"
            >
              For businesses
            </a>
            <a
              href="#for-ngos"
              onClick={(e) => scrollToSection(e, 'for-ngos')}
              className="text-[var(--muted)] hover:text-[var(--text)] transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[var(--primary)] rounded-xs py-1 px-1.5"
            >
              For NGOs
            </a>
            <a
              href="#features"
              onClick={(e) => scrollToSection(e, 'features')}
              className="text-[var(--muted)] hover:text-[var(--text)] transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[var(--primary)] rounded-xs py-1 px-1.5"
            >
              Features
            </a>
            <a
              href="#faq"
              onClick={(e) => scrollToSection(e, 'faq')}
              className="text-[var(--muted)] hover:text-[var(--text)] transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[var(--primary)] rounded-xs py-1 px-1.5"
            >
              FAQ
            </a>
          </nav>

          {/* Right Header Actions */}
          <div className="hidden md:flex items-center space-x-3">
            <button
              type="button"
              onClick={onToggleDark}
              aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              className="p-2 rounded-[8px] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
            >
              {isDark ? <Sun className="h-5 w-5" aria-hidden="true" /> : <Moon className="h-5 w-5" aria-hidden="true" />}
            </button>

            <Button
              variant="outline"
              size="sm"
              onClick={onNavigateToLogin}
              className="focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
            >
              Sign in
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => onNavigateToRegister()}
              className="focus-visible:ring-2 focus-visible:ring-[var(--primary)] shadow-xs"
            >
              Register
            </Button>
          </div>

          {/* Mobile menu trigger button */}
          <div className="flex md:hidden items-center space-x-2">
            <button
              type="button"
              onClick={onToggleDark}
              aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
              className="p-2 rounded-[8px] text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
            >
              {isDark ? <Sun className="h-5 w-5" aria-hidden="true" /> : <Moon className="h-5 w-5" aria-hidden="true" />}
            </button>

            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-expanded={mobileMenuOpen}
              aria-label="Toggle navigation menu"
              className="p-2 rounded-[8px] text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
            >
              {mobileMenuOpen ? <X className="h-6 w-6" aria-hidden="true" /> : <Menu className="h-6 w-6" aria-hidden="true" />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <div className="md:hidden border-b border-[var(--border)] bg-[var(--surface)] px-4 pt-3 pb-5 space-y-3 animate-in slide-in-from-top-2 duration-150">
            <nav className="flex flex-col space-y-2 text-base font-medium" aria-label="Mobile Navigation">
              <a
                href="#how-it-works"
                onClick={(e) => scrollToSection(e, 'how-it-works')}
                className="px-3 py-2 rounded-[8px] text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors"
              >
                How it works
              </a>
              <a
                href="#for-businesses"
                onClick={(e) => scrollToSection(e, 'for-businesses')}
                className="px-3 py-2 rounded-[8px] text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors"
              >
                For businesses
              </a>
              <a
                href="#for-ngos"
                onClick={(e) => scrollToSection(e, 'for-ngos')}
                className="px-3 py-2 rounded-[8px] text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors"
              >
                For NGOs
              </a>
              <a
                href="#features"
                onClick={(e) => scrollToSection(e, 'features')}
                className="px-3 py-2 rounded-[8px] text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors"
              >
                Features
              </a>
              <a
                href="#faq"
                onClick={(e) => scrollToSection(e, 'faq')}
                className="px-3 py-2 rounded-[8px] text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors"
              >
                FAQ
              </a>
            </nav>
            <div className="pt-3 border-t border-[var(--border)] flex flex-col space-y-2">
              <Button
                variant="outline"
                className="w-full justify-center"
                onClick={() => {
                  setMobileMenuOpen(false);
                  onNavigateToLogin();
                }}
              >
                Sign in
              </Button>
              <Button
                variant="primary"
                className="w-full justify-center shadow-xs"
                onClick={() => {
                  setMobileMenuOpen(false);
                  onNavigateToRegister();
                }}
              >
                Register
              </Button>
            </div>
          </div>
        )}
      </header>

      {/* 2. Hero Section */}
      <section className="relative overflow-hidden py-16 sm:py-24 lg:py-32">
        {/* Subtle Decorative Ambient Background Gradients */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[700px] h-[500px] rounded-full bg-gradient-to-tr from-[var(--primary)]/15 via-[var(--accent)]/10 to-transparent blur-3xl opacity-70"
        />

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-8 items-center">
            {/* Left Hero Content */}
            <div className="lg:col-span-7 text-center lg:text-left space-y-6">
              <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full border border-[var(--border)] bg-[var(--surface-2)] text-xs font-semibold text-[var(--text)] shadow-xs">
                <Sparkles className="h-3.5 w-3.5 text-[var(--primary)]" aria-hidden="true" />
                <span>Transparent Surplus Food Logistics</span>
              </div>

              <h1 className="text-3xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-[var(--text)] leading-[1.12]">
                Turning Surplus Food into{' '}
                <span className="bg-gradient-to-r from-[var(--primary)] to-[var(--accent)] bg-clip-text text-transparent">
                  Real Meals
                </span>
              </h1>

              <p className="text-base sm:text-xl text-[var(--muted)] max-w-2xl mx-auto lg:mx-0 leading-relaxed">
                A unified logistics platform connecting food businesses with verified NGOs to track inventory, identify
                surplus, and coordinate transparent food redistribution.
              </p>

              {/* Two Calls to Action */}
              <div className="pt-2 flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-3 sm:gap-4">
                <Button
                  variant="primary"
                  size="lg"
                  onClick={() => onNavigateToRegister('BUSINESS')}
                  className="w-full sm:w-auto font-semibold shadow-md flex items-center justify-center gap-2 focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
                >
                  <Building2 className="h-4 w-4" aria-hidden="true" />
                  <span>Register your business</span>
                  <ArrowRight className="h-4 w-4 ml-1" aria-hidden="true" />
                </Button>

                <Button
                  variant="outline"
                  size="lg"
                  onClick={() => onNavigateToRegister('NGO')}
                  className="w-full sm:w-auto font-semibold flex items-center justify-center gap-2 focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
                >
                  <HeartHandshake className="h-4 w-4 text-[var(--accent)]" aria-hidden="true" />
                  <span>Register as an NGO</span>
                </Button>
              </div>

              <div className="flex items-center justify-center lg:justify-start space-x-6 pt-3 text-xs sm:text-sm text-[var(--muted)]">
                <div className="flex items-center space-x-1.5">
                  <CheckCircle2 className="h-4 w-4 text-[var(--color-success)]" aria-hidden="true" />
                  <span>Verified NGO network</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <CheckCircle2 className="h-4 w-4 text-[var(--color-success)]" aria-hidden="true" />
                  <span>Zero fake metrics</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <CheckCircle2 className="h-4 w-4 text-[var(--color-success)]" aria-hidden="true" />
                  <span>Strict tenant privacy</span>
                </div>
              </div>
            </div>

            {/* Right Hero Decorative SVG Illustration */}
            <div className="lg:col-span-5 flex justify-center">
              <div className="relative w-full max-w-[460px] p-6 rounded-[20px] bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] border border-[var(--border)] shadow-xl">
                {/* Visual Architecture Diagram (Pure SVG) */}
                <svg
                  viewBox="0 0 400 320"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                  className="w-full h-auto"
                  aria-label="Illustration showing inventory tracking, automated matching, and coordinated pickup handoff"
                  role="img"
                >
                  {/* Decorative background grid lines */}
                  <defs>
                    <linearGradient id="primaryGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.8" />
                      <stop offset="100%" stopColor="var(--accent)" stopOpacity="0.8" />
                    </linearGradient>
                    <linearGradient id="nodeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stopColor="var(--surface)" />
                      <stop offset="100%" stopColor="var(--surface-2)" />
                    </linearGradient>
                  </defs>

                  {/* Flow Connection Paths */}
                  <path
                    d="M 100 100 C 100 160, 200 160, 200 160 C 200 160, 300 160, 300 220"
                    stroke="url(#primaryGrad)"
                    strokeWidth="3"
                    strokeDasharray="6 6"
                    className="opacity-70 animate-pulse"
                  />
                  <path
                    d="M 100 100 L 200 160 L 300 220"
                    stroke="var(--border)"
                    strokeWidth="1.5"
                    strokeOpacity="0.6"
                  />

                  {/* Node 1: Business Kitchen / Donor */}
                  <g transform="translate(35, 50)">
                    <rect width="135" height="90" rx="12" fill="url(#nodeGrad)" stroke="var(--border)" strokeWidth="1.5" />
                    <rect x="10" y="14" width="26" height="26" rx="6" fill="var(--primary)" fillOpacity="0.15" />
                    <circle cx="23" cy="27" r="5" fill="var(--primary)" />
                    <text x="42" y="25" fill="var(--text)" fontSize="10" fontWeight="700">Food Donor</text>
                    <text x="42" y="37" fill="var(--muted)" fontSize="8.5">Kitchen &amp; Bakery</text>
                    <rect x="10" y="52" width="115" height="6" rx="3" fill="var(--surface-2)" />
                    <rect x="10" y="64" width="85" height="6" rx="3" fill="var(--surface-2)" />
                    <rect x="10" y="76" width="55" height="4" rx="2" fill="var(--color-success)" />
                  </g>

                  {/* Central Hub: Automated Matching Engine */}
                  <g transform="translate(150, 125)">
                    <rect width="100" height="70" rx="14" fill="var(--surface)" stroke="var(--primary)" strokeWidth="2" filter="drop-shadow(0 4px 6px rgba(0,0,0,0.1))" />
                    <circle cx="50" cy="26" r="12" fill="var(--primary)" fillOpacity="0.2" />
                    <text x="50" y="30" textAnchor="middle" fill="var(--primary)" fontSize="11" fontWeight="800">SYNC</text>
                    <text x="50" y="52" textAnchor="middle" fill="var(--text)" fontSize="10" fontWeight="600">Surplus Match</text>
                  </g>

                  {/* Node 2: Verified NGO / Community Kitchen */}
                  <g transform="translate(230, 180)">
                    <rect width="135" height="90" rx="12" fill="url(#nodeGrad)" stroke="var(--border)" strokeWidth="1.5" />
                    <rect x="10" y="14" width="26" height="26" rx="6" fill="var(--accent)" fillOpacity="0.15" />
                    <circle cx="23" cy="27" r="5" fill="var(--accent)" />
                    <text x="42" y="25" fill="var(--text)" fontSize="10" fontWeight="700">Verified NGO</text>
                    <text x="42" y="37" fill="var(--muted)" fontSize="8.5">Community Kitchen</text>
                    <rect x="10" y="52" width="115" height="6" rx="3" fill="var(--surface-2)" />
                    <rect x="10" y="64" width="75" height="6" rx="3" fill="var(--surface-2)" />
                    <rect x="10" y="76" width="65" height="4" rx="2" fill="var(--accent)" />
                  </g>

                  {/* Live Status Floating Pill */}
                  <g transform="translate(20, 20)">
                    <rect width="130" height="24" rx="12" fill="var(--surface)" stroke="var(--border)" strokeWidth="1" />
                    <circle cx="12" cy="12" r="4" fill="var(--color-success)" />
                    <text x="24" y="16" fill="var(--text)" fontSize="9" fontWeight="600">Inventory Monitored</text>
                  </g>

                  {/* Pickup Status Floating Pill */}
                  <g transform="translate(225, 280)">
                    <rect width="150" height="24" rx="12" fill="var(--surface)" stroke="var(--border)" strokeWidth="1" />
                    <circle cx="12" cy="12" r="4" fill="var(--primary)" />
                    <text x="24" y="16" fill="var(--text)" fontSize="9" fontWeight="600">Direct Pickup Scheduled</text>
                  </g>
                </svg>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 3. Impact Counters Strip (GET /api/v1/home/public/) */}
      {!isAllZero && (
        <section
          aria-label="Platform Impact Metrics"
          className="border-y border-[var(--border)] bg-[var(--surface-2)]/60 py-10 sm:py-12"
        >
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-6 pb-2 border-b border-[var(--border)]">
              <div>
                <h2 className="text-lg sm:text-xl font-bold text-[var(--text)]">Verified Platform Impact</h2>
                <p className="text-xs sm:text-sm text-[var(--muted)]">
                  Live aggregate metrics computed from completed redistribution handoffs.
                </p>
              </div>
              {isDemo && (
                <div className="mt-2 sm:mt-0 inline-flex items-center px-2.5 py-1 rounded-md bg-[var(--surface)] border border-[var(--border)] text-xs font-semibold text-[var(--primary)] shadow-xs">
                  <span>Sample data</span>
                </div>
              )}
            </div>

            {/* Metric Cards Grid - Fixed Min-Heights to prevent layout shift */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4">
              <CounterCard
                label="Food Diverted"
                value={Number(publicTotals?.kg_redistributed || 0)}
                unit="kg"
                isDecimal={true}
              />
              <CounterCard
                label="Meals Provided"
                value={Number(publicTotals?.meals || 0)}
              />
              <CounterCard
                label="CO₂e Prevented"
                value={Number(publicTotals?.co2e || 0)}
                unit="kg"
                isDecimal={true}
              />
              <CounterCard
                label="Verified Donors"
                value={Number(publicTotals?.verified_donors || 0)}
              />
              <CounterCard
                label="Verified NGOs"
                value={Number(publicTotals?.verified_ngos || 0)}
              />
              <CounterCard
                label="Completed Rescues"
                value={Number(publicTotals?.completed_donations || 0)}
              />
            </div>
          </div>
        </section>
      )}

      {/* 4. How It Works Section */}
      <section id="how-it-works" className="py-16 sm:py-24 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16 space-y-3">
          <h2 className="text-2xl sm:text-4xl font-extrabold text-[var(--text)] tracking-tight">
            How SurplusSync Works
          </h2>
          <p className="text-base sm:text-lg text-[var(--muted)]">
            A structured, three-step lifecycle connecting surplus inventory to community meals.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Step 1 */}
          <div className="relative p-6 sm:p-8 rounded-[16px] bg-[var(--surface)] border border-[var(--border)] shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div className="h-12 w-12 rounded-[10px] bg-[var(--primary)]/10 text-[var(--primary)] flex items-center justify-center font-bold text-lg">
                <Package className="h-6 w-6" aria-hidden="true" />
              </div>
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--muted)]">Step 01</span>
            </div>
            <h3 className="text-lg sm:text-xl font-bold text-[var(--text)]">Track Inventory</h3>
            <p className="text-sm text-[var(--muted)] leading-relaxed">
              Log stock batches, monitor real-time shelf life, and ingest inventory manifests via barcode scanning, CSV upload, or POS keys.
            </p>
          </div>

          {/* Step 2 */}
          <div className="relative p-6 sm:p-8 rounded-[16px] bg-[var(--surface)] border border-[var(--border)] shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div className="h-12 w-12 rounded-[10px] bg-[var(--accent)]/10 text-[var(--accent)] flex items-center justify-center font-bold text-lg">
                <Layers className="h-6 w-6" aria-hidden="true" />
              </div>
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--muted)]">Step 02</span>
            </div>
            <h3 className="text-lg sm:text-xl font-bold text-[var(--text)]">Identify Surplus</h3>
            <p className="text-sm text-[var(--muted)] leading-relaxed">
              Automated expiry triggers flag nearing-date items before they become waste and create structured surplus listings with quantity reservation locks.
            </p>
          </div>

          {/* Step 3 */}
          <div className="relative p-6 sm:p-8 rounded-[16px] bg-[var(--surface)] border border-[var(--border)] shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div className="h-12 w-12 rounded-[10px] bg-[var(--color-success)]/10 text-[var(--color-success)] flex items-center justify-center font-bold text-lg">
                <Truck className="h-6 w-6" aria-hidden="true" />
              </div>
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--muted)]">Step 03</span>
            </div>
            <h3 className="text-lg sm:text-xl font-bold text-[var(--text)]">Redistribute Food</h3>
            <p className="text-sm text-[var(--muted)] leading-relaxed">
              Verified NGOs discover matching donations, schedule coordinated pickups, and log verified deliveries with full impact tracking.
            </p>
          </div>
        </div>
      </section>

      {/* 5. For Businesses and For NGOs Section */}
      <section className="py-16 bg-[var(--surface-2)]/40 border-y border-[var(--border)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto mb-14 space-y-3">
            <h2 className="text-2xl sm:text-4xl font-extrabold text-[var(--text)] tracking-tight">
              Tailored for Donors and Non-Profits
            </h2>
            <p className="text-base sm:text-lg text-[var(--muted)]">
              Dedicated workflows customized for the realities of commercial kitchens and charity food logistics.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Card 1: For Businesses */}
            <div
              id="for-businesses"
              className="p-6 sm:p-8 rounded-[16px] bg-[var(--surface)] border border-[var(--border)] shadow-xs flex flex-col justify-between space-y-6"
            >
              <div className="space-y-4">
                <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-[var(--primary)]/10 text-[var(--primary)] text-xs font-bold">
                  <Building2 className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>For Food Businesses</span>
                </div>
                <h3 className="text-xl sm:text-2xl font-bold text-[var(--text)]">
                  Reduce Waste & Automate Surplus Redistribution
                </h3>
                <p className="text-sm text-[var(--muted)] leading-relaxed">
                  Turn stock nearing expiration into meaningful community aid while maintaining precise inventory controls and audit records.
                </p>

                <ul className="space-y-3 pt-2 text-sm text-[var(--text)]" role="list">
                  <li className="flex items-start space-x-3">
                    <CheckCircle2 className="h-5 w-5 text-[var(--primary)] shrink-0 mt-0.5" aria-hidden="true" />
                    <span><strong>Expiry Tracking:</strong> Proactive batch countdowns and customizable spoilage alert rules.</span>
                  </li>
                  <li className="flex items-start space-x-3">
                    <CheckCircle2 className="h-5 w-5 text-[var(--primary)] shrink-0 mt-0.5" aria-hidden="true" />
                    <span><strong>Surplus Listings:</strong> One-click donation creation with automatic inventory reservation locks.</span>
                  </li>
                  <li className="flex items-start space-x-3">
                    <CheckCircle2 className="h-5 w-5 text-[var(--primary)] shrink-0 mt-0.5" aria-hidden="true" />
                    <span><strong>Donation Requests:</strong> Review, approve, or adjust claim quantities and pickup appointments.</span>
                  </li>
                  <li className="flex items-start space-x-3">
                    <CheckCircle2 className="h-5 w-5 text-[var(--primary)] shrink-0 mt-0.5" aria-hidden="true" />
                    <span><strong>Impact Reports:</strong> Verifiable kg saved, meals provided, and carbon emissions averted scorecards.</span>
                  </li>
                </ul>
              </div>

              <div className="pt-4 border-t border-[var(--border)]">
                <Button
                  variant="primary"
                  className="w-full sm:w-auto font-semibold"
                  onClick={() => onNavigateToRegister('BUSINESS')}
                >
                  Register your business
                </Button>
              </div>
            </div>

            {/* Card 2: For NGOs */}
            <div
              id="for-ngos"
              className="p-6 sm:p-8 rounded-[16px] bg-[var(--surface)] border border-[var(--border)] shadow-xs flex flex-col justify-between space-y-6"
            >
              <div className="space-y-4">
                <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-[var(--accent)]/10 text-[var(--accent)] text-xs font-bold">
                  <HeartHandshake className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>For Verified Non-Profits</span>
                </div>
                <h3 className="text-xl sm:text-2xl font-bold text-[var(--text)]">
                  Reliable Food Rescue for Community Kitchens
                </h3>
                <p className="text-sm text-[var(--muted)] leading-relaxed">
                  Gain consistent, dignified access to surplus groceries, fresh bakery items, and prepared meals from licensed donors.
                </p>

                <ul className="space-y-3 pt-2 text-sm text-[var(--text)]" role="list">
                  <li className="flex items-start space-x-3">
                    <CheckCircle2 className="h-5 w-5 text-[var(--accent)] shrink-0 mt-0.5" aria-hidden="true" />
                    <span><strong>Live Food Feed:</strong> Browse real-time surplus donations filtered by distance, category, and temperature.</span>
                  </li>
                  <li className="flex items-start space-x-3">
                    <CheckCircle2 className="h-5 w-5 text-[var(--accent)] shrink-0 mt-0.5" aria-hidden="true" />
                    <span><strong>Requirements & Matching:</strong> Post organization food needs to receive automated alerts on matching donations.</span>
                  </li>
                  <li className="flex items-start space-x-3">
                    <CheckCircle2 className="h-5 w-5 text-[var(--accent)] shrink-0 mt-0.5" aria-hidden="true" />
                    <span><strong>Pickup Scheduling:</strong> Coordinate transparent pickup windows, dispatch drivers, and update transit status.</span>
                  </li>
                  <li className="flex items-start space-x-3">
                    <CheckCircle2 className="h-5 w-5 text-[var(--accent)] shrink-0 mt-0.5" aria-hidden="true" />
                    <span><strong>Impact Reports:</strong> Transparent reporting on meal distribution milestones and community impact.</span>
                  </li>
                </ul>
              </div>

              <div className="pt-4 border-t border-[var(--border)]">
                <Button
                  variant="outline"
                  className="w-full sm:w-auto font-semibold"
                  onClick={() => onNavigateToRegister('NGO')}
                >
                  Register as an NGO
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 6. Features Grid */}
      <section id="features" className="py-16 sm:py-24 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto mb-16 space-y-3">
          <h2 className="text-2xl sm:text-4xl font-extrabold text-[var(--text)] tracking-tight">
            Enterprise Logistics Features
          </h2>
          <p className="text-base sm:text-lg text-[var(--muted)]">
            Built from the ground up for food safety, inventory precision, and reliable redistribution.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Feature 1 */}
          <div className="p-6 rounded-[14px] bg-[var(--surface)] border border-[var(--border)] shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <div className="p-2.5 rounded-[8px] bg-[var(--primary)]/10 text-[var(--primary)]">
                <CalendarCheck className="h-5 w-5" aria-hidden="true" />
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[var(--surface-2)] text-[var(--color-success)] border border-[var(--border)]">
                Live
              </span>
            </div>
            <h3 className="font-bold text-base sm:text-lg text-[var(--text)]">Expiry Alerts</h3>
            <p className="text-sm text-[var(--muted)] leading-relaxed">
              Configurable severity thresholds (Critical, Warning, Low) with automated email and in-app notifications before expiration.
            </p>
          </div>

          {/* Feature 2 */}
          <div className="p-6 rounded-[14px] bg-[var(--surface)] border border-[var(--border)] shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <div className="p-2.5 rounded-[8px] bg-[var(--primary)]/10 text-[var(--primary)]">
                <QrCode className="h-5 w-5" aria-hidden="true" />
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[var(--surface-2)] text-[var(--color-success)] border border-[var(--border)]">
                Live
              </span>
            </div>
            <h3 className="font-bold text-base sm:text-lg text-[var(--text)]">Barcode Scanning</h3>
            <p className="text-sm text-[var(--muted)] leading-relaxed">
              Camera-based barcode scanning and image file decoding for instant GS1 and EAN-13 product lookup and stock intake.
            </p>
          </div>

          {/* Feature 3 */}
          <div className="p-6 rounded-[14px] bg-[var(--surface)] border border-[var(--border)] shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <div className="p-2.5 rounded-[8px] bg-[var(--primary)]/10 text-[var(--primary)]">
                <FileSpreadsheet className="h-5 w-5" aria-hidden="true" />
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[var(--surface-2)] text-[var(--color-success)] border border-[var(--border)]">
                Live
              </span>
            </div>
            <h3 className="font-bold text-base sm:text-lg text-[var(--text)]">CSV & POS Integration</h3>
            <p className="text-sm text-[var(--muted)] leading-relaxed">
              Bulk inventory ingestion with background job processing and API key authentication for external cash registers.
            </p>
          </div>

          {/* Feature 4 */}
          <div className="p-6 rounded-[14px] bg-[var(--surface)] border border-[var(--border)] shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <div className="p-2.5 rounded-[8px] bg-[var(--accent)]/10 text-[var(--accent)]">
                <Layers className="h-5 w-5" aria-hidden="true" />
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[var(--surface-2)] text-[var(--color-success)] border border-[var(--border)]">
                Live
              </span>
            </div>
            <h3 className="font-bold text-base sm:text-lg text-[var(--text)]">Automated Matching</h3>
            <p className="text-sm text-[var(--muted)] leading-relaxed">
              Intelligent matching engine pairing surplus food with NGO requirements based on category, quantity, and geographic proximity.
            </p>
          </div>

          {/* Feature 5 */}
          <div className="p-6 rounded-[14px] bg-[var(--surface)] border border-[var(--border)] shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <div className="p-2.5 rounded-[8px] bg-[var(--accent)]/10 text-[var(--accent)]">
                <Truck className="h-5 w-5" aria-hidden="true" />
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[var(--surface-2)] text-[var(--color-success)] border border-[var(--border)]">
                Live
              </span>
            </div>
            <h3 className="font-bold text-base sm:text-lg text-[var(--text)]">Pickup Scheduling</h3>
            <p className="text-sm text-[var(--muted)] leading-relaxed">
              Coordinated pickup time windows, live on-my-way status, handoff confirmations, and driver details.
            </p>
          </div>

          {/* Feature 6 */}
          <div className="p-6 rounded-[14px] bg-[var(--surface)] border border-[var(--border)] shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <div className="p-2.5 rounded-[8px] bg-[var(--accent)]/10 text-[var(--accent)]">
                <TrendingUp className="h-5 w-5" aria-hidden="true" />
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[var(--surface-2)] text-[var(--color-success)] border border-[var(--border)]">
                Live
              </span>
            </div>
            <h3 className="font-bold text-base sm:text-lg text-[var(--text)]">Impact Tracking</h3>
            <p className="text-sm text-[var(--muted)] leading-relaxed">
              Auditable sustainability analytics tracking kilograms diverted, equivalent meals served, and CO₂e offset.
            </p>
          </div>

          {/* Feature 7: AI Waste Prediction (Powered by ML Service) */}
          <div className="p-6 rounded-[14px] bg-[var(--surface)] border border-[var(--primary)]/30 shadow-xs space-y-3 sm:col-span-2 lg:col-span-3 transition-all hover:border-[var(--primary)]/60">
            <div className="flex items-center justify-between">
              <div className="p-2.5 rounded-[8px] bg-[var(--primary-subtle)] text-[var(--primary)]">
                <Sparkles className="h-5 w-5" aria-hidden="true" />
              </div>
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Live ML
              </span>
            </div>
            <h3 className="font-bold text-base sm:text-lg text-[var(--text)]">AI Waste Prediction & Demand Planning</h3>
            <p className="text-sm text-[var(--muted)] leading-relaxed">
              Predictive demand intelligence, shelf-life risk scoring, and automated reorder recommendations powered by our dedicated machine learning service.
            </p>
          </div>
        </div>
      </section>

      {/* 7. FAQ Accordion (Keyboard Accessible) */}
      <section id="faq" className="py-16 sm:py-24 bg-[var(--surface-2)]/40 border-t border-[var(--border)]">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12 space-y-3">
            <h2 className="text-2xl sm:text-4xl font-extrabold text-[var(--text)] tracking-tight">
              Frequently Asked Questions
            </h2>
            <p className="text-base sm:text-lg text-[var(--muted)]">
              Factual information on platform access, verification, safety, and security.
            </p>
          </div>

          <div className="space-y-3" role="region" aria-label="Frequently Asked Questions">
            {faqItems.map((item, index) => {
              const isExpanded = expandedFaqIndex === index;
              const buttonId = `faq-btn-${index}`;
              const panelId = `faq-panel-${index}`;

              return (
                <div
                  key={item.question}
                  className="rounded-[12px] bg-[var(--surface)] border border-[var(--border)] overflow-hidden transition-all duration-200"
                >
                  <h3>
                    <button
                      type="button"
                      id={buttonId}
                      aria-expanded={isExpanded}
                      aria-controls={panelId}
                      onClick={() => toggleFaq(index)}
                      className="w-full flex items-center justify-between p-5 text-left font-semibold text-base sm:text-lg text-[var(--text)] hover:bg-[var(--surface-2)]/60 transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
                    >
                      <span>{item.question}</span>
                      <ChevronDown
                        className={`h-5 w-5 text-[var(--muted)] shrink-0 ml-4 transition-transform duration-200 ${
                          isExpanded ? 'rotate-180 text-[var(--primary)]' : ''
                        }`}
                        aria-hidden="true"
                      />
                    </button>
                  </h3>
                  {isExpanded && (
                    <div
                      id={panelId}
                      role="region"
                      aria-labelledby={buttonId}
                      className="px-5 pb-5 pt-1 text-sm sm:text-base text-[var(--muted)] leading-relaxed border-t border-[var(--border)]/60 animate-in fade-in duration-150"
                    >
                      {item.answer}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* 8. Final Call to Action & Footer */}
      <section className="py-16 sm:py-20 bg-gradient-to-br from-[var(--surface)] via-[var(--surface-2)] to-[var(--surface)] border-t border-[var(--border)]">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-6">
          <h2 className="text-2xl sm:text-4xl font-extrabold text-[var(--text)] tracking-tight">
            Ready to stop food waste and feed communities?
          </h2>
          <p className="text-base sm:text-lg text-[var(--muted)] max-w-2xl mx-auto leading-relaxed">
            Join verified food businesses and community charities across the region on SurplusSync today.
          </p>

          <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button
              variant="primary"
              size="lg"
              onClick={() => onNavigateToRegister('BUSINESS')}
              className="w-full sm:w-auto font-semibold shadow-md flex items-center justify-center gap-2 focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
            >
              <span>Register your business</span>
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Button>
            <Button
              variant="outline"
              size="lg"
              onClick={() => onNavigateToRegister('NGO')}
              className="w-full sm:w-auto font-semibold flex items-center justify-center gap-2 focus-visible:ring-2 focus-visible:ring-[var(--primary)]"
            >
              <HeartHandshake className="h-4 w-4 text-[var(--accent)]" aria-hidden="true" />
              <span>Register as an NGO</span>
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[var(--border)] bg-[var(--surface)] py-12 text-sm text-[var(--muted)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-8">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <div className="h-6 w-6 rounded-[6px] bg-[var(--primary)] flex items-center justify-center">
                  <Package className="h-4 w-4 text-white" aria-hidden="true" />
                </div>
                <span className="font-bold text-base text-[var(--text)]">SurplusSync</span>
              </div>
              <p className="text-xs text-[var(--muted)]">
                Food Surplus Redistribution & Logistics Platform
              </p>
            </div>

            <nav className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs sm:text-sm font-medium" aria-label="Footer Navigation">
              <a href="#how-it-works" onClick={(e) => scrollToSection(e, 'how-it-works')} className="hover:text-[var(--text)] transition-colors">
                How it works
              </a>
              <a href="#for-businesses" onClick={(e) => scrollToSection(e, 'for-businesses')} className="hover:text-[var(--text)] transition-colors">
                For businesses
              </a>
              <a href="#for-ngos" onClick={(e) => scrollToSection(e, 'for-ngos')} className="hover:text-[var(--text)] transition-colors">
                For NGOs
              </a>
              <a href="#faq" onClick={(e) => scrollToSection(e, 'faq')} className="hover:text-[var(--text)] transition-colors">
                FAQ
              </a>
              <button
                type="button"
                onClick={onNavigateToLogin}
                className="hover:text-[var(--text)] transition-colors cursor-pointer"
              >
                Sign in
              </button>
              <button
                type="button"
                onClick={() => onNavigateToRegister()}
                className="hover:text-[var(--text)] transition-colors cursor-pointer"
              >
                Register
              </button>
            </nav>
          </div>

          <div className="pt-6 border-t border-[var(--border)] flex flex-col sm:flex-row items-center justify-between gap-4 text-xs">
            <div className="flex items-center space-x-2">
              <Mail className="h-3.5 w-3.5 text-[var(--muted)]" aria-hidden="true" />
              <span>Contact: </span>
              <a
                href={`mailto:${contactEmail}`}
                className="underline hover:text-[var(--text)] transition-colors"
              >
                {contactEmail}
              </a>
            </div>

            <div className="flex items-center space-x-1.5 text-[var(--muted)]">
              <ShieldCheck className="h-3.5 w-3.5 text-[var(--color-success)]" aria-hidden="true" />
              <span>Multi-tenant database isolation & honest zero-data reporting.</span>
            </div>

            <div>
              &copy; {currentYear} SurplusSync. All rights reserved.
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};
