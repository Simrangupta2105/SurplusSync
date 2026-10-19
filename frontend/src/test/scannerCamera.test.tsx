/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  BusinessScanPage,
  validateBarcode,
  mapCameraError,
  SUPPORTED_BARCODE_FORMATS,
  calculateWideScanBox,
  getPrimaryVideoConstraints,
  getFallbackVideoConstraints,
} from '../pages/business/BusinessScanPage';
import { demoSource, setDataSourceMode } from '../services';

// Provide URL mock methods for jsdom
if (typeof window !== 'undefined') {
  if (!window.URL.createObjectURL) {
    window.URL.createObjectURL = vi.fn(() => 'blob:mock-preview-url');
  }
  if (!window.URL.revokeObjectURL) {
    window.URL.revokeObjectURL = vi.fn();
  }
}

// Shared mocks for Html5Qrcode and ZXing using vi.hoisted to prevent hoisting TDZ errors
const {
  mockStart,
  mockStop,
  mockClear,
  mockGetCameras,
  mockScanFile,
  mockApplyVideoConstraints,
  mockZxingDecode,
  mockZxingStop,
} = vi.hoisted(() => ({
  mockStart: vi.fn(),
  mockStop: vi.fn().mockResolvedValue(undefined),
  mockClear: vi.fn().mockResolvedValue(undefined),
  mockGetCameras: vi.fn(),
  mockScanFile: vi.fn(),
  mockApplyVideoConstraints: vi.fn().mockResolvedValue(undefined),
  mockZxingDecode: vi.fn(),
  mockZxingStop: vi.fn(),
}));

vi.mock('html5-qrcode', () => {
  const Html5QrcodeSupportedFormats = {
    QR_CODE: 0,
    AZTEC: 1,
    CODABAR: 2,
    CODE_39: 3,
    CODE_93: 4,
    CODE_128: 5,
    DATA_MATRIX: 6,
    MAXICODE: 7,
    ITF: 8,
    EAN_13: 9,
    EAN_8: 10,
    PDF_417: 11,
    RSS_14: 12,
    RSS_EXPANDED: 13,
    UPC_A: 14,
    UPC_E: 15,
    UPC_EAN_EXTENSION: 16,
  };

  return {
    Html5QrcodeSupportedFormats,
    Html5Qrcode: class MockHtml5Qrcode {
      elementId: string;
      config?: any;
      isScanning = false;
      constructor(elementId: string, config?: any) {
        this.elementId = elementId;
        this.config = config;
      }
      start = vi.fn().mockImplementation(async (...args) => {
        this.isScanning = true;
        return mockStart(...args);
      });
      stop = vi.fn().mockImplementation(async (...args) => {
        this.isScanning = false;
        return mockStop(...args);
      });
      clear = mockClear;
      scanFile = mockScanFile;
      applyVideoConstraints = mockApplyVideoConstraints;
      static getCameras = mockGetCameras;
    },
  };
});

vi.mock('@zxing/browser', () => {
  return {
    BarcodeFormat: {
      QR_CODE: 0,
      CODE_128: 1,
      EAN_8: 2,
      EAN_13: 3,
      UPC_A: 4,
      UPC_E: 5,
    },
    BrowserMultiFormatReader: class MockBrowserMultiFormatReader {
      delayBetweenScanAttempts?: number;
      hints?: any;
      constructor(hints?: any, options?: any) {
        this.hints = hints;
        this.delayBetweenScanAttempts = options?.delayBetweenScanAttempts;
      }
      decodeFromConstraints = vi.fn().mockImplementation(async (constraints, video, callback) => {
        mockZxingDecode(constraints, video, callback);
        return {
          stop: mockZxingStop,
        };
      });
      decodeFromImageUrl = vi.fn().mockResolvedValue({
        getText: () => '4006381333931',
      });
    },
  };
});

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

describe('Barcode Format Restrictions (SUPPORTED_BARCODE_FORMATS)', () => {
  it('restricts formats strictly to retail 1D barcodes and QR codes', () => {
    // Expected formats: EAN_13, EAN_8, UPC_A, UPC_E, CODE_128, QR_CODE
    expect(SUPPORTED_BARCODE_FORMATS).toHaveLength(6);
    expect(SUPPORTED_BARCODE_FORMATS).toContain(9); // EAN_13
    expect(SUPPORTED_BARCODE_FORMATS).toContain(10); // EAN_8
    expect(SUPPORTED_BARCODE_FORMATS).toContain(14); // UPC_A
    expect(SUPPORTED_BARCODE_FORMATS).toContain(15); // UPC_E
    expect(SUPPORTED_BARCODE_FORMATS).toContain(5); // CODE_128
    expect(SUPPORTED_BARCODE_FORMATS).toContain(0); // QR_CODE

    // Excludes heavy 2D formats that degrade 1D performance
    expect(SUPPORTED_BARCODE_FORMATS).not.toContain(1); // AZTEC
    expect(SUPPORTED_BARCODE_FORMATS).not.toContain(6); // DATA_MATRIX
    expect(SUPPORTED_BARCODE_FORMATS).not.toContain(11); // PDF_417
  });
});

describe('Wide Scan Box Geometry (calculateWideScanBox)', () => {
  it('computes a wide ~300x120 box on desktop viewports (width >= 600px)', () => {
    const desktopBox = calculateWideScanBox(1024, 768);
    expect(desktopBox.width).toBe(300);
    expect(desktopBox.height).toBe(120);
  });

  it('computes 85% width by 35% height on mobile viewports (width < 600px)', () => {
    const mobileBox = calculateWideScanBox(400, 700);
    expect(mobileBox.width).toBe(Math.floor(400 * 0.85)); // 340
    expect(mobileBox.height).toBe(Math.floor(700 * 0.35)); // 245
  });

  it('enforces minimum dimension constraints on very small viewports', () => {
    const tinyBox = calculateWideScanBox(120, 100);
    expect(tinyBox.width).toBeGreaterThanOrEqual(150);
    expect(tinyBox.height).toBeGreaterThanOrEqual(80);
  });
});

describe('Video Constraints Generation', () => {
  it('specifies 1280x720 ideal resolution, environment facingMode, and continuous focus', () => {
    const constraints = getPrimaryVideoConstraints(null) as any;
    expect(constraints.width).toEqual({ ideal: 1280 });
    expect(constraints.height).toEqual({ ideal: 720 });
    expect(constraints.facingMode).toEqual({ ideal: 'environment' });
    expect(constraints.advanced).toEqual([{ focusMode: 'continuous' }]);
  });

  it('targets specific deviceId when cameraId is provided', () => {
    const constraints = getPrimaryVideoConstraints('cam-specific-123') as any;
    expect(constraints.deviceId).toEqual({ exact: 'cam-specific-123' });
    expect(constraints.width).toEqual({ ideal: 1280 });
  });

  it('provides simple fallback constraints when advanced constraints fail', () => {
    const fallback = getFallbackVideoConstraints(null);
    expect(fallback).toEqual({ facingMode: 'environment' });

    const fallbackSpecific = getFallbackVideoConstraints('cam-456');
    expect(fallbackSpecific).toEqual({ deviceId: { exact: 'cam-456' } });
  });
});

describe('Check-Digit Validation Utility (validateBarcode)', () => {
  it('rejects empty input', () => {
    const res = validateBarcode('');
    expect(res.isValid).toBe(false);
  });

  it('rejects non-numeric input', () => {
    const res = validateBarcode('ABC1234567890');
    expect(res.isValid).toBe(false);
    expect(res.errorMessage).toBe('This code looks incomplete. EAN-13 codes have 13 digits.');
  });

  it('rejects barcodes with invalid lengths (e.g. 5, 7, 9, 10, 11, 14 digits)', () => {
    const invalidLengths = ['12345', '1234567', '123456789', '1234567890', '12345678901', '12345678901234'];
    for (const code of invalidLengths) {
      const res = validateBarcode(code);
      expect(res.isValid).toBe(false);
      expect(res.errorMessage).toBe('This code looks incomplete. EAN-13 codes have 13 digits.');
    }
  });

  it('rejects barcodes with wrong check digits', () => {
    // Correct EAN-8 is 73513537, wrong check digit is 73513538
    expect(validateBarcode('73513538')).toEqual({
      isValid: false,
      errorMessage: 'This code looks incomplete. EAN-13 codes have 13 digits.',
    });

    // Correct UPC-A 12 is 012345678905, wrong is 012345678906
    expect(validateBarcode('012345678906')).toEqual({
      isValid: false,
      errorMessage: 'This code looks incomplete. EAN-13 codes have 13 digits.',
    });

    // Correct EAN-13 is 4006381333931, wrong is 4006381333939
    expect(validateBarcode('4006381333939')).toEqual({
      isValid: false,
      errorMessage: 'This code looks incomplete. EAN-13 codes have 13 digits.',
    });
  });

  it('accepts valid 8-digit EAN-8 barcodes', () => {
    const res = validateBarcode('73513537');
    expect(res.isValid).toBe(true);
    expect(res.errorMessage).toBeUndefined();
  });

  it('accepts valid 12-digit UPC-A barcodes', () => {
    const res = validateBarcode('012345678905');
    expect(res.isValid).toBe(true);
    expect(res.errorMessage).toBeUndefined();
  });

  it('accepts valid 13-digit EAN-13 barcodes', () => {
    const res = validateBarcode('4006381333931');
    expect(res.isValid).toBe(true);
    expect(res.errorMessage).toBeUndefined();
  });
});

describe('Camera Error Mapping Utility (mapCameraError)', () => {
  it('maps NotFoundError to specific message', () => {
    const err = new DOMException('Requested device not found', 'NotFoundError');
    const mapped = mapCameraError(err);
    expect(mapped.type).toBe('NotFoundError');
    expect(mapped.message).toBe('No camera found on this device. Use manual entry or open this page on a phone.');
  });

  it('maps NotAllowedError with steps for both browser and Windows', () => {
    const err = new DOMException('Permission denied', 'NotAllowedError');
    const mapped = mapCameraError(err);
    expect(mapped.type).toBe('NotAllowedError');
    expect(mapped.message).toContain('Browser: Click the lock or camera icon in the address bar');
    expect(mapped.message).toContain('Windows: Open Windows Settings > Privacy & security > Camera');
  });

  it('maps NotReadableError to in-use message', () => {
    const err = new DOMException('Could not start video source', 'NotReadableError');
    const mapped = mapCameraError(err);
    expect(mapped.type).toBe('NotReadableError');
    expect(mapped.message).toContain('Camera is in use by another app');
  });

  it('maps InsecureOrigin to HTTPS/localhost message', () => {
    const err = new Error('Camera access requires a secure context (insecure origin)');
    const mapped = mapCameraError(err);
    expect(mapped.type).toBe('InsecureOrigin');
    expect(mapped.message).toContain('Camera access requires HTTPS or localhost');
  });

  it('maps generic error and includes the error name', () => {
    const err = new DOMException('Constraints could not be satisfied', 'OverconstrainedError');
    const mapped = mapCameraError(err);
    expect(mapped.type).toBe('Generic');
    expect(mapped.title).toContain('OverconstrainedError');
    expect(mapped.message).toContain('OverconstrainedError');
  });
});

describe('BusinessScanPage Camera Scanner Lifecycle & Diagnostics', () => {
  const mockTriggerToast = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    setDataSourceMode('demo');
    mockGetCameras.mockResolvedValue([
      { id: 'cam-rear', label: 'Back Camera Ultra' },
      { id: 'cam-front', label: 'Front Camera HD' },
    ]);
  });

  it('ensures the container div is always rendered in the DOM with minHeight: 300px and never display: none', () => {
    renderWithClient(<BusinessScanPage onTriggerToast={mockTriggerToast} />);

    const container = document.getElementById('html5qr-code-full-region');
    expect(container).toBeInTheDocument();
    expect(container).not.toHaveClass('hidden');
    expect(container?.style.minHeight).toBe('300px');
    expect(container?.style.display).toBe('block');
  });

  it('mocks a rejected start() with NotAllowedError and asserts permission blocked error message, retry button, and link', async () => {
    mockStart.mockRejectedValue(new DOMException('Permission denied', 'NotAllowedError'));

    renderWithClient(<BusinessScanPage onTriggerToast={mockTriggerToast} />);

    const startBtn = screen.getByRole('button', { name: /start camera scanner/i });
    fireEvent.click(startBtn);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /camera permission blocked/i })).toBeInTheDocument();
    });

    expect(screen.getByText(/camera access is blocked/i)).toBeInTheDocument();
    expect(screen.getByText(/browser: click the lock or camera icon in the address bar/i)).toBeInTheDocument();
    expect(screen.getByText(/windows: open windows settings > privacy & security > camera/i)).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /retry camera/i });
    expect(retryBtn).toBeInTheDocument();

    const link = screen.getByRole('link', { name: /how to fix camera issues/i });
    expect(link).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /close camera/i })).not.toBeInTheDocument();
  });

  it('opens troubleshooting guide when "How to fix camera issues" link is clicked', async () => {
    mockStart.mockRejectedValue(new DOMException('Permission denied', 'NotAllowedError'));

    renderWithClient(<BusinessScanPage onTriggerToast={mockTriggerToast} />);

    fireEvent.click(screen.getByRole('button', { name: /start camera scanner/i }));

    await waitFor(() => {
      expect(screen.getByRole('link', { name: /how to fix camera issues/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('link', { name: /how to fix camera issues/i }));

    await waitFor(() => {
      expect(screen.getByText(/camera troubleshooting guide/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/1\. camera permission blocked/i)).toBeInTheDocument();
    expect(screen.getByText(/2\. camera in use/i)).toBeInTheDocument();
    expect(screen.getByText(/3\. no camera found/i)).toBeInTheDocument();
    expect(screen.getByText(/4\. insecure origin/i)).toBeInTheDocument();
  });

  it('clicking Retry Camera re-attempts Html5Qrcode.start()', async () => {
    mockStart.mockRejectedValueOnce(new DOMException('Permission denied', 'NotAllowedError'));

    renderWithClient(<BusinessScanPage onTriggerToast={mockTriggerToast} />);

    fireEvent.click(screen.getByRole('button', { name: /start camera scanner/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /retry camera/i })).toBeInTheDocument();
    });

    mockStart.mockResolvedValueOnce(null);

    fireEvent.click(screen.getByRole('button', { name: /retry camera/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /close camera/i })).toBeInTheDocument();
    });
    expect(screen.queryByText(/camera permission blocked/i)).not.toBeInTheDocument();
  });

  it('shows scanning helper text under camera: "Hold the barcode flat, 15-25 cm away, in good light"', async () => {
    mockStart.mockResolvedValue(null);

    renderWithClient(<BusinessScanPage onTriggerToast={mockTriggerToast} />);

    fireEvent.click(screen.getByRole('button', { name: /start camera scanner/i }));

    await waitFor(() => {
      expect(screen.getByText('Hold the barcode flat, 15-25 cm away, in good light')).toBeInTheDocument();
    });
  });

  it('falls back to available camera ID if { facingMode: "environment" } fails', async () => {
    mockStart
      .mockRejectedValueOnce(new Error('OverconstrainedError: facingMode environment not supported'))
      .mockResolvedValueOnce(null);

    renderWithClient(<BusinessScanPage onTriggerToast={mockTriggerToast} />);

    fireEvent.click(screen.getByRole('button', { name: /start camera scanner/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /close camera/i })).toBeInTheDocument();
    });

    expect(mockStart).toHaveBeenCalledTimes(2);
    expect(mockStart).toHaveBeenNthCalledWith(
      1,
      { facingMode: 'environment' },
      expect.objectContaining({
        fps: 10,
        qrbox: calculateWideScanBox,
      }),
      expect.any(Function),
      expect.any(Function)
    );
    expect(mockStart).toHaveBeenNthCalledWith(
      2,
      'cam-rear',
      expect.objectContaining({
        fps: 10,
        qrbox: calculateWideScanBox,
      }),
      expect.any(Function),
      expect.any(Function)
    );
  });
});

describe('Alternative Scanner Fallback Switch (@zxing/browser)', () => {
  const mockTriggerToast = vi.fn();

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    vi.clearAllMocks();
    setDataSourceMode('demo');
    mockGetCameras.mockResolvedValue([
      { id: 'cam-rear', label: 'Back Camera Ultra' },
    ]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows "No barcode detected yet" after 10s and "Try alternative scanner" button after 15s', async () => {
    mockStart.mockResolvedValue(null);

    renderWithClient(<BusinessScanPage onTriggerToast={mockTriggerToast} />);

    // Start primary scanner
    fireEvent.click(screen.getByRole('button', { name: /start camera scanner/i }));

    await waitFor(() => {
      expect(screen.getByText('Hold the barcode flat, 15-25 cm away, in good light')).toBeInTheDocument();
    });

    // 9 seconds: neither hint nor alt button should appear yet
    act(() => {
      vi.advanceTimersByTime(9000);
    });
    expect(screen.queryByText(/no barcode detected yet/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /try alternative scanner/i })).not.toBeInTheDocument();

    // 10 seconds: "No barcode detected yet" hint appears
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByText(/no barcode detected yet/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /try alternative scanner/i })).not.toBeInTheDocument();

    // 15 seconds: "Try alternative scanner (@zxing/browser)" button appears
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    const altBtn = screen.getByRole('button', { name: /try alternative scanner/i });
    expect(altBtn).toBeInTheDocument();

    // Clicking alternative scanner stops previous scanner and switches engine to ZXing
    fireEvent.click(altBtn);

    await waitFor(() => {
      // stop and clear must be called to ensure only one camera stream is open
      expect(mockStop).toHaveBeenCalled();
      expect(mockClear).toHaveBeenCalled();
      expect(screen.getByText('ZXing Fallback')).toBeInTheDocument();
      expect(mockZxingDecode).toHaveBeenCalled();
    });
  });
});

describe('Open Food Facts Only State & Product Card Fixes', () => {
  const mockTriggerToast = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    setDataSourceMode('demo');
  });

  it('renders "Add to inventory" action first, disables POS Sale and Mark Waste when 0 stock, shows "Price not set" and "No SKU"', async () => {
    // Mock lookup returning an item found ONLY on Open Food Facts (not in local inventory)
    vi.spyOn(demoSource, 'lookupBarcode').mockResolvedValueOnce({
      found: true,
      source: 'openfoodfacts',
      product_name: 'Nutella Hazelnut Spread',
      current_stock: 0,
      categories_text: 'Spreads, Sweet spreads, Hazelnut spreads',
      detail: 'Found on Open Food Facts',
      product: undefined,
    });

    renderWithClient(<BusinessScanPage onTriggerToast={mockTriggerToast} />);

    const input = screen.getByPlaceholderText(/enter barcode/i);
    const lookupBtn = screen.getByRole('button', { name: /lookup/i });

    // Valid EAN-13 barcode
    fireEvent.change(input, { target: { value: '3017620422003' } });
    fireEvent.click(lookupBtn);

    // 1. Assert "Not in Local Inventory" banner with "Add to inventory" action shown first
    await waitFor(() => {
      expect(screen.getByText(/not in local inventory/i)).toBeInTheDocument();
    });
    const addToInventoryBtn = screen.getByRole('button', { name: /add to inventory/i });
    expect(addToInventoryBtn).toBeInTheDocument();

    // 2. Assert "Price not set" is displayed instead of "₹0"
    expect(screen.getByText('Price not set')).toBeInTheDocument();
    expect(screen.queryByText('₹0')).not.toBeInTheDocument();

    // 3. Assert "No SKU" is displayed instead of blank text
    expect(screen.getByText(/No SKU/)).toBeInTheDocument();

    // 4. Assert POS Sale and Mark Waste buttons are disabled when stock is 0
    const saleBtn = screen.getByRole('button', { name: /pos sale/i });
    const wasteBtn = screen.getByRole('button', { name: /mark waste/i });
    const receiveBtn = screen.getByRole('button', { name: /receive/i });

    expect(saleBtn).toBeDisabled();
    expect(wasteBtn).toBeDisabled();
    expect(receiveBtn).not.toBeDisabled();

    // 5. Assert shelf life text handles mapped/unmapped categories
    expect(screen.getByText(/Default Shelf:/i)).toBeInTheDocument();

    // 6. Clicking "Add to inventory" opens the sheet with prefilled data
    fireEvent.click(addToInventoryBtn);
    await waitFor(() => {
      expect(screen.getByText('Add Product to Catalog')).toBeInTheDocument();
    });

    const nameInput = screen.getByLabelText(/product name/i) as HTMLInputElement;
    expect(nameInput.value).toBe('Nutella Hazelnut Spread');
  });

  it('allows photo upload to decode barcode via scanFile', async () => {
    mockScanFile.mockResolvedValueOnce('4006381333931');
    const lookupSpy = vi.spyOn(demoSource, 'lookupBarcode').mockResolvedValueOnce({
      found: true,
      source: 'local',
      product_name: 'Organic Milk 1L',
      current_stock: 12,
      product: {
        id: 1,
        name: 'Organic Milk 1L',
        sku: 'MILK-001',
        barcode: '4006381333931',
        category_name: 'Dairy',
        unit: 'units',
        selling_price: '4.99',
        cost_price: '3.00',
        min_stock_level: 5,
        shelf_life_days: 10,
        is_active: true,
      },
    });

    renderWithClient(<BusinessScanPage onTriggerToast={mockTriggerToast} />);

    const uploadBtns = screen.getAllByTitle(/upload photo of barcode/i);
    expect(uploadBtns.length).toBeGreaterThan(0);

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeInTheDocument();

    const fakeFile = new File(['mock_image_bytes'], 'barcode.jpg', { type: 'image/jpeg' });
    fireEvent.change(fileInput, { target: { files: [fakeFile] } });

    await waitFor(() => {
      expect(mockScanFile).toHaveBeenCalledWith(fakeFile, false);
      expect(lookupSpy).toHaveBeenCalledWith('4006381333931');
    });
  });
});
