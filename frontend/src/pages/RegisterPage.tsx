import React, { useState } from 'react';
import {
  Repeat,
  Lock,
  User,
  Mail,
  Building2,
  HeartHandshake,
  MapPin,
  Phone,
  Eye,
  EyeOff,
  ArrowRight,
  ShieldCheck,
  AlertCircle,
  Clock,
  CheckCircle2,
  Navigation,
} from 'lucide-react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { dataSource } from '../services';
import { Button } from '../components/ui/Button';
import { ThemeToggle } from '../components/ThemeToggle';
import type { OrganizationType } from '../types';

const registerSchema = z.object({
  org_type: z.enum(['BUSINESS', 'NGO']),
  username: z
    .string()
    .min(3, 'Username must be at least 3 characters')
    .max(150, 'Username cannot exceed 150 characters'),
  email: z.string().email('Please enter a valid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  org_name: z
    .string()
    .min(2, 'Organization name is required')
    .max(200, 'Organization name cannot exceed 200 characters'),
  address: z.string().optional(),
  phone: z.string().optional(),
});

type RegisterFormData = z.infer<typeof registerSchema>;

interface RegisterPageProps {
  onRegisterSuccess: (user?: unknown) => void;
  onNavigateToLogin: () => void;
  onBackToPlatform: () => void;
  onNavigate?: (path: string) => void;
  isDark?: boolean;
  onToggleDark?: () => void;
}

export const RegisterPage: React.FC<RegisterPageProps> = ({
  onRegisterSuccess,
  onNavigateToLogin,
}) => {
  const [showPassword, setShowPassword] = useState(false);
  const [selectedType, setSelectedType] = useState<OrganizationType>('BUSINESS');
  const [locationStatus, setLocationStatus] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      org_type: 'BUSINESS',
      username: '',
      email: '',
      password: '',
      org_name: '',
      address: '',
      phone: '',
    },
  });

  const handleSelectType = (type: OrganizationType) => {
    setSelectedType(type);
    setValue('org_type', type);
  };

  const handleUseLocation = () => {
    setLocationStatus('Locating...');
    if (!navigator.geolocation) {
      setLocationStatus('Geolocation is not supported by your browser.');
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        const coordsStr = `${latitude.toFixed(4)}, ${longitude.toFixed(4)} (Current Coordinates)`;
        setValue('address', coordsStr);
        setLocationStatus(`Location detected: ${latitude.toFixed(3)}°N, ${longitude.toFixed(3)}°E`);
      },
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          setLocationStatus('Location access permission was denied. Please enter your address manually.');
        } else {
          setLocationStatus('Unable to retrieve location. Please enter your address manually.');
        }
      },
      { timeout: 10000 }
    );
  };

  const onSubmit = async (data: RegisterFormData) => {
    setServerError(null);
    try {
      const res = await dataSource.register({
        username: data.username.trim(),
        email: data.email.trim(),
        password: data.password,
        org_name: data.org_name.trim(),
        org_type: data.org_type,
        address: data.address?.trim() || '',
        phone: data.phone?.trim() || '',
      });
      onRegisterSuccess(res);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: Record<string, string | string[]> } };
        const dataErrors = axiosErr.response?.data;
        if (dataErrors) {
          const firstKey = Object.keys(dataErrors)[0];
          const val = dataErrors[firstKey];
          const msg = Array.isArray(val) ? val[0] : String(val);
          setServerError(`${firstKey}: ${msg}`);
          return;
        }
      }
      if (err instanceof Error) {
        setServerError(err.message);
      } else {
        setServerError('Registration failed. Please check your inputs and try again.');
      }
    }
  };

  return (
    <div className="min-h-screen w-full flex bg-[var(--bg)] text-[var(--text)] antialiased selection:bg-[var(--primary)] selection:text-[var(--primary-foreground)] transition-colors duration-200">
      {/* Left: Dark Immersive Branded Panel (Desktop Only) */}
      <div className="hidden lg:flex lg:w-5/12 relative bg-[var(--surface)] flex-col justify-between p-12 border-r border-[var(--border)] overflow-hidden">
        {/* Subtle decorative grid and ambient glow */}
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

        {/* Narrative */}
        <div className="relative z-10 max-w-lg space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--surface-2)] text-[var(--primary)] border border-[var(--border)] text-xs font-semibold">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Admin-Verified Relief Network</span>
          </div>

          <h2 className="text-3xl font-extrabold text-[var(--text)] tracking-tight leading-tight">
            Register your organization on SurplusSync.
          </h2>

          <p className="text-sm text-[var(--muted)] leading-relaxed">
            Whether you operate a commercial kitchen with edible food surplus or a charitable trust distributing hot meals to those in need, join our coordinated platform.
          </p>

          {/* Key Platform Pillars */}
          <div className="grid grid-cols-2 gap-3 pt-2">
            <div className="p-3.5 rounded-[12px] bg-[var(--surface-2)] border border-[var(--border)]">
              <div className="flex items-center gap-2 mb-1.5 text-[var(--primary)]">
                <Building2 className="w-4 h-4 shrink-0" />
                <span className="text-xs font-bold text-[var(--text)]">Business Hub</span>
              </div>
              <p className="text-[11px] text-[var(--muted)] leading-relaxed">
                Log batches, barcode scan, and track expiry horizons automatically.
              </p>
            </div>
            <div className="p-3.5 rounded-[12px] bg-[var(--surface-2)] border border-[var(--border)]">
              <div className="flex items-center gap-2 mb-1.5 text-[var(--color-success)]">
                <ShieldCheck className="w-4 h-4 shrink-0" />
                <span className="text-xs font-bold text-[var(--text)]">Verified NGOs</span>
              </div>
              <p className="text-[11px] text-[var(--muted)] leading-relaxed">
                Audited charity networks for timely, accountable food rescues.
              </p>
            </div>
          </div>
        </div>

        <div className="relative z-10 text-[11px] text-[var(--muted)] flex items-center justify-between border-t border-[var(--border)] pt-4">
          <span>Enterprise Inventory &amp; Claims</span>
          <span>Version 2.0 • Production Quality</span>
        </div>
      </div>

      {/* Right: Roomy Registration Form */}
      <div className="w-full lg:w-7/12 flex flex-col justify-center px-6 sm:px-12 xl:px-16 py-10 overflow-y-auto">
        <div className="w-full max-w-xl mx-auto space-y-6">
          {/* Mobile Header */}
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

          <div className="space-y-1">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[var(--text)]">
              Create Organization Account
            </h1>
            <p className="text-xs sm:text-sm text-[var(--muted)]">
              Select your organization type and enter your administrator details.
            </p>
          </div>

          {/* Selectable Account Type Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            <button
              type="button"
              onClick={() => handleSelectType('BUSINESS')}
              className={`p-4 rounded-[12px] border text-left transition-all cursor-pointer select-none flex flex-col justify-between ${
                selectedType === 'BUSINESS'
                  ? 'border-[var(--primary)] bg-[var(--surface-2)] shadow-sm ring-1 ring-[var(--primary)]'
                  : 'border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-2)]'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="w-9 h-9 rounded-[8px] bg-[var(--primary)]/10 text-[var(--primary)] flex items-center justify-center">
                  <Building2 className="w-5 h-5" />
                </div>
                {selectedType === 'BUSINESS' && (
                  <CheckCircle2 className="w-4 h-4 text-[var(--primary)]" />
                )}
              </div>
              <div>
                <p className="text-sm font-bold text-[var(--text)]">Business / Donor</p>
                <p className="text-[11px] text-[var(--muted)] mt-1 leading-snug">
                  Hotels, banquets, and supermarkets tracking stock and redistributing surplus food.
                </p>
              </div>
            </button>

            <button
              type="button"
              onClick={() => handleSelectType('NGO')}
              className={`p-4 rounded-[12px] border text-left transition-all cursor-pointer select-none flex flex-col justify-between ${
                selectedType === 'NGO'
                  ? 'border-[var(--accent)] bg-[var(--surface-2)] shadow-sm ring-1 ring-[var(--accent)]'
                  : 'border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-2)]'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="w-9 h-9 rounded-[8px] bg-[var(--accent)]/10 text-[var(--accent)] flex items-center justify-center">
                  <HeartHandshake className="w-5 h-5" />
                </div>
                {selectedType === 'NGO' && (
                  <CheckCircle2 className="w-4 h-4 text-[var(--accent)]" />
                )}
              </div>
              <div>
                <p className="text-sm font-bold text-[var(--text)]">NGO / Charity Partner</p>
                <p className="text-[11px] text-[var(--muted)] mt-1 leading-snug">
                  Community feeding networks and hunger relief trusts claiming available food.
                </p>
              </div>
            </button>
          </div>

          {/* Mandatory NGO Verification Note */}
          {selectedType === 'NGO' && (
            <div className="rounded-[8px] border border-[var(--color-warning-border)] bg-[var(--color-warning-subtle)] p-3 text-xs text-[var(--color-warning)] flex items-start gap-2.5 animate-in fade-in duration-150">
              <Clock className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="flex-1 leading-relaxed">
                <strong>Admin Verification Required:</strong> In accordance with food safety standards, newly registered NGO organizations must be verified by an administrator before they can claim perishable surplus batches.
              </div>
            </div>
          )}

          {/* Server Error Banner */}
          {serverError && (
            <div
              role="alert"
              className="rounded-[8px] border border-[var(--color-danger-border)] bg-[var(--color-danger-subtle)] p-3.5 text-xs text-[var(--color-danger)] flex items-start gap-2.5 animate-in fade-in duration-150"
            >
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="flex-1 leading-relaxed">{serverError}</div>
            </div>
          )}

          {/* Registration Form */}
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* Organization Name */}
            <div className="space-y-1">
              <label htmlFor="reg-org-name" className="block text-xs font-semibold text-[var(--text)]">
                Organization Name <span className="text-[var(--color-danger)]">*</span>
              </label>
              <div className="relative">
                <Building2 className="w-4 h-4 text-[var(--muted)] absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  id="reg-org-name"
                  type="text"
                  placeholder="e.g. Indiranagar Hospitality Group or Robin Hood Army BLR"
                  {...register('org_name')}
                  className={`w-full rounded-[8px] border bg-[var(--surface)] pl-9 pr-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--muted)] transition-all focus:outline-none focus:ring-1 ${
                    errors.org_name
                      ? 'border-[var(--color-danger)] focus:ring-[var(--color-danger)]'
                      : 'border-[var(--border)] focus:border-[var(--primary)] focus:ring-[var(--primary)]'
                  }`}
                />
              </div>
              {errors.org_name && (
                <p className="text-[11px] text-[var(--color-danger)]">{errors.org_name.message}</p>
              )}
            </div>

            {/* Username & Email in 2 columns */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label htmlFor="reg-username" className="block text-xs font-semibold text-[var(--text)]">
                  Admin Username <span className="text-[var(--color-danger)]">*</span>
                </label>
                <div className="relative">
                  <User className="w-4 h-4 text-[var(--muted)] absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    id="reg-username"
                    type="text"
                    autoComplete="username"
                    placeholder="e.g. rohit_ops"
                    {...register('username')}
                    className={`w-full rounded-[8px] border bg-[var(--surface)] pl-9 pr-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--muted)] transition-all focus:outline-none focus:ring-1 ${
                      errors.username
                        ? 'border-[var(--color-danger)] focus:ring-[var(--color-danger)]'
                        : 'border-[var(--border)] focus:border-[var(--primary)] focus:ring-[var(--primary)]'
                    }`}
                  />
                </div>
                {errors.username && (
                  <p className="text-[11px] text-[var(--color-danger)]">{errors.username.message}</p>
                )}
              </div>

              <div className="space-y-1">
                <label htmlFor="reg-email" className="block text-xs font-semibold text-[var(--text)]">
                  Work Email <span className="text-[var(--color-danger)]">*</span>
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-[var(--muted)] absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    id="reg-email"
                    type="email"
                    autoComplete="email"
                    placeholder="contact@organization.in"
                    {...register('email')}
                    className={`w-full rounded-[8px] border bg-[var(--surface)] pl-9 pr-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--muted)] transition-all focus:outline-none focus:ring-1 ${
                      errors.email
                        ? 'border-[var(--color-danger)] focus:ring-[var(--color-danger)]'
                        : 'border-[var(--border)] focus:border-[var(--primary)] focus:ring-[var(--primary)]'
                    }`}
                  />
                </div>
                {errors.email && (
                  <p className="text-[11px] text-[var(--color-danger)]">{errors.email.message}</p>
                )}
              </div>
            </div>

            {/* Password & Phone */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label htmlFor="reg-password" className="block text-xs font-semibold text-[var(--text)]">
                  Password (min 8 chars) <span className="text-[var(--color-danger)]">*</span>
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-[var(--muted)] absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    id="reg-password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    placeholder="Minimum 8 characters"
                    {...register('password')}
                    className={`w-full rounded-[8px] border bg-[var(--surface)] pl-9 pr-10 py-2 text-sm text-[var(--text)] placeholder:text-[var(--muted)] transition-all focus:outline-none focus:ring-1 ${
                      errors.password
                        ? 'border-[var(--color-danger)] focus:ring-[var(--color-danger)]'
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
                  <p className="text-[11px] text-[var(--color-danger)]">{errors.password.message}</p>
                )}
              </div>

              <div className="space-y-1">
                <label htmlFor="reg-phone" className="block text-xs font-semibold text-[var(--text)]">
                  Phone Contact (Optional)
                </label>
                <div className="relative">
                  <Phone className="w-4 h-4 text-[var(--muted)] absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    id="reg-phone"
                    type="tel"
                    placeholder="e.g. +91 9876543210"
                    {...register('phone')}
                    className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface)] pl-9 pr-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--muted)] transition-all focus:outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)]"
                  />
                </div>
              </div>
            </div>

            {/* Address with "Use My Location" Button */}
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label htmlFor="reg-address" className="block text-xs font-semibold text-[var(--text)]">
                  Physical Address / Operating Hub
                </label>
                <button
                  type="button"
                  onClick={handleUseLocation}
                  className="flex items-center gap-1 text-[11px] font-semibold text-[var(--primary)] hover:underline cursor-pointer"
                >
                  <Navigation className="w-3 h-3" />
                  <span>Use my current location</span>
                </button>
              </div>

              <div className="relative">
                <MapPin className="w-4 h-4 text-[var(--muted)] absolute left-3 top-3" />
                <textarea
                  id="reg-address"
                  rows={2}
                  placeholder="Street address, city, and state"
                  {...register('address')}
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface)] pl-9 pr-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--muted)] transition-all focus:outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)]"
                />
              </div>

              {locationStatus && (
                <p className="text-[11px] text-[var(--muted)] font-medium">
                  {locationStatus}
                </p>
              )}
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              variant="primary"
              size="lg"
              isLoading={isSubmitting}
              className="w-full justify-center gap-2 mt-2"
            >
              <span>Complete Organization Registration</span>
              <ArrowRight className="w-4 h-4" />
            </Button>
          </form>

          {/* Switch to Login */}
          <div className="text-center text-xs text-[var(--muted)] pt-3 border-t border-[var(--border)]">
            <span>Already have an authorized account? </span>
            <button
              type="button"
              onClick={onNavigateToLogin}
              className="font-semibold text-[var(--primary)] hover:underline cursor-pointer"
            >
              Sign in here
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
export default RegisterPage;
