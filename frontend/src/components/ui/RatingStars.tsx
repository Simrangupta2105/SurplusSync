import React, { useState } from 'react';
import { Star } from 'lucide-react';
import { cn } from '../../lib/utils';

interface RatingStarsProps {
  value?: number;
  rating?: number;
  onChange?: (rating: number) => void;
  max?: number;
  size?: 'sm' | 'md' | 'lg';
  showNumber?: boolean;
  className?: string;
  readOnly?: boolean;
}

export const RatingStars: React.FC<RatingStarsProps> = ({
  value,
  rating,
  onChange,
  max = 5,
  size = 'md',
  showNumber = false,
  className,
  readOnly = false,
}) => {
  const currentVal = value ?? rating ?? 0;
  const [hoverValue, setHoverValue] = useState<number | null>(null);

  const isInteractive = !readOnly && !!onChange;
  const displayRating = hoverValue !== null ? hoverValue : currentVal;


  const sizeClasses = {
    sm: 'w-3.5 h-3.5',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  };

  return (
    <div className={cn('inline-flex items-center gap-1', className)}>
      <div className="flex items-center gap-0.5" role={isInteractive ? 'radiogroup' : undefined}>
        {Array.from({ length: max }, (_, i) => {
          const starIndex = i + 1;
          const isFilled = displayRating >= starIndex;
          const isHalf = !isFilled && displayRating >= starIndex - 0.5;

          return (
            <button
              key={starIndex}
              type="button"
              disabled={!isInteractive}
              onClick={() => isInteractive && onChange(starIndex)}
              onMouseEnter={() => isInteractive && setHoverValue(starIndex)}
              onMouseLeave={() => isInteractive && setHoverValue(null)}
              className={cn(
                'transition-transform',
                isInteractive ? 'cursor-pointer hover:scale-115 focus:outline-none' : 'cursor-default'
              )}
              aria-label={`${starIndex} of ${max} stars`}
            >
              <Star
                className={cn(
                  sizeClasses[size],
                  isFilled
                    ? 'fill-[var(--color-warning)] text-[var(--color-warning)]'
                    : isHalf
                    ? 'fill-[var(--color-warning-subtle)] text-[var(--color-warning)]'
                    : 'text-[var(--border)] fill-transparent'
                )}
              />
            </button>
          );
        })}
      </div>
      {showNumber && (
        <span className="text-xs font-semibold tabular-nums text-[var(--text)] ml-1">
          {currentVal.toFixed(1)}
        </span>
      )}

    </div>
  );
};
