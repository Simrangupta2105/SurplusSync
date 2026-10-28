import React, { useState } from 'react';
import {
  Repeat,
  Lock,
  User,
  Eye,
  EyeOff,
  ArrowRight,
  AlertCircle,
  Layers,
  ShieldCheck,
} from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { dataSource } from '../services';
import { isAuthenticated } from '../services/auth';
import { Button } from '../components/ui/Button';
import { ThemeToggle } from '../components/ThemeToggle';

const loginSchema = z.object({
  username: z.string().min(1, 'Username is required'),
  password: z.string().min(1, 'Password is required'),
  rememberMe: z.boolean(),
});

type LoginFormData = z.infer<typeof loginSchema>;

interface LoginPageProps {
  onLoginSuccess: (user?: unknown) => void;
  onNavigateToRegister: () => void;
  onBackToPlatform?: () => void;
  onNavigate?: (path: string) => void;
  isDark?: boolean;
  onToggleDark?: () => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({
  onLoginSuccess,
  onNavigateToRegister,
  onBackToPlatform,
}) => {
  const [showPassword, setShowPassword] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      username: '',
      password: '',
      rememberMe: true,
    },
  });

  const onSubmit = async (data: LoginFormData) => {
    setServerError(null);
    try {
      const res = await dataSource.login(data.username, data.password, data.rememberMe);
      onLoginSuccess(res.user);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } };
        if (axiosErr.response?.status === 401) {
          setServerError('Invalid username or password. Please verify your credentials.');
        } else if (axiosErr.response?.data?.detail) {
          setServerError(axiosErr.response.data.detail);
        } else {
          setServerError('Unable to connect to the authentication service. Please check your network.');
        }
      } else if (err instanceof Error) {
        setServerError(err.message);
      } else {
        setServerError('An unexpected error occurred during sign in. Please try again.');
      }
    }
  };

  return (
    <div className="min-h-screen w-full flex bg-[var(--bg)] text-[var(--text)] antialiased selection:bg-[var(--primary)] selection:text-[var(--primary-foreground)] transition-colors duration-200">
      {/* Left: Dark Immersive Branded Panel (Desktop Only) */}
      <div className="hidden lg:flex lg:w-1/2 relative bg-[var(--surface)] flex-col justify-between p-12 border-r border-[var(--border)] overflow-hidden">
        {/* Subtle decorative grid and ambient radial glow */}
        <div
          className="absolute inset-0 opacity-10 pointer-events-none"
          style={{
            backgroundImage: `radial-gradient(var(--border) 1px, transparent 1px)`,
            backgroundSize: '24px 24px',
          }}
        />
        <div className="absolute -top-24 -left-24 w-96 h-96 rounded-full bg-[var(--primary)]/10 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -right-24 w-96 h-96 rounded-full bg-[var(--accent)]/10 blur-3xl pointer-events-none" />

        {/* Brand Header */}
        <div className="relative z-10 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-[10px] bg-[var(--primary)] text-white flex items-center justify-center shadow-md">
              <Repeat className="w-5 h-5 stroke-[2.4]" />
            </div>
            <div>
              <span className="font-bold text-lg tracking-tight text-[var(--text)]">
                Surplus<span className="text-[var(--primary)]">Sync</span>
              </span>
              <span className="block text-[11px] text-[var(--muted)] font-medium">
                Food Surplus Redistribution Platform
              </span>
            </div>
          </div>
          <ThemeToggle />
        </div>

        {/* Narrative & Value Proposition */}
        <div className="relative z-10 max-w-lg space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--surface-2)] text-[var(--primary)] border border-[var(--border)] text-xs font-semibold">
            <Layers className="w-3.5 h-3.5" />
            <span>Strict FEFO Rotation &amp; Stock Conservation</span>
          </div>

          <h2 className="text-3xl font-extrabold text-[var(--text)] tracking-tight leading-tight">
            Prevent commercial food waste before it happens.
          </h2>

          <p className="text-sm text-[var(--muted)] leading-relaxed">
            SurplusSync connects hotels, restaurants, and food retailers with verified NGO relief networks, turning near-expiry batches into immediate meals through deterministic shelf-life tracking.
          </p>

          {/* Key Platform Pillars */}
          <div className="grid grid-cols-2 gap-3 pt-2">
            <div className="p-3.5 rounded-[12px] bg-[var(--surface-2)] border border-[var(--border)]">
              <div className="flex items-center gap-2 mb-1.5 text-[var(--primary)]">
                <Layers className="w-4 h-4 shrink-0" />
                <span className="text-xs font-bold text-[var(--text)]">FEFO Logistics</span>
              </div>
              <p className="text-[11px] text-[var(--muted)] leading-relaxed">
                Prioritizes earliest expiry batches across all stock deductions.
              </p>
            </div>
            <div className="p-3.5 rounded-[12px] bg-[var(--surface-2)] border border-[var(--border)]">
              <div className="flex items-center gap-2 mb-1.5 text-[var(--color-success)]">
                <ShieldCheck className="w-4 h-4 shrink-0" />
                <span className="text-xs font-bold text-[var(--text)]">Verified Network</span>
              </div>
              <p className="text-[11px] text-[var(--muted)] leading-relaxed">
                Direct handoff to authenticated NGO partners with audit trails.
              </p>
            </div>
          </div>


        </div>

        {/* Truthful Footer Note */}
        <div className="relative z-10 text-[11px] text-[var(--muted)] flex items-center justify-between border-t border-[var(--border)] pt-4">
          <span>Enterprise Inventory &amp; Claims</span>
          <span>Version 2.0 • Production Quality</span>
        </div>
      </div>

      {/* Right: Roomy Login Form */}
      <div className="w-full lg:w-1/2 flex flex-col justify-center px-6 sm:px-12 xl:px-20 py-12">
        <div className="w-full max-w-md mx-auto space-y-6">
          {/* Mobile Brand Top Header */}
          <div className="lg:hidden flex items-center justify-between pb-4 border-b border-[var(--border)]">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-[8px] bg-[var(--primary)] text-white flex items-center justify-center shadow-xs">
                <Repeat className="w-4 h-4 stroke-[2.2]" />
              </div>
              <span className="font-bold text-base tracking-tight text-[var(--text)]">
                Surplus<span className="text-[var(--primary)]">Sync</span>
              </span>
            </div>
            <ThemeToggle />
          </div>

          {/* Active Session Continuation Banner */}
          {isAuthenticated() && onBackToPlatform && (
            <div className="rounded-[8px] border border-[var(--primary)]/30 bg-[var(--primary)]/10 p-3 text-xs text-[var(--text)] flex items-center justify-between animate-in fade-in duration-150">
              <span className="text-[var(--text)] font-medium">You have an active session.</span>
              <button
                type="button"
                onClick={onBackToPlatform}
                className="font-semibold text-[var(--primary)] hover:underline inline-flex items-center gap-1 cursor-pointer"
              >
                <span>Continue to Dashboard</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Form Header */}
          <div className="space-y-1.5">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[var(--text)]">
              Sign in to your account
            </h1>
            <p className="text-xs sm:text-sm text-[var(--muted)]">
              Enter your assigned username and password to proceed.
            </p>
          </div>

          {/* Server / Auth Error Banner */}
          {serverError && (
            <div
              role="alert"
              className="rounded-[8px] border border-[var(--color-danger-border)] bg-[var(--color-danger-subtle)] p-3.5 text-xs text-[var(--color-danger)] flex items-start gap-2.5 animate-in fade-in duration-150"
            >
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="flex-1 leading-relaxed">{serverError}</div>
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* Username Field */}
            <div className="space-y-1.5">
              <label
                htmlFor="username-input"
                className="block text-xs font-semibold text-[var(--text)]"
              >
                Username
              </label>
              <div className="relative">
                <User className="w-4 h-4 text-[var(--muted)] absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  id="username-input"
                  type="text"
                  autoComplete="username"
                  placeholder="Enter your username"
                  {...register('username')}
                  className={`w-full rounded-[8px] border bg-[var(--surface)] pl-9 pr-3 py-2.5 text-sm text-[var(--text)] placeholder:text-[var(--muted)] transition-all focus:outline-none focus:ring-1 ${
                    errors.username
                      ? 'border-[var(--color-danger)] focus:border-[var(--color-danger)] focus:ring-[var(--color-danger)]'
                      : 'border-[var(--border)] focus:border-[var(--primary)] focus:ring-[var(--primary)]'
                  }`}
                />
              </div>
              {errors.username && (
                <p className="text-[11px] text-[var(--color-danger)] font-medium">
                  {errors.username.message}
                </p>
              )}
            </div>

            {/* Password Field with Show/Hide */}
            <div className="space-y-1.5">
              <label
                htmlFor="password-input"
                className="block text-xs font-semibold text-[var(--text)]"
              >
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-[var(--muted)] absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  id="password-input"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  {...register('password')}
                  className={`w-full rounded-[8px] border bg-[var(--surface)] pl-9 pr-10 py-2.5 text-sm text-[var(--text)] placeholder:text-[var(--muted)] transition-all focus:outline-none focus:ring-1 ${
                    errors.password
                      ? 'border-[var(--color-danger)] focus:border-[var(--color-danger)] focus:ring-[var(--color-danger)]'
                      : 'border-[var(--border)] focus:border-[var(--primary)] focus:ring-[var(--primary)]'
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((p) => !p)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--muted)] hover:text-[var(--text)] transition-colors cursor-pointer"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {errors.password && (
                <p className="text-[11px] text-[var(--color-danger)] font-medium">
                  {errors.password.message}
                </p>
              )}
            </div>

            {/* Remember Me Checkbox (Tokens stored in localStorage if ticked, sessionStorage otherwise) */}
            <div className="flex items-center justify-between pt-1">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  {...register('rememberMe')}
                  className="rounded-[4px] border-[var(--border)] text-[var(--primary)] focus:ring-[var(--primary)]"
                />
                <span className="text-xs text-[var(--muted)]">Remember me on this browser</span>
              </label>
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              variant="primary"
              size="lg"
              isLoading={isSubmitting}
              className="w-full justify-center gap-2 mt-2"
            >
              <span>Sign In to Platform</span>
              <ArrowRight className="w-4 h-4" />
            </Button>
          </form>

          {/* Switch to Register */}
          <div className="text-center text-xs text-[var(--muted)] pt-2 border-t border-[var(--border)]">
            <span>Don't have an organization account yet? </span>
            <button
              type="button"
              onClick={onNavigateToRegister}
              className="font-semibold text-[var(--primary)] hover:underline cursor-pointer"
            >
              Register your organization
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
export default LoginPage;
