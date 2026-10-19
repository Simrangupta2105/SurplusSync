import React from 'react';
import { Sparkles, ArrowRight, ShieldCheck, Database } from 'lucide-react';
import { isFeatureLive, getDataSource, type FeatureKey } from '../services';
import { Button } from './ui/Button';

interface FeatureGuardProps {
  feature: FeatureKey;
  featureName: string;
  description?: string;
  children: React.ReactNode;
  onSwitchToDemo?: () => void;
}

export const FeatureGuard: React.FC<FeatureGuardProps> = ({
  feature,
  featureName,
  description,
  children,
  onSwitchToDemo,
}) => {
  const currentMode = getDataSource().mode;
  const isAvailable = currentMode === 'demo' || isFeatureLive(feature);

  if (isAvailable) {
    return <>{children}</>;
  }

  return (
    <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-8 sm:p-12 text-center max-w-xl mx-auto my-8 space-y-4">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[var(--primary)]/10 text-[var(--primary)]">
        <Sparkles className="h-6 w-6" />
      </div>

      <div className="space-y-1.5">
        <div className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-info-border)] bg-[var(--color-info-bg)] px-2.5 py-0.5 text-xs font-semibold text-[var(--color-info-text)]">
          <ShieldCheck className="h-3.5 w-3.5" />
          <span>Coming Soon in Live Mode</span>
        </div>
        <h3 className="text-xl font-semibold text-[var(--text)] tracking-tight">
          {featureName}
        </h3>
        <p className="text-sm text-[var(--muted)] leading-relaxed">
          {description ||
            'This capability is currently in development for the production API backend. You can test and experience the full workflow right now in Demo Mode.'}
        </p>
      </div>

      {onSwitchToDemo && (
        <div className="pt-2">
          <Button
            variant="primary"
            onClick={onSwitchToDemo}
            className="gap-2 mx-auto shadow-xs"
          >
            <Database className="h-4 w-4" />
            <span>Switch to Demo Mode to Preview</span>
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
};
