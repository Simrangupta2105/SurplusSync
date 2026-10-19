import React from 'react';

export type DeviceMode = 'fluid' | 'laptop' | 'tablet' | 'mobile';

interface DeviceSimulatorFrameProps {
  mode: DeviceMode;
  onModeChange: (mode: DeviceMode) => void;
  children: React.ReactNode;
}

export const DeviceSimulatorFrame: React.FC<DeviceSimulatorFrameProps> = ({
  mode,
  onModeChange,
  children,
}) => {
  const isDevMode = typeof window !== 'undefined' && window.location.search.includes('dev=1');

  // If not explicitly activated with ?dev=1, bypass completely
  if (!isDevMode || mode === 'fluid') {
    return <>{children}</>;
  }

  const dimensions = {
    laptop: { width: '1024px', label: 'Laptop 1024px' },
    tablet: { width: '768px', label: 'Tablet 768px' },
    mobile: { width: '375px', label: 'Mobile 375px' },
  }[mode];

  return (
    <div className="w-full flex flex-col items-center justify-start py-4 px-2 min-h-screen bg-black/60 backdrop-blur-xs transition-all duration-200">
      {/* Dev Mode Floating Switcher */}
      <div className="sticky top-20 z-50 mb-3 bg-[var(--surface)] px-3 py-1.5 rounded-full shadow-xl border border-[var(--border)] flex items-center gap-2 text-xs">
        <span className="font-semibold text-[var(--muted)]">Dev Preview:</span>
        <span className="font-bold text-[var(--primary)]">{dimensions.label}</span>
        <div className="flex items-center gap-1 bg-[var(--surface-2)] p-0.5 rounded-full">
          {(['fluid', 'laptop', 'tablet', 'mobile'] as const).map((m) => (
            <button
              key={m}
              onClick={() => onModeChange(m)}
              className={`px-2 py-0.5 rounded-full text-[11px] font-medium transition-all cursor-pointer ${
                mode === m
                  ? 'bg-[var(--primary)] text-white'
                  : 'text-[var(--muted)] hover:text-[var(--text)]'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      {/* Frame Container */}
      <div
        className="relative bg-[var(--bg)] border border-[var(--border)] shadow-2xl rounded-[12px] overflow-hidden transition-all duration-300"
        style={{
          width: dimensions.width,
          minHeight: '800px',
        }}
      >
        {children}
      </div>
    </div>
  );
};
