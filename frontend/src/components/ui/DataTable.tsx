import React, { useState, useMemo } from 'react';
import {
  ChevronDown,
  ChevronUp,
  ChevronsUpDown,
  ChevronLeft,
  ChevronRight,
  Search,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { EmptyState } from './EmptyState';

export interface Column<T> {
  key?: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  accessor?: (item: T) => React.ReactNode;
  sortable?: boolean;
  className?: string;
  /** Primary label in mobile card view */
  isMobileTitle?: boolean;
  /** Sub-label in mobile card view */
  isMobileSubtitle?: boolean;
  /** Hidden on mobile card view if secondary */
  hideOnMobile?: boolean;
}

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  keyExtractor: (item: T) => string | number;
  searchPlaceholder?: string;
  searchField?: (item: T) => string;
  pageSize?: number;
  emptyTitle?: string;
  emptyDescription?: string;
  isLoading?: boolean;
  onRowClick?: (item: T) => void;
  actionsRenderer?: (item: T) => React.ReactNode;
}

export function DataTable<T>({
  data,
  columns,
  keyExtractor,
  searchPlaceholder = 'Search records...',
  searchField,
  pageSize = 10,
  emptyTitle = 'No records found',
  emptyDescription = 'There are no items matching the current filter criteria.',
  onRowClick,
  actionsRenderer,
}: DataTableProps<T>) {
  const [searchTerm, setSearchTerm] = useState('');
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [currentPage, setCurrentPage] = useState(1);

  // Filter
  const filteredData = useMemo(() => {
    if (!searchTerm.trim() || !searchField) return data;
    const term = searchTerm.toLowerCase();
    return data.filter((item) => searchField(item).toLowerCase().includes(term));
  }, [data, searchTerm, searchField]);

  // Sort
  const sortedData = useMemo(() => {
    if (!sortKey) return filteredData;
    return [...filteredData].sort((a, b) => {
      const valA = (a as Record<string, unknown>)[sortKey];
      const valB = (b as Record<string, unknown>)[sortKey];
      if (valA === valB) return 0;
      if (valA === null || valA === undefined) return 1;
      if (valB === null || valB === undefined) return -1;
      const comp = valA < valB ? -1 : 1;
      return sortDir === 'asc' ? comp : -comp;
    });
  }, [filteredData, sortKey, sortDir]);

  // Paginate
  const totalPages = Math.ceil(sortedData.length / pageSize) || 1;
  const paginatedData = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sortedData.slice(start, start + pageSize);
  }, [sortedData, currentPage, pageSize]);

  const handleSort = (key: string) => {
    if (sortKey === key) {
      if (sortDir === 'asc') setSortDir('desc');
      else {
        setSortKey(null);
        setSortDir('asc');
      }
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const titleCol = columns.find((c) => c.isMobileTitle) || columns[0];
  const subtitleCol = columns.find((c) => c.isMobileSubtitle);

  return (
    <div className="w-full space-y-3">
      {/* Top Search / Filter Bar */}
      {searchField && (
        <div className="flex items-center justify-between gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="w-4 h-4 text-[var(--muted)] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
              placeholder={searchPlaceholder}
              className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] pl-9 pr-3 py-1.5 text-xs text-[var(--text)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)] focus:border-[var(--primary)] transition-all"
            />
          </div>
          <span className="text-xs text-[var(--muted)] tabular-nums shrink-0">
            {sortedData.length} records
          </span>
        </div>
      )}

      {/* Empty State */}
      {paginatedData.length === 0 ? (
        <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-8">
          <EmptyState title={emptyTitle} description={emptyDescription} />
        </div>
      ) : (
        <>
          {/* Desktop & Tablet Table (>= 768px) */}
          <div className="hidden md:block overflow-x-auto rounded-[12px] border border-[var(--border)] bg-[var(--surface)]">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[var(--surface-2)] text-[var(--muted)] font-medium">
                  {columns.map((col) => (
                    <th
                      key={col.key || col.header}
                      onClick={() => col.sortable && col.key && handleSort(col.key)}
                      className={cn(
                        'px-4 py-3 select-none',
                        col.sortable && 'cursor-pointer hover:text-[var(--text)]',
                        col.className
                      )}
                    >
                      <div className="flex items-center gap-1.5">
                        <span>{col.header}</span>
                        {col.sortable && (
                          <span className="text-[var(--muted)]">
                            {sortKey === col.key ? (
                              sortDir === 'asc' ? (
                                <ChevronUp className="w-3.5 h-3.5 text-[var(--primary)]" />
                              ) : (
                                <ChevronDown className="w-3.5 h-3.5 text-[var(--primary)]" />
                              )
                            ) : (
                              <ChevronsUpDown className="w-3.5 h-3.5 opacity-40" />
                            )}
                          </span>
                        )}
                      </div>
                    </th>
                  ))}
                  {actionsRenderer && <th className="px-4 py-3 text-right">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)] text-[var(--text)]">
                {paginatedData.map((item) => {
                  const key = keyExtractor(item);
                  return (
                    <tr
                      key={key}
                      onClick={() => onRowClick && onRowClick(item)}
                      className={cn(
                        'transition-colors duration-150',
                        onRowClick ? 'cursor-pointer hover:bg-[var(--surface-2)]' : 'hover:bg-[var(--surface-2)]/50'
                      )}
                    >
                      {columns.map((col) => (
                        <td key={col.key || col.header} className={cn('px-4 py-3 align-middle', col.className)}>
                          {col.render
                            ? col.render(item)
                            : col.accessor
                            ? col.accessor(item)
                            : String((item as Record<string, unknown>)[col.key || ''] ?? '')}
                        </td>
                      ))}
                      {actionsRenderer && (
                        <td className="px-4 py-3 text-right align-middle shrink-0">
                          {actionsRenderer(item)}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile Card List (< 768px) */}
          <div className="md:hidden space-y-2.5">
            {paginatedData.map((item) => {
              const key = keyExtractor(item);
              return (
                <div
                  key={key}
                  onClick={() => onRowClick && onRowClick(item)}
                  className={cn(
                    'rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-3.5 space-y-2.5 transition-colors',
                    onRowClick && 'cursor-pointer active:bg-[var(--surface-2)]'
                  )}
                >
                  {/* Card Title & Primary Info */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-semibold text-[var(--text)] truncate">
                        {titleCol.render
                          ? titleCol.render(item)
                          : titleCol.accessor
                          ? titleCol.accessor(item)
                          : String((item as Record<string, unknown>)[titleCol.key || ''] ?? '')}
                      </div>
                      {subtitleCol && (
                        <div className="text-[11px] text-[var(--muted)] mt-0.5 truncate">
                          {subtitleCol.render
                            ? subtitleCol.render(item)
                            : subtitleCol.accessor
                            ? subtitleCol.accessor(item)
                            : String((item as Record<string, unknown>)[subtitleCol.key || ''] ?? '')}
                        </div>
                      )}
                    </div>
                    {actionsRenderer && (
                      <div className="shrink-0">{actionsRenderer(item)}</div>
                    )}
                  </div>

                  {/* Other fields grid */}
                  <div className="grid grid-cols-2 gap-2 pt-2 border-t border-[var(--border)] text-[11px]">
                    {columns
                      .filter((c) => c !== titleCol && c !== subtitleCol && !c.hideOnMobile)
                      .map((col) => (
                        <div key={col.key || col.header} className="min-w-0">
                          <span className="text-[var(--muted)] text-[10px] block uppercase tracking-wider">
                            {col.header}
                          </span>
                          <div className="mt-0.5 font-medium text-[var(--text)] truncate">
                            {col.render
                              ? col.render(item)
                              : col.accessor
                              ? col.accessor(item)
                              : String((item as Record<string, unknown>)[col.key || ''] ?? '')}
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-2 px-1 text-xs text-[var(--muted)]">
              <span>
                Page <strong className="text-[var(--text)] tabular-nums">{currentPage}</strong> of{' '}
                <strong className="text-[var(--text)] tabular-nums">{totalPages}</strong>
              </span>

              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="rounded-[8px] p-1.5 border border-[var(--border)] bg-[var(--surface)] text-[var(--text)] hover:bg-[var(--surface-2)] disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
                  aria-label="Previous page"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="rounded-[8px] p-1.5 border border-[var(--border)] bg-[var(--surface)] text-[var(--text)] hover:bg-[var(--surface-2)] disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
                  aria-label="Next page"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
