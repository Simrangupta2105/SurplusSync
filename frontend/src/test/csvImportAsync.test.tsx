import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BusinessImportPage } from '../pages/business/BusinessImportPage';
import { demoSource, setDataSourceMode } from '../services';
import type { ImportJob } from '../types';

describe('BusinessImportPage - Async CSV Import & Diagnostics', () => {
  let queryClient: QueryClient;
  const mockTriggerToast = vi.fn();
  const mockNavigate = vi.fn();

  const mockJobs: ImportJob[] = [
    {
      id: 101,
      organization: 1,
      file: 'october_manifest.csv',
      status: 'DONE',
      total_rows: 50,
      processed_rows: 50,
      rows_ok: 50,
      rows_failed: 0,
      started_at: '2026-10-17T10:00:00Z',
      finished_at: '2026-10-17T10:00:05Z',
      error_report: [],
      created_at: '2026-10-17T10:00:00Z',
    },
    {
      id: 102,
      organization: 1,
      file: 'produce_batches.csv',
      status: 'PARTIAL',
      total_rows: 30,
      processed_rows: 30,
      rows_ok: 28,
      rows_failed: 2,
      started_at: '2026-10-17T11:00:00Z',
      finished_at: '2026-10-17T11:00:04Z',
      error_report: [
        { row: 7, error: 'Invalid date format' },
        { row: 12, error: 'Missing product_name' },
      ],
      created_at: '2026-10-17T11:00:00Z',
    },
  ];

  beforeEach(() => {
    setDataSourceMode('demo');
    demoSource.setEnableLatency(false);
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 0 },
      },
    });
    vi.clearAllMocks();
    vi.spyOn(demoSource, 'getImportJobs').mockResolvedValue([...mockJobs]);
    vi.spyOn(demoSource, 'getImportJob').mockImplementation(async (id: number) => {
      const found = mockJobs.find((j) => j.id === id);
      if (!found) throw new Error('Not found');
      return found;
    });
  });

  const renderComponent = () =>
    render(
      <QueryClientProvider client={queryClient}>
        <BusinessImportPage onTriggerToast={mockTriggerToast} onNavigate={mockNavigate} />
      </QueryClientProvider>
    );

  it('renders page header, template download button, and dropzone', async () => {
    renderComponent();

    expect(screen.getByText('CSV Manifest Ingestion')).toBeInTheDocument();
    expect(screen.getByText('Download CSV Template')).toBeInTheDocument();
    expect(screen.getByText(/Click or drag ERP manifest CSV here/i)).toBeInTheDocument();
  });

  it('displays recent import jobs in the history table', async () => {
    renderComponent();

    const matches = await screen.findAllByText('october_manifest.csv');
    expect(matches.length).toBeGreaterThanOrEqual(1);
    expect(await screen.findByText('produce_batches.csv')).toBeInTheDocument();
    expect(screen.getAllByText('#101').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('#102').length).toBeGreaterThanOrEqual(1);
  });

  it('selecting a previous job displays its details and failed rows breakdown', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('produce_batches.csv')).toBeInTheDocument();
    });

    const row = screen.getByText('produce_batches.csv').closest('tr');
    if (row) {
      fireEvent.click(row);
    }

    await waitFor(() => {
      expect(screen.getByText(/Failed Rows Breakdown \(2\)/i)).toBeInTheDocument();
      expect(screen.getByText('Invalid date format')).toBeInTheDocument();
      expect(screen.getByText('Missing product_name')).toBeInTheDocument();
    });
  });

  it('renders worker_may_be_down warning alert when worker is inactive', async () => {
    const stuckJob: ImportJob = {
      id: 103,
      organization: 1,
      file: 'stuck_manifest.csv',
      status: 'PENDING',
      total_rows: 100,
      processed_rows: 0,
      rows_ok: 0,
      rows_failed: 0,
      started_at: null,
      finished_at: null,
      error_report: [],
      worker_may_be_down: true,
      created_at: new Date(Date.now() - 3 * 60 * 1000).toISOString(),
    };

    vi.spyOn(demoSource, 'getImportJobs').mockResolvedValue([stuckJob, ...mockJobs]);
    renderComponent();

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Background Worker May Be Inactive')).toBeInTheDocument();
      expect(screen.getByText(/python manage.py qcluster/i)).toBeInTheDocument();
    });
  });

  it('simulates uploading an asynchronous job and triggers polling feedback', async () => {
    const pendingJob: ImportJob = {
      id: 104,
      organization: 1,
      file: 'bulk_data.csv',
      status: 'PROCESSING',
      total_rows: 100,
      processed_rows: 40,
      rows_ok: 40,
      rows_failed: 0,
      started_at: new Date().toISOString(),
      finished_at: null,
      error_report: [],
      created_at: new Date().toISOString(),
    };

    vi.spyOn(demoSource, 'uploadCsvImport').mockResolvedValue(pendingJob);
    renderComponent();

    const file = new File(['name,quantity,expiry_date\nItem,10,2026-11-01'], 'bulk_data.csv', { type: 'text/csv' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText('bulk_data.csv')).toBeInTheDocument();
    });

    const uploadBtn = screen.getByRole('button', { name: /Import Manifest/i });
    expect(uploadBtn).not.toBeDisabled();
    fireEvent.click(uploadBtn);

    await waitFor(() => {
      expect(demoSource.uploadCsvImport).toHaveBeenCalledWith(file);
      expect(mockTriggerToast).toHaveBeenCalledWith('File uploaded. Queued for asynchronous processing.');
    });
  });
});
