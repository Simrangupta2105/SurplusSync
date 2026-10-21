import React, { useState, useMemo } from 'react';
import {
  Bell,
  CheckCheck,
  Clock,
  Sparkles,
  Truck,
  HeartHandshake,
  AlertTriangle,
  ArrowRight,
  Filter,
} from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { Skeleton } from '../components/ui/Skeleton';
import {
  useMarketplaceNotifications,
  useMarkMarketplaceNotificationRead,
  useMarkAllMarketplaceNotificationsRead,
} from '../hooks/useData';
import type { MarketplaceNotification } from '../types';

interface NotificationsPageProps {
  onTriggerToast?: (msg: string) => void;
  onNavigate?: (path: string) => void;
}

export const NotificationsPage: React.FC<NotificationsPageProps> = ({
  onTriggerToast,
  onNavigate,
}) => {
  const [filterUnread, setFilterUnread] = useState(false);
  const { data: notificationsData, isLoading } = useMarketplaceNotifications(filterUnread);
  const markReadMutation = useMarkMarketplaceNotificationRead();
  const markAllReadMutation = useMarkAllMarketplaceNotificationsRead();

  const notifications: MarketplaceNotification[] = useMemo(() => {
    return notificationsData?.results || [];
  }, [notificationsData]);

  const unreadCount = useMemo(() => {
    if (notificationsData?.unread_count !== undefined) {
      return notificationsData.unread_count;
    }
    return notifications.filter((n) => !n.is_read).length;
  }, [notificationsData, notifications]);

  const handleMarkAllRead = () => {
    markAllReadMutation.mutate(undefined, {
      onSuccess: () => {
        onTriggerToast?.('All notifications marked as read');
      },
    });
  };

  const handleNotificationClick = (notif: MarketplaceNotification) => {
    if (!notif.is_read) {
      markReadMutation.mutate(notif.id);
    }
    if (notif.action_url && onNavigate) {
      const cleanPath = notif.action_url.replace(/^#?\/?/, '');
      onNavigate(cleanPath);
    }
  };

  const getNotifIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'match_found':
        return <Sparkles className="w-4 h-4 text-amber-500 shrink-0" />;
      case 'pickup_scheduled':
      case 'driver_dispatched':
        return <Truck className="w-4 h-4 text-blue-500 shrink-0" />;
      case 'donation_approved':
      case 'donation_requested':
        return <HeartHandshake className="w-4 h-4 text-emerald-500 shrink-0" />;
      case 'spoilage_alert':
        return <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0" />;
      default:
        return <Bell className="w-4 h-4 text-[var(--primary)] shrink-0" />;
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-150">
      {/* Header */}
      <PageHeader
        title="Notifications & Alerts Center"
        subtitle="Real-time alerts for surplus matches, scheduled pickups, delivery tracking, and status transitions."
        action={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setFilterUnread(!filterUnread)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] text-xs font-semibold border transition-colors cursor-pointer ${
                filterUnread
                  ? 'border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)] shadow-2xs'
                  : 'border-[var(--border)] bg-[var(--surface-2)] text-[var(--muted)] hover:text-[var(--text)]'
              }`}
            >
              <Filter className="w-3.5 h-3.5" />
              <span>Unread Only ({unreadCount})</span>
            </button>

            {unreadCount > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleMarkAllRead}
                disabled={markAllReadMutation.isPending}
                className="text-xs"
              >
                <CheckCheck className="w-3.5 h-3.5" />
                <span>Mark All Read</span>
              </Button>
            )}
          </div>
        }
      />

      {/* Notifications List */}
      {isLoading ? (
        <div className="space-y-3">
          <Skeleton variant="card" />
          <Skeleton variant="card" />
          <Skeleton variant="card" />
        </div>
      ) : notifications.length === 0 ? (
        <EmptyState
          icon={Bell}
          title="All caught up!"
          description="You don't have any unread notifications or alerts right now. Newly matched surplus donations and dispatch updates will appear here."
          action={
            <Button variant="outline" size="sm" onClick={() => onNavigate?.('marketplace')}>
              Explore Surplus Marketplace
            </Button>
          }
        />
      ) : (
        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] overflow-hidden shadow-2xs divide-y divide-[var(--border)]">
          {notifications.map((notif: MarketplaceNotification) => (
            <div
              key={notif.id}
              onClick={() => handleNotificationClick(notif)}
              className={`p-4 transition-colors cursor-pointer flex items-start justify-between gap-3 ${
                notif.is_read
                  ? 'bg-[var(--surface)] hover:bg-[var(--surface-2)]/50 opacity-75 hover:opacity-100'
                  : 'bg-[var(--primary)]/5 hover:bg-[var(--primary)]/10 border-l-4 border-l-[var(--primary)]'
              }`}
            >
              <div className="flex items-start gap-3 min-w-0">
                <div className="w-8 h-8 rounded-full bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-center shrink-0 mt-0.5">
                  {getNotifIcon(notif.notification_type)}
                </div>

                <div className="space-y-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs font-bold text-[var(--text)] truncate">
                      {notif.title}
                    </h4>
                    {!notif.is_read && (
                      <span className="w-2 h-2 rounded-full bg-[var(--primary)] shrink-0" />
                    )}
                  </div>
                  <p className="text-xs text-[var(--muted)] leading-relaxed">
                    {notif.message}
                  </p>
                  <div className="flex items-center gap-2 text-[10px] text-[var(--muted)] pt-0.5 tabular-nums">
                    <Clock className="w-3 h-3" />
                    <span>
                      {new Date(notif.created_at).toLocaleDateString([], {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                    <span className="capitalize text-[var(--muted)]/60">
                      • {notif.notification_type.replace(/_/g, ' ')}
                    </span>
                  </div>
                </div>
              </div>

              {notif.action_url && (
                <div className="flex items-center gap-1 text-xs font-semibold text-[var(--primary)] shrink-0 pt-1">
                  <span className="hidden sm:inline">View details</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
