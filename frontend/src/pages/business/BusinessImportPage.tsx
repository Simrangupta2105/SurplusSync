import React, { useState, useRef, useEffect } from 'react';
import {
  UploadCloud,
  FileText,
  Download,
  AlertCircle,
  AlertTriangle,
  RefreshCw,
  FileCheck,
  CheckCircle2,
  Clock,
  ExternalLink,
  ChevronRight,
} from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { PageHeader } from '../../components/ui/PageHeader';
import { StatusBadge, type StatusVariant } from '../../components/ui/StatusBadge';
import { useUploadCsv, useImportJobs, useImportJob } from '../../hooks/useData';
import type { ImportJob } from '../../types';

interface BusinessImportPageProps {
  onTriggerToast: (msg: string) => void;
  onNavigate: (path: string) => void;
}

function getJobStatusVariant(status: string): StatusVariant {
  switch (status) {
    case 'DONE':
      return 'success';
    case 'PARTIAL':
      return 'warning';
    case 'PROCESSING':
      return 'info';
    case 'FAILED':
    case 'CANCELLED':
      return 'danger';
    case 'PENDING':
    default:
      return 'neutral';
  }
}

export const BusinessImportPage: React.FC<BusinessImportPageProps> = ({
  onTriggerToast,
  onNavigate,
}) => {
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [activeJobId, setActiveJobId] = useState<number | null>(null);
  const [selectedJobForDetail, setSelectedJobForDetail] = useState<ImportJob | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadMutation = useUploadCsv();
  const { data: importJobs = [], refetch: refetchJobs } = useImportJobs();

  // Poll active job if currently pending or processing
  const { data: polledJob } = useImportJob(activeJobId, {
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 1500;
      if (data.status === 'PENDING' || data.status === 'PROCESSING') {
        return 1500;
      }
      return false;
    },
  });

  // Track completion of active polled job for toast notifications and refetch
  const completedJobRef = useRef<number | null>(null);
  useEffect(() => {
    if (polledJob && (polledJob.status === 'DONE' || polledJob.status === 'PARTIAL' || polledJob.status === 'FAILED')) {
      if (activeJobId === polledJob.id && completedJobRef.current !== polledJob.id) {
        completedJobRef.current = polledJob.id;
        refetchJobs();
        if (polledJob.status === 'DONE') {
          onTriggerToast(`Import complete: ${polledJob.rows_ok} batches successfully ingested`);
        } else if (polledJob.status === 'PARTIAL') {
          onTriggerToast(`Import completed with warnings: ${polledJob.rows_ok} ok, ${polledJob.rows_failed} failed`);
        } else {
          onTriggerToast(`Import failed: ${polledJob.error_message || 'Validation errors encountered'}`);
        }
      }
    }
  }, [polledJob, activeJobId, onTriggerToast, refetchJobs]);

  const activeJob = polledJob || (activeJobId ? importJobs.find((j) => j.id === activeJobId) : null);
  const displayedJob = selectedJobForDetail || (activeJob?.status === 'DONE' || activeJob?.status === 'PARTIAL' || activeJob?.status === 'FAILED' ? activeJob : importJobs[0] || null);

  // Detect worker downtime: either active job flagged or any pending job flagged by serializer/demo
  const isWorkerDown = Boolean(
    activeJob?.worker_may_be_down ||
    importJobs.some((j) => Boolean(j.worker_may_be_down))
  );

  // Template Download Helper
  const handleDownloadTemplate = () => {
    const csvContent =
      'product_name,sku,barcode,category,quantity,unit,cost_price,selling_price,manufacturing_date,expiry_date\n' +
      'Nandini Toned Fresh Milk 500ml,MILK-NAN-500,8901030865421,Dairy,50,units,24.00,27.00,2026-10-12,2026-10-16\n' +
      'Milky Mist Fresh Paneer 200g,PAN-MM-200,8902040987123,Dairy,30,units,85.00,105.00,2026-10-10,2026-10-25\n' +
      'Fresh Robusta Bananas 1kg,PROD-BAN-ROB,8903050123456,Produce,40,kg,35.00,50.00,2026-10-13,2026-10-17\n';

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'surplussync_inventory_template.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    onTriggerToast('Downloaded inventory CSV template');
  };

  const handleFileSelect = (file: File) => {
    if (!file.name.endsWith('.csv')) {
      onTriggerToast('Please select a valid .csv file');
      return;
    }
    setSelectedFile(file);
  };

  const handleUpload = () => {
    if (!selectedFile) return;

    uploadMutation.mutate(selectedFile, {
      onSuccess: (result) => {
        setSelectedFile(null);
        if (result.status === 'PENDING' || result.status === 'PROCESSING') {
          setActiveJobId(result.id);
          onTriggerToast('File uploaded. Queued for asynchronous processing.');
        } else {
          setSelectedJobForDetail(result);
          onTriggerToast(`Processed manifest: ${result.rows_ok} batches imported`);
        }
        refetchJobs();
      },
      onError: (err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Manifest import failed';
        onTriggerToast(msg);
      },
    });
  };

  // Compute live progress percentage
  let progressPercent = 0;
  if (activeJob) {
    if (activeJob.total_rows && activeJob.total_rows > 0) {
      const processed = activeJob.processed_rows || (activeJob.rows_ok + activeJob.rows_failed) || 0;
      progressPercent = Math.min(100, Math.round((processed / activeJob.total_rows) * 100));
    } else if (activeJob.status === 'PROCESSING') {
      progressPercent = 45;
    } else if (activeJob.status === 'PENDING') {
      progressPercent = 10;
    }
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <PageHeader
        title="CSV Manifest Ingestion"
        description="Bulk import inventory batches, SKU definitions, and expiry horizons with asynchronous queuing and validation diagnostics."
        action={
          <Button
            variant="outline"
            size="sm"
            onClick={handleDownloadTemplate}
            className="gap-1.5"
          >
            <Download className="w-4 h-4" />
            <span>Download CSV Template</span>
          </Button>
        }
      />

      {/* Worker Downtime Warning Banner */}
      {isWorkerDown && (
        <div
          role="alert"
          className="rounded-[12px] border border-amber-500/30 bg-amber-500/10 p-4 sm:p-5 flex items-start gap-3.5 text-amber-600 dark:text-amber-400 animate-in fade-in duration-200"
        >
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs">
            <h4 className="font-semibold text-sm">Background Worker May Be Inactive</h4>
            <p className="leading-relaxed">
              An import job has been waiting in the queue for over 2 minutes without progress.
              Please ensure the Django-Q2 background cluster is active in your terminal:{' '}
              <code className="px-1.5 py-0.5 rounded bg-black/10 dark:bg-white/10 font-mono text-[11px]">
                python manage.py qcluster
              </code>
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Upload Zone (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                handleFileSelect(e.dataTransfer.files[0]);
              }
            }}
            onClick={() => fileInputRef.current?.click()}
            className={`rounded-[12px] border-2 border-dashed p-8 text-center transition-all cursor-pointer flex flex-col items-center justify-center min-h-[260px] ${
              dragOver
                ? 'border-[var(--primary)] bg-[var(--primary)]/5'
                : 'border-[var(--border)] bg-[var(--surface)] hover:border-[var(--primary)]/50'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  handleFileSelect(e.target.files[0]);
                }
              }}
            />

            <div className="w-12 h-12 rounded-full bg-[var(--surface-2)] text-[var(--primary)] flex items-center justify-center mb-3.5 border border-[var(--border)]">
              <UploadCloud className="w-6 h-6" />
            </div>

            <p className="text-sm font-semibold text-[var(--text)]">
              {selectedFile ? selectedFile.name : 'Click or drag ERP manifest CSV here'}
            </p>
            <p className="text-xs text-[var(--muted)] mt-1 max-w-sm">
              Supports standard tabular headers: product_name, sku, barcode, quantity, unit, expiry_date
            </p>

            {selectedFile && (
              <div className="mt-4 flex items-center gap-2 px-3 py-1.5 rounded-[6px] bg-[var(--surface-2)] border border-[var(--border)] text-xs text-[var(--text)]">
                <FileText className="w-4 h-4 text-[var(--primary)]" />
                <span>{(selectedFile.size / 1024).toFixed(1)} KB</span>
              </div>
            )}
          </div>

          {/* Active Job Processing / Live Progress Bar */}
          {activeJob && (activeJob.status === 'PENDING' || activeJob.status === 'PROCESSING') && (
            <div className="rounded-[10px] border border-[var(--primary)]/30 bg-[var(--surface)] p-4 space-y-2.5 animate-in fade-in">
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-[var(--text)] flex items-center gap-2">
                  <RefreshCw className="w-3.5 h-3.5 text-[var(--primary)] animate-spin" />
                  <span>
                    {activeJob.status === 'PENDING' ? 'Waiting in background queue...' : 'Processing Ingestion Task...'}
                  </span>
                </span>
                <span className="tabular-nums font-semibold text-[var(--primary)]">
                  {activeJob.total_rows && activeJob.total_rows > 0
                    ? `${activeJob.processed_rows || 0} / ${activeJob.total_rows} rows (${progressPercent}%)`
                    : `${progressPercent}%`}
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-[var(--surface-2)] overflow-hidden">
                <div
                  className="h-full bg-[var(--primary)] transition-all duration-300"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
              <p className="text-[11px] text-[var(--muted)]">
                Manifest file: <span className="font-mono text-[var(--text)]">{activeJob.file}</span> (Job #{activeJob.id})
              </p>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-3">
            {selectedFile && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedFile(null)}
              >
                Clear
              </Button>
            )}
            <Button
              variant="primary"
              size="md"
              disabled={!selectedFile || uploadMutation.isPending || !!(activeJob && (activeJob.status === 'PENDING' || activeJob.status === 'PROCESSING'))}
              onClick={handleUpload}
              className="gap-2 text-xs"
            >
              {uploadMutation.isPending ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Uploading...</span>
                </>
              ) : (
                <>
                  <FileCheck className="w-4 h-4" />
                  <span>Import Manifest</span>
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Right: Selected Results Breakdown (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
              <h3 className="text-sm font-semibold text-[var(--text)]">
                Ingestion Details
              </h3>
              {displayedJob && (
                <StatusBadge variant={getJobStatusVariant(displayedJob.status)} dot size="sm">
                  {displayedJob.status}
                </StatusBadge>
              )}
            </div>

            {displayedJob ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3.5 rounded-[8px] bg-[var(--color-success-subtle)] border border-[var(--color-success-border)] text-center">
                    <p className="text-2xl font-bold tabular-nums text-[var(--color-success)]">
                      {displayedJob.rows_ok}
                    </p>
                    <p className="text-[11px] font-medium text-[var(--color-success)] mt-0.5">
                      Batches Ingested
                    </p>
                  </div>
                  <div className="p-3.5 rounded-[8px] bg-[var(--color-danger-subtle)] border border-[var(--color-danger-border)] text-center">
                    <p className="text-2xl font-bold tabular-nums text-[var(--color-danger)]">
                      {displayedJob.rows_failed}
                    </p>
                    <p className="text-[11px] font-medium text-[var(--color-danger)] mt-0.5">
                      Failed Records
                    </p>
                  </div>
                </div>

                <div className="space-y-1.5 text-xs text-[var(--muted)]">
                  <div className="flex items-center justify-between">
                    <span>Job ID:</span>
                    <span className="font-mono font-medium text-[var(--text)]">#{displayedJob.id}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>File Name:</span>
                    <span className="font-mono text-[var(--text)] truncate max-w-[200px]">{displayedJob.file}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Total Rows:</span>
                    <span className="font-semibold text-[var(--text)]">
                      {displayedJob.total_rows || (displayedJob.rows_ok + displayedJob.rows_failed)}
                    </span>
                  </div>
                  {displayedJob.started_at && (
                    <div className="flex items-center justify-between">
                      <span>Started At:</span>
                      <span className="text-[var(--text)]">
                        {new Date(displayedJob.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  )}
                  {displayedJob.finished_at && (
                    <div className="flex items-center justify-between">
                      <span>Completed At:</span>
                      <span className="text-[var(--text)]">
                        {new Date(displayedJob.finished_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-end pt-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onNavigate('inventory')}
                    className="text-xs text-[var(--primary)] hover:underline p-0 h-auto gap-1"
                  >
                    <span>Inspect In Inventory</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </Button>
                </div>

                {/* Failed Rows Table */}
                {displayedJob.error_report && displayedJob.error_report.length > 0 && (
                  <div className="space-y-2 pt-3 border-t border-[var(--border)]">
                    <p className="text-xs font-semibold text-[var(--color-danger)] flex items-center gap-1.5">
                      <AlertCircle className="w-4 h-4" />
                      Failed Rows Breakdown ({displayedJob.error_report.length})
                    </p>
                    <div className="max-h-48 overflow-y-auto rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)]">
                      <table className="w-full text-left text-[11px]">
                        <thead className="bg-[var(--surface)] text-[var(--muted)] border-b border-[var(--border)] sticky top-0">
                          <tr>
                            <th className="p-2 font-semibold">Row</th>
                            <th className="p-2 font-semibold">Error Reason</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--border)]">
                          {displayedJob.error_report.map((err, idx) => (
                            <tr key={idx} className="hover:bg-[var(--surface)]/50">
                              <td className="p-2 font-mono tabular-nums font-bold text-[var(--color-danger)]">
                                #{err.row || idx + 1}
                              </td>
                              <td className="p-2 text-[var(--text)]">{err.error}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="py-10 text-center space-y-2">
                <FileText className="w-8 h-8 text-[var(--muted)] mx-auto opacity-50" />
                <p className="text-xs text-[var(--muted)]">
                  Select and ingest a CSV file or inspect a previous import below.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent Imports Section */}
      <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
          <div>
            <h3 className="text-sm font-semibold text-[var(--text)] flex items-center gap-2">
              <Clock className="w-4 h-4 text-[var(--primary)]" />
              <span>Recent Import Jobs</span>
            </h3>
            <p className="text-xs text-[var(--muted)] mt-0.5">
              Historical manifests ingested through batch ingestion and background queues.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetchJobs()}
            className="text-xs gap-1.5"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </Button>
        </div>

        {importJobs.length > 0 ? (
          <div className="overflow-x-auto rounded-[8px] border border-[var(--border)]">
            <table className="w-full text-left text-xs">
              <thead className="bg-[var(--surface-2)] text-[var(--muted)] border-b border-[var(--border)]">
                <tr>
                  <th className="p-3 font-semibold">ID</th>
                  <th className="p-3 font-semibold">File Name</th>
                  <th className="p-3 font-semibold">Status</th>
                  <th className="p-3 font-semibold">Processed / Total</th>
                  <th className="p-3 font-semibold">Success / Failed</th>
                  <th className="p-3 font-semibold">Date</th>
                  <th className="p-3 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {importJobs.map((job) => {
                  const isSelected = displayedJob?.id === job.id;
                  const total = job.total_rows || (job.rows_ok + job.rows_failed);
                  const processed = job.processed_rows !== undefined ? job.processed_rows : total;
                  return (
                    <tr
                      key={job.id}
                      className={`transition-colors cursor-pointer ${
                        isSelected ? 'bg-[var(--primary)]/10' : 'hover:bg-[var(--surface-2)]/60'
                      }`}
                      onClick={() => setSelectedJobForDetail(job)}
                    >
                      <td className="p-3 font-mono font-medium text-[var(--muted)]">#{job.id}</td>
                      <td className="p-3 font-medium text-[var(--text)] flex items-center gap-2">
                        <FileText className="w-4 h-4 text-[var(--primary)] shrink-0" />
                        <span className="truncate max-w-[180px]">{job.file}</span>
                      </td>
                      <td className="p-3">
                        <StatusBadge variant={getJobStatusVariant(job.status)} dot size="sm">
                          {job.status}
                        </StatusBadge>
                      </td>
                      <td className="p-3 tabular-nums font-mono text-[var(--text)]">
                        {processed} / {total}
                      </td>
                      <td className="p-3 tabular-nums">
                        <span className="text-[var(--color-success)] font-semibold">{job.rows_ok}</span>
                        {' / '}
                        <span className="text-[var(--color-danger)] font-semibold">{job.rows_failed}</span>
                      </td>
                      <td className="p-3 text-[var(--muted)] text-[11px]">
                        {new Date(job.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </td>
                      <td className="p-3 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 px-2 text-xs text-[var(--primary)] hover:underline gap-1"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedJobForDetail(job);
                          }}
                        >
                          <span>Details</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-8 text-center text-xs text-[var(--muted)]">
            <CheckCircle2 className="w-6 h-6 mx-auto mb-2 opacity-40" />
            <p>No previous import manifests found.</p>
          </div>
        )}
      </div>
    </div>
  );
};
