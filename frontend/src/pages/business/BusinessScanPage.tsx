/* eslint-disable react-refresh/only-export-components */
import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  ScanLine,
  Camera,
  Flashlight,
  AlertCircle,
  CheckCircle2,
  Package,
  Plus,
  Minus,
  RefreshCw,
  Search,
  Upload,
  Image as ImageIcon,
  HelpCircle,
} from 'lucide-react';
import { Html5Qrcode, Html5QrcodeSupportedFormats } from 'html5-qrcode';
import { Button } from '../../components/ui/Button';
import { PageHeader } from '../../components/ui/PageHeader';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { Sheet } from '../../components/ui/Sheet';
import { dataSource } from '../../services';
import { useDeductStock, useCategories, useCreateProduct } from '../../hooks/useData';
import { mapOpenFoodFactsCategory, type MappedCategoryResult } from '../../lib/categoryMapping';
import type { ScanResult } from '../../types';

interface BusinessScanPageProps {
  onTriggerToast: (msg: string) => void;
  onNavigate?: (path: string) => void;
}

export interface CameraErrorInfo {
  type: 'NotAllowedError' | 'NotFoundError' | 'NotReadableError' | 'InsecureOrigin' | 'Generic';
  title: string;
  message: string;
  errorName?: string;
}

/**
 * 2. Formats restricted to retail 1D barcodes and QR codes for focused performance.
 */
export const SUPPORTED_BARCODE_FORMATS: Html5QrcodeSupportedFormats[] = [
  Html5QrcodeSupportedFormats.EAN_13,
  Html5QrcodeSupportedFormats.EAN_8,
  Html5QrcodeSupportedFormats.UPC_A,
  Html5QrcodeSupportedFormats.UPC_E,
  Html5QrcodeSupportedFormats.CODE_128,
  Html5QrcodeSupportedFormats.QR_CODE,
];

/**
 * Stable timestamp reader for performance throttling.
 */
function getCurrentTimestamp(): number {
  return Date.now();
}

/**
 * 2. Computes a wide rectangular scan box:
 * - Desktop: about 300x120 (bounded by viewfinder)
 * - Mobile: 85% width by 35% height
 */
export function calculateWideScanBox(
  viewfinderWidth: number,
  viewfinderHeight: number
): { width: number; height: number } {
  if (viewfinderWidth < 600) {
    const width = Math.floor(viewfinderWidth * 0.85);
    const height = Math.floor(viewfinderHeight * 0.35);
    return {
      width: Math.max(width, 150),
      height: Math.max(height, 80),
    };
  }

  const width = Math.min(300, Math.floor(viewfinderWidth * 0.85));
  const height = Math.min(120, Math.floor(viewfinderHeight * 0.45));
  return {
    width: Math.max(width, 180),
    height: Math.max(height, 80),
  };
}

/**
 * 2. Primary video constraints: 1280x720 ideal resolution, environment facingMode, continuous autofocus.
 */
export function getPrimaryVideoConstraints(cameraId?: string | null): MediaTrackConstraints {
  const constraints: MediaTrackConstraints = {
    width: { ideal: 1280 },
    height: { ideal: 720 },
  };

  if (cameraId) {
    constraints.deviceId = { exact: cameraId };
  } else {
    constraints.facingMode = { ideal: 'environment' };
  }

  // Continuous autofocus where supported by browser W3C ImageCapture API
  try {
    (constraints as MediaTrackConstraints & { advanced?: Array<Record<string, unknown>> }).advanced = [
      { focusMode: 'continuous' },
    ];
  } catch {
    // Unsupported browser
  }

  return constraints;
}

/**
 * Fallback constraints if high resolution or advanced focus constraints are rejected by driver.
 */
export function getFallbackVideoConstraints(cameraId?: string | null): MediaTrackConstraints {
  if (cameraId) {
    return { deviceId: { exact: cameraId } };
  }
  return { facingMode: 'environment' };
}

/**
 * Validates retail barcodes:
 * - Must be strictly numeric
 * - Must be 8, 12, or 13 digits
 * - Must satisfy standard GS1 modulo 10 check digit calculation
 */
export function validateBarcode(barcode: string): { isValid: boolean; errorMessage?: string } {
  const trimmed = barcode.trim();
  if (!trimmed) {
    return { isValid: false, errorMessage: 'Please enter a barcode number.' };
  }

  // Must be only digits and exactly 8, 12, or 13 digits
  if (!/^\d+$/.test(trimmed) || (trimmed.length !== 8 && trimmed.length !== 12 && trimmed.length !== 13)) {
    return {
      isValid: false,
      errorMessage: 'This code looks incomplete. EAN-13 codes have 13 digits.',
    };
  }

  const digits = trimmed.split('').map(Number);
  const checkDigit = digits[digits.length - 1];

  let sum = 0;
  let weight = 3;
  // Moving from right to left (excluding check digit): weight alternates 3, 1, 3, 1...
  for (let i = digits.length - 2; i >= 0; i--) {
    sum += digits[i] * weight;
    weight = weight === 3 ? 1 : 3;
  }

  const expected = (10 - (sum % 10)) % 10;
  if (checkDigit !== expected) {
    return {
      isValid: false,
      errorMessage: 'This code looks incomplete. EAN-13 codes have 13 digits.',
    };
  }

  return { isValid: true };
}

/**
 * Maps camera errors to specific plain-language messages and actionable guidance.
 */
export const mapCameraError = (err: unknown): CameraErrorInfo => {
  const errObj = err as Error;
  const rawName =
    errObj?.name ||
    (typeof err === 'object' && err !== null && 'name' in err
      ? String((err as Record<string, unknown>).name)
      : '');
  const rawMessage = errObj?.message || (typeof err === 'string' ? err : String(err || ''));

  const combined = `${rawName} ${rawMessage}`.toLowerCase();

  // 1. NotFoundError: No camera hardware detected
  if (
    rawName === 'NotFoundError' ||
    rawName === 'DevicesNotFoundError' ||
    combined.includes('notfounderror') ||
    combined.includes('devicesnotfounderror') ||
    combined.includes('no camera') ||
    combined.includes('requested device not found')
  ) {
    return {
      type: 'NotFoundError',
      title: 'No Camera Detected',
      message: 'No camera found on this device. Use manual entry or open this page on a phone.',
      errorName: rawName || 'NotFoundError',
    };
  }

  // 2. NotAllowedError: Permission blocked in browser or OS
  if (
    rawName === 'NotAllowedError' ||
    rawName === 'PermissionDeniedError' ||
    combined.includes('notallowederror') ||
    combined.includes('permissiondeniederror') ||
    combined.includes('permission denied') ||
    combined.includes('permission dismissed') ||
    combined.includes('permission blocked') ||
    combined.includes('permission')
  ) {
    return {
      type: 'NotAllowedError',
      title: 'Camera Permission Blocked',
      message:
        'Camera access is blocked. To allow it: 1. Browser: Click the lock or camera icon in the address bar and select "Allow". 2. Windows: Open Windows Settings > Privacy & security > Camera, and turn on "Let apps access your camera" and "Let desktop apps access your camera".',
      errorName: rawName || 'NotAllowedError',
    };
  }

  // 3. NotReadableError: Camera hardware busy / locked
  if (
    rawName === 'NotReadableError' ||
    rawName === 'TrackStartError' ||
    combined.includes('notreadableerror') ||
    combined.includes('trackstarterror') ||
    combined.includes('already in use') ||
    combined.includes('could not start video source') ||
    combined.includes('in use by another app')
  ) {
    return {
      type: 'NotReadableError',
      title: 'Camera Currently In Use',
      message: 'Camera is in use by another app. Please close other applications using your camera and try again.',
      errorName: rawName || 'NotReadableError',
    };
  }

  // 4. Insecure Origin: HTTP vs HTTPS
  if (
    rawName === 'InsecureOrigin' ||
    combined.includes('insecureorigin') ||
    combined.includes('secure context') ||
    combined.includes('insecure origin')
  ) {
    return {
      type: 'InsecureOrigin',
      title: 'Insecure Connection',
      message: 'Camera access requires HTTPS or localhost. Insecure HTTP connections cannot access camera hardware.',
      errorName: 'InsecureOrigin',
    };
  }

  // 5. Generic fallback: includes the error name
  const displayErrorName =
    rawName && rawName !== 'Error'
      ? rawName
      : rawMessage && rawMessage.includes(':')
      ? rawMessage.split(':')[0].trim()
      : 'CameraError';

  return {
    type: 'Generic',
    title: `Camera Error (${displayErrorName})`,
    message: `Camera error (${displayErrorName}): ${rawMessage || 'Unable to access camera hardware'}. Please try again or use manual barcode entry.`,
    errorName: displayErrorName,
  };
};

export const BusinessScanPage: React.FC<BusinessScanPageProps> = ({
  onTriggerToast,
  onNavigate: _onNavigate,
}) => {
  const [scannerActive, setScannerActive] = useState(false);
  const [activeEngine, setActiveEngine] = useState<'html5-qrcode' | 'zxing'>('html5-qrcode');
  const [isStarting, setIsStarting] = useState(false);
  const [torchOn, setTorchOn] = useState(false);
  const [cameraError, setCameraError] = useState<CameraErrorInfo | null>(null);
  const [showTroubleshooting, setShowTroubleshooting] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [cameras, setCameras] = useState<Array<{ id: string; label: string }>>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [manualBarcode, setManualBarcode] = useState('');
  const [lastSearchedBarcode, setLastSearchedBarcode] = useState('');
  const [scannedResult, setScannedResult] = useState<ScanResult | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [actionType, setActionType] = useState<'RECEIVE' | 'SALE' | 'WASTE' | 'DONATION'>('SALE');
  const [quantity, setQuantity] = useState(1);
  const [scanElapsedSeconds, setScanElapsedSeconds] = useState(0);

  // Add Product Sheet state
  const [isProductSheetOpen, setIsProductSheetOpen] = useState(false);
  const { data: categories } = useCategories();
  const createProductMutation = useCreateProduct();
  const [newProduct, setNewProduct] = useState({
    name: '',
    category: 1,
    sku: '',
    barcode: '',
    unit: 'units',
    cost_price: '',
    selling_price: '',
    min_stock_level: 10,
    shelf_life_days: '' as unknown as number,
  });

  const qrRegionId = 'html5qr-code-full-region';
  const html5QrCodeRef = useRef<Html5Qrcode | null>(null);
  const zxingControlsRef = useRef<{ stop: () => void } | null>(null);
  const zxingVideoRef = useRef<HTMLVideoElement | null>(null);
  const photoInputRef = useRef<HTMLInputElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const isStartingRef = useRef(false);
  const isStoppingRef = useRef(false);
  const isMountedRef = useRef(true);
  const frameCounterRef = useRef(0);
  const lastLogRef = useRef(0);
  const deductMutation = useDeductStock();

  // 5. Track active scanning duration for 10s and 15s hints
  useEffect(() => {
    if (!scannerActive) return;
    const timer = setInterval(() => {
      setScanElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => {
      clearInterval(timer);
    };
  }, [scannerActive]);

  // Trigger haptic feedback if device supports it
  const triggerHaptics = () => {
    if ('vibrate' in navigator) {
      try {
        navigator.vibrate(50);
      } catch {
        // Ignore haptics failure if unsupported or restricted
      }
    }
  };

  // Perform backend / local barcode lookup
  const handleLookup = async (barcode: string) => {
    const trimmed = barcode.trim();
    if (!trimmed) return;

    // Validate barcode first: must be 8, 12, or 13 digits with valid check digit
    const validation = validateBarcode(trimmed);
    if (!validation.isValid) {
      setLookupError(validation.errorMessage || 'This code looks incomplete. EAN-13 codes have 13 digits.');
      return;
    }

    setLastSearchedBarcode(trimmed);
    setIsScanning(true);
    setLookupError(null);
    try {
      const res = await dataSource.lookupBarcode(trimmed);
      setScannedResult(res);
      triggerHaptics();
      onTriggerToast(`Barcode detected: ${res.product?.name || res.product_name || trimmed}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Product not found locally or on Open Food Facts';
      setLookupError(msg);
      // Set scannedResult to not found so the "Add product" button appears
      setScannedResult({
        found: false,
        source: 'none',
        detail: msg,
      });
    } finally {
      setIsScanning(false);
    }
  };

  // 3. Stop and clear scanner instances safely, ensuring only one camera stream is ever open
  const stopAndClearScanner = async () => {
    if (isStoppingRef.current) {
      while (isStoppingRef.current) {
        await new Promise((r) => setTimeout(r, 50));
      }
      return;
    }
    isStoppingRef.current = true;
    try {
      // 1. Stop ZXing controls if active
      if (zxingControlsRef.current) {
        console.log('[Scanner Diagnostics] Stopping @zxing/browser controls and camera track...');
        try {
          zxingControlsRef.current.stop();
        } catch (zErr) {
          console.warn('[Scanner Diagnostics] ZXing stop warning:', zErr);
        }
        zxingControlsRef.current = null;
      }
      if (zxingVideoRef.current && zxingVideoRef.current.srcObject) {
        const stream = zxingVideoRef.current.srcObject as MediaStream;
        stream.getTracks().forEach((track) => track.stop());
        zxingVideoRef.current.srcObject = null;
      }

      // 2. Stop HTML5 QR Code instance if active
      if (html5QrCodeRef.current) {
        if (html5QrCodeRef.current.isScanning) {
          console.log('[Scanner Diagnostics] Calling html5QrCode.stop()...');
          await html5QrCodeRef.current.stop();
          console.log('[Scanner Diagnostics] html5QrCode.stop() resolved');
        }
        try {
          console.log('[Scanner Diagnostics] Calling html5QrCode.clear()...');
          await html5QrCodeRef.current.clear();
          console.log('[Scanner Diagnostics] html5QrCode.clear() resolved');
        } catch (clearErr) {
          console.warn('[Scanner Diagnostics] html5QrCode.clear() warning:', clearErr);
        }
      }
    } catch (err) {
      console.warn('[Scanner Diagnostics] stop/clear error:', err);
    } finally {
      isStoppingRef.current = false;
    }
  };

  // 1. Helper to log obtained video resolution from HTML5 video element
  const logObtainedVideoResolution = (engineName: string) => {
    try {
      const videoEl =
        engineName === 'zxing'
          ? zxingVideoRef.current
          : document.querySelector<HTMLVideoElement>(`#${qrRegionId} video`);

      if (videoEl) {
        const stream = videoEl.srcObject as MediaStream | null;
        const track = stream?.getVideoTracks()[0];
        const settings = track?.getSettings();
        console.log(`[Scanner Diagnostics] (${engineName}) Live video resolution obtained:`, {
          elementWidth: videoEl.videoWidth || videoEl.clientWidth,
          elementHeight: videoEl.videoHeight || videoEl.clientHeight,
          trackSettingsWidth: settings?.width,
          trackSettingsHeight: settings?.height,
          frameRate: settings?.frameRate,
          facingMode: settings?.facingMode,
          focusMode: (settings as MediaTrackSettings & { focusMode?: string })?.focusMode,
        });
      }
    } catch (logErr) {
      console.warn('[Scanner Diagnostics] Failed to inspect video stream resolution:', logErr);
    }
  };

  // Start Primary Camera Scanner (html5-qrcode)
  const startCamera = async (overrideCameraId?: string) => {
    const chosenCam = overrideCameraId !== undefined ? overrideCameraId : selectedCameraId;
    console.log('[Scanner] button pressed: Start Camera', chosenCam ? `(target camera: ${chosenCam})` : '');
    setCameraError(null);

    // React StrictMode & double-start guard
    if (isStartingRef.current) {
      console.log('[Scanner] Camera start already in progress, ignoring duplicate call (StrictMode guard)');
      return;
    }
    isStartingRef.current = true;
    setIsStarting(true);
    setActiveEngine('html5-qrcode');

    try {
      // Check for secure context
      if (
        window.location.protocol !== 'https:' &&
        window.location.hostname !== 'localhost' &&
        window.location.hostname !== '127.0.0.1'
      ) {
        console.warn('[Scanner] Insecure origin detected:', window.location.origin);
        setCameraError({
          type: 'InsecureOrigin',
          title: 'Insecure Connection',
          message: 'Camera access requires HTTPS or localhost. Insecure HTTP connections cannot access camera hardware.',
          errorName: 'InsecureOrigin',
        });
        return;
      }

      // Cleanup any active scanner and wait for stop/clear to complete
      await stopAndClearScanner();

      // Ensure container element exists in DOM and verify its dimensions
      const container = containerRef.current || document.getElementById(qrRegionId);
      if (!container) {
        console.error('[Scanner] Container element not found in DOM');
        setCameraError({
          type: 'Generic',
          title: 'Scanner Error',
          message: 'Scanner container element was not found in the DOM. Please reload the page.',
          errorName: 'ContainerNotFound',
        });
        return;
      }

      console.log(
        '[Scanner] container element found:',
        true,
        'width:',
        container.clientWidth,
        'height:',
        container.clientHeight
      );

      // 2. Initialize Html5Qrcode with restricted formats and BarcodeDetector
      if (!html5QrCodeRef.current) {
        console.log('[Scanner] Initializing new Html5Qrcode instance on element:', qrRegionId);
        html5QrCodeRef.current = new Html5Qrcode(qrRegionId, {
          formatsToSupport: SUPPORTED_BARCODE_FORMATS,
          verbose: false,
          experimentalFeatures: {
            useBarCodeDetectorIfSupported: true,
          },
        });
      }

      // Query available camera hardware
      let availableCameras: Array<{ id: string; label: string }> = [];
      try {
        console.log('[Scanner] Querying available cameras via Html5Qrcode.getCameras()...');
        availableCameras = await Html5Qrcode.getCameras();
        console.log('[Scanner] Available cameras found:', availableCameras);
        if (isMountedRef.current && availableCameras.length > 0) {
          setCameras(availableCameras);
        }
      } catch (camErr: unknown) {
        const camErrObj = camErr as Error;
        const cName = camErrObj?.name || 'Error';
        const cMsg = camErrObj?.message || String(camErr);
        console.error('[Scanner] getCameras() failed:', cName, cMsg, camErr);
      }

      // 2. Configure fps to 10 and wide scan box
      const qrConfig = {
        fps: 10,
        qrbox: calculateWideScanBox,
        videoConstraints: getPrimaryVideoConstraints(chosenCam),
      };

      const onScanSuccess = (decodedText: string, result: unknown) => {
        console.log('[Scanner Diagnostics] Barcode successfully decoded (html5-qrcode):', decodedText, result);
        stopCamera();
        handleLookup(decodedText);
      };

      frameCounterRef.current = 0;
      lastLogRef.current = getCurrentTimestamp();

      // 1. Log frame processing and decode errors
      const onScanError = (errorMessage: string, _error: unknown) => {
        frameCounterRef.current++;
        const now = getCurrentTimestamp();
        if (now - lastLogRef.current >= 2000) {
          console.log(
            `[Scanner Diagnostics] (html5-qrcode) Frames processed: ${frameCounterRef.current}. Latest decode state: "${errorMessage}"`
          );
          lastLogRef.current = now;
        }
      };

      // Configuration: prefer rear camera { facingMode: 'environment' } if no camera manually selected
      const cameraConfig: string | { facingMode: string } = chosenCam
        ? chosenCam
        : { facingMode: 'environment' };

      console.log('[Scanner] Html5Qrcode.start() called with:', cameraConfig);

      try {
        await html5QrCodeRef.current.start(
          cameraConfig,
          qrConfig,
          onScanSuccess,
          onScanError
        );
      } catch (startErr: unknown) {
        const errObj = startErr as Error;
        const sName = errObj?.name || 'Error';
        const sMsg = errObj?.message || String(startErr);
        console.error('[Scanner] start() failed on primary config:', sName, sMsg, startErr);

        // Fallback: try fallback constraints or available camera
        const fallbackConstraints = getFallbackVideoConstraints(chosenCam);
        const fallbackConfig = {
          ...qrConfig,
          videoConstraints: fallbackConstraints,
        };

        if (!chosenCam && availableCameras.length > 0) {
          const fallbackId = availableCameras[0].id;
          console.log('[Scanner] Falling back to available camera:', fallbackId);
          setSelectedCameraId(fallbackId);
          console.log('[Scanner] Html5Qrcode.start() called with fallback camera ID:', fallbackId);
          try {
            await html5QrCodeRef.current.start(
              fallbackId,
              fallbackConfig,
              onScanSuccess,
              onScanError
            );
          } catch (fallbackErr: unknown) {
            const fbErrObj = fallbackErr as Error;
            const fbName = fbErrObj?.name || 'Error';
            const fbMsg = fbErrObj?.message || String(fallbackErr);
            console.error('[Scanner] start() failed on fallback camera:', fbName, fbMsg, fallbackErr);
            throw fallbackErr;
          }
        } else {
          throw startErr;
        }
      }

      if (!isMountedRef.current) {
        console.log('[Scanner] Component unmounted during start(), tearing down');
        await stopAndClearScanner();
        return;
      }

      console.log('[Scanner] start() resolved successfully');
      setScannerActive(true);
      setCameraError(null);
      logObtainedVideoResolution('html5-qrcode');
    } catch (err: unknown) {
      const errObj = err as Error;
      const errName =
        errObj?.name ||
        (typeof err === 'object' && err !== null && 'name' in err
          ? String((err as Record<string, unknown>).name)
          : 'Error');
      const errMessage = errObj?.message || (typeof err === 'string' ? err : String(err));
      console.error('[Scanner] start() rejected:', errName, errMessage, err);
      if (isMountedRef.current) {
        const parsed = mapCameraError(err);
        setCameraError(parsed);
        setScannerActive(false);
      }
    } finally {
      isStartingRef.current = false;
      if (isMountedRef.current) {
        setIsStarting(false);
      }
    }
  };

  // 3. Start Alternative Scanner (@zxing/browser, lazy-loaded)
  const startZxingScanner = async (overrideCameraId?: string) => {
    const chosenCam = overrideCameraId !== undefined ? overrideCameraId : selectedCameraId;
    console.log('[Scanner Diagnostics] Initializing fallback scanner (@zxing/browser)...');
    setCameraError(null);
    setIsStarting(true);
    isStartingRef.current = true;

    try {
      // Clean up previous scanner streams
      await stopAndClearScanner();
      setActiveEngine('zxing');

      // Allow DOM to reveal zxing video element
      await new Promise((r) => setTimeout(r, 60));

      const video = zxingVideoRef.current;
      if (!video) {
        throw new Error('ZXing video element is not available.');
      }

      // Lazy load @zxing/browser
      const { BrowserMultiFormatReader, BarcodeFormat } = await import('@zxing/browser');

      const hints = new Map<number, unknown>();
      hints.set(2, [
        BarcodeFormat.EAN_13,
        BarcodeFormat.EAN_8,
        BarcodeFormat.UPC_A,
        BarcodeFormat.UPC_E,
        BarcodeFormat.CODE_128,
        BarcodeFormat.QR_CODE,
      ]);

      const reader = new BrowserMultiFormatReader(hints, {
        delayBetweenScanAttempts: 100, // ~10 fps
      });

      const constraints = getPrimaryVideoConstraints(chosenCam);
      console.log('[Scanner Diagnostics] (ZXing) Starting decodeFromConstraints with:', constraints);

      let frameCounter = 0;
      let lastLog = getCurrentTimestamp();

      const controls = await reader.decodeFromConstraints(
        { video: constraints, audio: false },
        video,
        (result, error, ctrls) => {
          frameCounter++;
          const now = getCurrentTimestamp();
          if (now - lastLog >= 2000) {
            console.log(
              `[Scanner Diagnostics] (ZXing) Frames processed: ${frameCounter}. Status: ${
                error ? (error as Error).name || 'searching' : 'frame_analyzed'
              }`
            );
            lastLog = now;
          }
          if (result) {
            const text = result.getText();
            console.log('[Scanner Diagnostics] (ZXing) Barcode successfully decoded:', text);
            ctrls.stop();
            zxingControlsRef.current = null;
            stopCamera();
            handleLookup(text);
          }
        }
      );

      zxingControlsRef.current = controls;
      setScannerActive(true);
      setCameraError(null);
      logObtainedVideoResolution('zxing');
    } catch (err: unknown) {
      console.error('[Scanner Diagnostics] ZXing start rejected:', err);
      if (isMountedRef.current) {
        const parsed = mapCameraError(err);
        setCameraError(parsed);
        setScannerActive(false);
      }
    } finally {
      isStartingRef.current = false;
      if (isMountedRef.current) {
        setIsStarting(false);
      }
    }
  };

  // 3. Switch between primary and alternative decoders
  const handleSwitchDecoder = async (engine: 'html5-qrcode' | 'zxing') => {
    console.log('[Scanner Diagnostics] Switching decoder engine to:', engine);
    await stopAndClearScanner();
    setScannerActive(false);
    if (engine === 'zxing') {
      await startZxingScanner();
    } else {
      await startCamera();
    }
  };

  // Switch camera when user selects a different lens
  const handleCameraChange = async (newCamId: string) => {
    console.log('[Scanner] Camera switched to:', newCamId);
    setSelectedCameraId(newCamId);
    if (scannerActive) {
      await stopAndClearScanner();
      setScannerActive(false);
      if (activeEngine === 'zxing') {
        await startZxingScanner(newCamId);
      } else {
        await startCamera(newCamId);
      }
    }
  };

  // Stop Camera
  const stopCamera = async () => {
    await stopAndClearScanner();
    if (isMountedRef.current) {
      setScannerActive(false);
      setTorchOn(false);
    }
  };

  // Toggle Torch if supported
  const toggleTorch = async () => {
    if (html5QrCodeRef.current && scannerActive && activeEngine === 'html5-qrcode') {
      try {
        const next = !torchOn;
        await html5QrCodeRef.current.applyVideoConstraints({
          advanced: [{ torch: next } as MediaTrackConstraintSet],
        });
        setTorchOn(next);
      } catch {
        onTriggerToast('Flashlight torch is not supported on this camera lens.');
      }
    } else {
      onTriggerToast('Torch control requires standard camera mode.');
    }
  };

  // 4. Upload photo of barcode using Html5Qrcode.scanFile with ZXing fallback
  const handlePhotoUpload = async (file: File) => {
    setIsScanning(true);
    setLookupError(null);
    console.log('[Scanner Diagnostics] Image file selected for barcode decoding:', file.name, file.size);

    try {
      let decodedText: string | null = null;

      // 1. Try Html5Qrcode scanFile first
      try {
        if (!html5QrCodeRef.current) {
          html5QrCodeRef.current = new Html5Qrcode(qrRegionId, {
            formatsToSupport: SUPPORTED_BARCODE_FORMATS,
            verbose: false,
            experimentalFeatures: {
              useBarCodeDetectorIfSupported: true,
            },
          });
        }
        decodedText = await html5QrCodeRef.current.scanFile(file, false);
        console.log('[Scanner Diagnostics] Html5Qrcode.scanFile successfully decoded:', decodedText);
      } catch (html5Err) {
        console.warn(
          '[Scanner Diagnostics] Html5Qrcode.scanFile could not decode, falling back to @zxing/browser:',
          html5Err
        );

        // 2. Fall back to lazy-loaded ZXing decodeFromImageUrl
        const { BrowserMultiFormatReader, BarcodeFormat } = await import('@zxing/browser');
        const hints = new Map<number, unknown>();
        hints.set(2, [
          BarcodeFormat.EAN_13,
          BarcodeFormat.EAN_8,
          BarcodeFormat.UPC_A,
          BarcodeFormat.UPC_E,
          BarcodeFormat.CODE_128,
          BarcodeFormat.QR_CODE,
        ]);
        const reader = new BrowserMultiFormatReader(hints);
        const objectUrl = URL.createObjectURL(file);
        try {
          const res = await reader.decodeFromImageUrl(objectUrl);
          decodedText = res.getText();
          console.log('[Scanner Diagnostics] ZXing.decodeFromImageUrl successfully decoded:', decodedText);
        } finally {
          URL.revokeObjectURL(objectUrl);
        }
      }

      if (decodedText) {
        await handleLookup(decodedText);
      } else {
        throw new Error('No readable barcode detected in image.');
      }
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : 'No readable barcode found in photo. Ensure the barcode is clear, flat, and well lit.';
      console.warn('[Scanner Diagnostics] Photo barcode decoding failed:', msg);
      setLookupError(msg);
      onTriggerToast(msg);
    } finally {
      setIsScanning(false);
    }
  };

  // 6. Map Open Food Facts categories and detect if product is ONLY on Open Food Facts
  const isOffOnly = Boolean(
    scannedResult &&
      (scannedResult.source === 'openfoodfacts' ||
        scannedResult.source === 'fatsecret' ||
        !scannedResult.product ||
        !scannedResult.product.id)
  );

  const mappedCat: MappedCategoryResult = useMemo(() => {
    if (!scannedResult) return {};
    const text =
      scannedResult.categories_text ||
      scannedResult.category_name ||
      (scannedResult.product as { category_name?: string } | undefined)?.category_name ||
      '';
    return mapOpenFoodFactsCategory(text, categories);
  }, [scannedResult, categories]);

  const currentStock = typeof scannedResult?.current_stock === 'number' ? scannedResult.current_stock : 0;

  // 6. Open Product Creation Sheet with prefilled barcode & mapped category
  const handleOpenAddProduct = (
    barcode: string,
    suggestedName = '',
    suggestedCategory?: MappedCategoryResult
  ) => {
    const defaultCatId = suggestedCategory?.categoryId || categories?.[0]?.id || 1;
    const defaultShelfLife =
      suggestedCategory?.defaultShelfLifeDays !== undefined ? suggestedCategory.defaultShelfLifeDays : '';

    setNewProduct({
      name: suggestedName,
      category: defaultCatId,
      sku: `SKU-${barcode.slice(-4) || 'NEW'}`,
      barcode: barcode,
      unit: 'units',
      cost_price: '',
      selling_price: '',
      min_stock_level: 10,
      shelf_life_days: defaultShelfLife as unknown as number,
    });
    setIsProductSheetOpen(true);
  };

  // Handle saving new product to catalog
  const handleSaveProduct = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProduct.name || !newProduct.sku) {
      onTriggerToast('Product name and SKU are required');
      return;
    }

    createProductMutation.mutate(
      {
        name: newProduct.name,
        sku: newProduct.sku,
        barcode: newProduct.barcode || lastSearchedBarcode,
        category: Number(newProduct.category),
        unit: newProduct.unit,
        unit_cost: newProduct.cost_price ? newProduct.cost_price : null,
        reorder_level: String(newProduct.min_stock_level || 10),
        is_active: true,
        cost_price: newProduct.cost_price || undefined,
        selling_price: newProduct.selling_price || undefined,
        min_stock_level: Number(newProduct.min_stock_level),
        shelf_life_days: newProduct.shelf_life_days ? Number(newProduct.shelf_life_days) : undefined,
      },
      {
        onSuccess: (createdProd) => {
          setIsProductSheetOpen(false);
          onTriggerToast(`Created product ${createdProd.name}`);
          setScannedResult({
            found: true,
            source: 'local',
            product: createdProd,
            product_name: createdProd.name,
            current_stock: 0,
          });
        },
        onError: (err: unknown) => {
          const msg = err instanceof Error ? err.message : 'Failed to register product';
          onTriggerToast(msg);
        },
      }
    );
  };

  // Handle inventory receive or deduct
  const handleExecuteStockAction = () => {
    if (!scannedResult) return;

    if (actionType === 'RECEIVE') {
      const prodName = scannedResult.product?.name || scannedResult.product_name || 'Item';
      onTriggerToast(`Inward received ${quantity} units of ${prodName}`);
      triggerHaptics();
      setScannedResult(null);
      setQuantity(1);
      return;
    }

    // Deduct stock action via mutation
    if (!scannedResult.product?.id) {
      onTriggerToast('Cannot process sale or waste for an item not yet enrolled in inventory.');
      return;
    }

    deductMutation.mutate(
      {
        product: scannedResult.product.id,
        quantity,
        reason: `Processed via Optical Scanner • ${actionType}`,
        txn_type: actionType === 'WASTE' ? 'DISCARDED' : 'SOLD',
      },
      {
        onSuccess: (res) => {
          triggerHaptics();
          onTriggerToast(res.message || `Deducted ${quantity} units via ${actionType}`);
          setScannedResult(null);
          setQuantity(1);
        },
        onError: (err: unknown) => {
          const msg = err instanceof Error ? err.message : 'Insufficient stock in active batches';
          onTriggerToast(msg);
        },
      }
    );
  };

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      stopAndClearScanner().catch((e) => console.warn('[Scanner] cleanup error:', e));
    };
  }, []);

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      <PageHeader
        title="Barcode Scanner & POS Station"
        subtitle="Hardware-accelerated optical barcode decoder & inventory management"
      />

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Optical Camera Viewport & Fallback Manual Input (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-[var(--text)] flex items-center gap-2">
                  <ScanLine className="w-4 h-4 text-[var(--primary)]" />
                  Live Camera Scanner
                </h2>
                <p className="text-xs text-[var(--muted)] mt-0.5">
                  Point camera at product barcode or upload a photo
                </p>
              </div>

              {/* Engine Badge */}
              {scannerActive && (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20">
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--primary)] animate-ping" />
                  {activeEngine === 'zxing' ? 'ZXing Fallback' : 'HTML5 Standard'}
                </span>
              )}
            </div>

            {/* Camera Viewport Container */}
            <div
              className="relative w-full max-w-sm rounded-[10px] overflow-hidden bg-[var(--surface-2)] flex flex-col items-center justify-center border border-[var(--border)]"
              style={{ minHeight: '300px' }}
            >
              {/* HTML5 QR Code DOM target - ALWAYS in the DOM with min-height 300px and NEVER display: none */}
              <div
                id={qrRegionId}
                ref={containerRef}
                className={`w-full h-full ${activeEngine === 'zxing' && scannerActive ? 'opacity-0 absolute inset-0 pointer-events-none' : ''}`}
                style={{ minHeight: '300px', display: 'block' }}
              />

              {/* 3. Fallback ZXing Video Viewport when activeEngine === 'zxing' */}
              <video
                ref={zxingVideoRef}
                id="zxing-video-preview"
                className={`w-full h-full object-cover ${activeEngine === 'zxing' && scannerActive ? 'block' : 'hidden'}`}
                style={{ minHeight: '300px' }}
                playsInline
                muted
              />

              {/* Inactive Camera Placeholder / Instructions */}
              {!scannerActive && !isStarting && !cameraError && (
                <div className="absolute inset-0 z-10 flex flex-col items-center justify-center p-6 text-center bg-[var(--surface)] space-y-4">
                  <div className="w-14 h-14 rounded-full bg-[var(--surface-2)] text-[var(--primary)] flex items-center justify-center mx-auto border border-[var(--border)] shadow-xs">
                    <Camera className="w-7 h-7" />
                  </div>
                  <div>
                    <h2 className="text-base font-semibold text-[var(--text)]">
                      Optical Barcode Scanner
                    </h2>
                    <p className="text-xs text-[var(--muted)] mt-1 leading-relaxed">
                      Point camera at a retail EAN-13, EAN-8, UPC, or Code-128 barcode under good lighting.
                    </p>
                  </div>

                  {cameras.length > 1 && (
                    <div className="flex items-center gap-2">
                      <label htmlFor="inactive-camera-select" className="text-xs text-[var(--muted)]">
                        Camera:
                      </label>
                      <select
                        id="inactive-camera-select"
                        value={selectedCameraId || ''}
                        onChange={(e) => setSelectedCameraId(e.target.value)}
                        className="text-xs rounded-[6px] border border-[var(--border)] bg-[var(--surface-2)] px-2 py-1 text-[var(--text)] outline-none"
                      >
                        {cameras.map((cam, idx) => (
                          <option key={cam.id} value={cam.id}>
                            {cam.label || `Camera ${idx + 1}`}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  <div className="flex flex-col gap-2 w-full">
                    <Button
                      id="start-camera-scanner-btn"
                      variant="primary"
                      size="md"
                      onClick={() => startCamera()}
                      className="w-full gap-2 text-xs font-semibold"
                    >
                      <ScanLine className="w-4 h-4" />
                      <span>Start Camera Scanner</span>
                    </Button>

                    {/* 4. Upload photo of barcode */}
                    <Button
                      id="upload-barcode-photo-btn"
                      variant="outline"
                      size="sm"
                      disabled={isScanning}
                      onClick={() => photoInputRef.current?.click()}
                      className="w-full gap-2 text-xs"
                    >
                      <Upload className="w-4 h-4" />
                      <span>Upload photo of barcode</span>
                    </Button>
                    <input
                      ref={photoInputRef}
                      type="file"
                      accept="image/*"
                      aria-label="Upload photo of barcode"
                      className="hidden"
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          handlePhotoUpload(e.target.files[0]);
                          e.target.value = '';
                        }
                      }}
                    />
                  </div>
                </div>
              )}

              {/* Starting Spinner Overlay */}
              {isStarting && (
                <div className="absolute inset-0 z-10 flex flex-col items-center justify-center p-6 text-center bg-[var(--surface)]/95 backdrop-blur-xs space-y-3">
                  <RefreshCw className="w-8 h-8 animate-spin text-[var(--primary)]" />
                  <p className="text-xs font-medium text-[var(--text)]">Initializing optical feed...</p>
                </div>
              )}

              {/* Camera Error State Panel with Plain Message & Retry Button */}
              {cameraError && !scannerActive && !isStarting && (
                <div
                  id="camera-error-panel"
                  className="absolute inset-0 z-10 flex flex-col items-center justify-center p-6 text-center bg-[var(--surface)] space-y-3"
                >
                  <div className="w-12 h-12 rounded-full bg-[var(--color-danger-subtle)] text-[var(--color-danger)] flex items-center justify-center border border-[var(--color-danger-border)]">
                    <AlertCircle className="w-6 h-6" />
                  </div>
                  <div className="max-w-xs space-y-1">
                    <h3 className="text-sm font-semibold text-[var(--text)]">
                      {cameraError.title}
                    </h3>
                    <p className="text-xs text-[var(--muted)] leading-relaxed">
                      {cameraError.message}
                    </p>
                  </div>
                  <div className="flex flex-col items-center gap-2 mt-2">
                    <Button
                      id="retry-camera-btn"
                      variant="primary"
                      size="sm"
                      onClick={() => {
                        console.log('[Scanner] button pressed: Retry Camera');
                        startCamera();
                      }}
                      className="gap-2 text-xs"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      <span>Retry Camera</span>
                    </Button>
                    <a
                      href="#camera-troubleshooting"
                      id="camera-troubleshoot-link"
                      onClick={(e) => {
                        e.preventDefault();
                        setShowTroubleshooting(true);
                      }}
                      className="text-xs text-[var(--primary)] underline hover:opacity-80 transition-opacity mt-1 cursor-pointer"
                    >
                      How to fix camera issues
                    </a>
                  </div>
                </div>
              )}
            </div>

            {/* 5. Camera Helper Text & Diagnostic Hints While Scanning */}
            {scannerActive && (
              <div className="mt-2 text-center space-y-1.5 w-full">
                <p className="text-xs font-medium text-[var(--muted)]">
                  Hold the barcode flat, 15-25 cm away, in good light
                </p>
                {scanElapsedSeconds >= 10 && (
                  <p className="text-xs font-semibold text-amber-500 animate-pulse">
                    No barcode detected yet
                  </p>
                )}
                {/* 3. Offer alternative scanner switch if nothing decoded after 15s */}
                {scanElapsedSeconds >= 15 && activeEngine === 'html5-qrcode' && (
                  <div className="pt-1.5 flex justify-center">
                    <Button
                      id="try-alt-scanner-btn"
                      variant="secondary"
                      size="sm"
                      onClick={() => handleSwitchDecoder('zxing')}
                      className="gap-1.5 text-xs font-semibold"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      <span>Try alternative scanner (@zxing/browser)</span>
                    </Button>
                  </div>
                )}
                {activeEngine === 'zxing' && (
                  <div className="pt-1 flex justify-center">
                    <Button
                      id="switch-standard-scanner-btn"
                      variant="ghost"
                      size="sm"
                      onClick={() => handleSwitchDecoder('html5-qrcode')}
                      className="gap-1.5 text-[11px] text-[var(--muted)] hover:text-[var(--text)]"
                    >
                      <RefreshCw className="w-3 h-3" />
                      <span>Switch back to standard scanner</span>
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* Active Scanner Controls Overlay */}
            {scannerActive && (
              <div className="flex flex-wrap items-center justify-center gap-3 mt-4 w-full">
                {cameras.length > 1 && (
                  <div className="flex items-center gap-1.5">
                    <label htmlFor="scanner-camera-select" className="text-xs text-[var(--muted)]">
                      Lens:
                    </label>
                    <select
                      id="scanner-camera-select"
                      value={selectedCameraId || ''}
                      onChange={(e) => handleCameraChange(e.target.value)}
                      className="text-xs rounded-[6px] border border-[var(--border)] bg-[var(--surface-2)] px-2 py-1 text-[var(--text)] outline-none"
                    >
                      {cameras.map((cam, idx) => (
                        <option key={cam.id} value={cam.id}>
                          {cam.label || `Camera ${idx + 1}`}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={toggleTorch}
                  className={`text-xs gap-1.5 ${torchOn ? 'text-[var(--accent)] border-[var(--accent)]' : ''}`}
                >
                  <Flashlight className="w-4 h-4" />
                  <span>{torchOn ? 'Torch On' : 'Torch Off'}</span>
                </Button>
                <Button
                  id="close-camera-btn"
                  variant="outline"
                  size="sm"
                  onClick={stopCamera}
                  className="text-xs text-[var(--color-danger)]"
                >
                  Close Camera
                </Button>
              </div>
            )}
          </div>

          {/* Manual Barcode Fallback Input & Photo Upload Button */}
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-[var(--text)] flex items-center gap-1.5">
                <Search className="w-3.5 h-3.5 text-[var(--primary)]" />
                Manual Barcode / Photo Ingestion
              </span>
              <span className="text-[11px] text-[var(--muted)]">EAN-13 / UPC / SKU</span>
            </div>
            <div className="flex items-center gap-2">
              <input
                id="manual-barcode-input"
                type="text"
                placeholder="Enter barcode e.g. 4006381333931"
                value={manualBarcode}
                onChange={(e) => setManualBarcode(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleLookup(manualBarcode)}
                className="flex-1 rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 font-mono text-xs text-[var(--text)] focus:border-[var(--primary)] outline-none"
              />
              <Button
                id="manual-lookup-btn"
                variant="primary"
                size="sm"
                disabled={isScanning || !manualBarcode.trim()}
                onClick={() => handleLookup(manualBarcode)}
                className="gap-1.5 text-xs h-9 px-4 shrink-0"
              >
                {isScanning ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : 'Lookup'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={isScanning}
                onClick={() => photoInputRef.current?.click()}
                title="Upload Photo of Barcode"
                className="gap-1.5 text-xs h-9 px-3 shrink-0"
              >
                <ImageIcon className="w-4 h-4" />
              </Button>
            </div>
            {lookupError && (
              <div
                id="lookup-error-msg"
                className="p-3 rounded-[8px] bg-[var(--color-danger-subtle)] border border-[var(--color-danger-border)] text-xs text-[var(--color-danger)] flex items-start gap-2"
              >
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <div className="flex-1 leading-relaxed">{lookupError}</div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Scan Results & Action Stepper (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="rounded-[12px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
              <h2 className="text-sm font-semibold text-[var(--text)]">Scanner Output</h2>
              {scannedResult ? (
                <StatusBadge
                  status={
                    scannedResult.found === false || scannedResult.source === 'none'
                      ? 'Not Found'
                      : isOffOnly
                      ? 'Open Food Facts'
                      : 'Local Catalog'
                  }
                  variant={
                    scannedResult.found === false || scannedResult.source === 'none'
                      ? 'warning'
                      : isOffOnly
                      ? 'info'
                      : 'success'
                  }
                  size="sm"
                >
                  {scannedResult.found === false || scannedResult.source === 'none'
                    ? 'Not in Catalog'
                    : isOffOnly
                    ? 'Open Food Facts'
                    : 'Local Catalog'}
                </StatusBadge>
              ) : (
                <span className="text-[11px] text-[var(--muted)]">Awaiting input</span>
              )}
            </div>

            {scannedResult ? (
              scannedResult.found === false || scannedResult.source === 'none' ? (
                /* Barcode NOT found anywhere */
                <div
                  id="barcode-not-found-card"
                  className="p-4 rounded-[10px] bg-[var(--surface-2)] border border-[var(--border)] space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-500">
                      Not in Catalog
                    </span>
                    <span className="text-[11px] font-mono text-[var(--muted)]">
                      {lastSearchedBarcode || manualBarcode}
                    </span>
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-[var(--text)]">Product Not Found</h3>
                    <p className="text-xs text-[var(--muted)] mt-1 leading-relaxed">
                      Barcode{' '}
                      <strong className="font-mono text-[var(--text)]">
                        {lastSearchedBarcode || manualBarcode}
                      </strong>{' '}
                      is not registered in your catalog or Open Food Facts.
                    </p>
                  </div>
                  <div className="pt-2 border-t border-[var(--border)]">
                    <Button
                      id="add-product-btn"
                      variant="primary"
                      size="sm"
                      onClick={() => handleOpenAddProduct(lastSearchedBarcode || manualBarcode)}
                      className="w-full gap-2 text-xs font-semibold"
                    >
                      <Plus className="w-4 h-4" />
                      <span>Add product</span>
                    </Button>
                  </div>
                </div>
              ) : (
                /* 6. Product Result Card (Handles both local inventory and Open Food Facts) */
                <div className="space-y-4">
                  {/* 6. If found ONLY on Open Food Facts: Show "Add to inventory" action FIRST */}
                  {isOffOnly && (
                    <div className="p-3.5 rounded-[10px] bg-amber-500/10 border border-amber-500/30 space-y-2.5">
                      <div className="flex items-center justify-between text-xs text-amber-500 font-semibold">
                        <span className="flex items-center gap-1.5">
                          <Package className="w-4 h-4 text-amber-500" />
                          <span>Not in Local Inventory</span>
                        </span>
                        <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-amber-500/20">
                          External Master Data
                        </span>
                      </div>
                      <p className="text-[11px] text-[var(--muted)] leading-relaxed">
                        Recognized via Open Food Facts. Add this item to your inventory catalog to configure local
                        pricing, SKU codes, and batch horizons.
                      </p>
                      <Button
                        id="add-to-inventory-btn"
                        variant="primary"
                        size="sm"
                        onClick={() =>
                          handleOpenAddProduct(
                            lastSearchedBarcode || manualBarcode,
                            scannedResult.product_name || scannedResult.product?.name,
                            mappedCat
                          )
                        }
                        className="w-full gap-2 text-xs font-semibold"
                      >
                        <Plus className="w-4 h-4" />
                        <span>Add to inventory</span>
                      </Button>
                    </div>
                  )}

                  {/* Product Specification Card */}
                  <div className="p-3.5 rounded-[10px] bg-[var(--surface-2)] border border-[var(--border)] space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <h4 className="text-sm font-bold text-[var(--text)]">
                          {scannedResult.product?.name || scannedResult.product_name || 'Product Barcode Item'}
                        </h4>
                        {/* 6. Category mapped sensibly; SKU displays "No SKU" instead of blank text */}
                        <p className="text-xs text-[var(--muted)] mt-0.5">
                          <span>
                            {isOffOnly
                              ? mappedCat.categoryName || scannedResult.category_name || 'Category not set'
                              : scannedResult.product?.category_name || 'Uncategorized'}
                          </span>
                          <span> • </span>
                          <span>
                            {scannedResult.product?.sku && scannedResult.product.sku.trim()
                              ? `SKU: ${scannedResult.product.sku}`
                              : 'No SKU'}
                          </span>
                        </p>
                      </div>
                      {/* 6. Selling price displays "Price not set" instead of ₹0 */}
                      <span className="text-xs font-semibold tabular-nums text-[var(--primary)]">
                        {scannedResult.product?.selling_price &&
                        Number(scannedResult.product.selling_price) > 0
                          ? `₹${scannedResult.product.selling_price}`
                          : 'Price not set'}
                      </span>
                    </div>

                    {/* 6. Default shelf displays mapped days or requires user entry */}
                    <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-[var(--border)]/60 text-[11px] text-[var(--muted)]">
                      <span>
                        Barcode:{' '}
                        <strong className="font-mono text-[var(--text)]">
                          {scannedResult.product?.barcode || lastSearchedBarcode || manualBarcode}
                        </strong>
                      </span>
                      <span>•</span>
                      <span>
                        Default Shelf:{' '}
                        <strong className="text-[var(--text)]">
                          {isOffOnly
                            ? mappedCat.defaultShelfLifeDays
                              ? `${mappedCat.defaultShelfLifeDays}d`
                              : 'Not set (requires expiry date)'
                            : scannedResult.product?.shelf_life_days
                            ? `${scannedResult.product.shelf_life_days}d`
                            : 'Not set (requires expiry date)'}
                        </strong>
                      </span>
                      <span>•</span>
                      <span>
                        Stock:{' '}
                        <strong className={currentStock > 0 ? 'text-emerald-500' : 'text-amber-500'}>
                          {currentStock} units
                        </strong>
                      </span>
                    </div>
                  </div>

                  {/* 6. Action Mode Toggle with POS Sale and Mark Waste disabled for Open Food Facts */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="block text-xs font-semibold text-[var(--text)]">
                        Transaction Operation
                      </label>
                      {isOffOnly && currentStock === 0 && (
                        <span className="text-[10px] text-amber-500 font-medium">
                          Sale &amp; Waste disabled (0 stock)
                        </span>
                      )}
                    </div>
                    <div className="grid grid-cols-3 gap-1.5">
                      {[
                        { id: 'SALE', label: 'POS Sale', disabled: isOffOnly && currentStock === 0 },
                        { id: 'RECEIVE', label: 'Receive', disabled: false },
                        { id: 'WASTE', label: 'Mark Waste', disabled: isOffOnly && currentStock === 0 },
                      ].map((act) => (
                        <button
                          key={act.id}
                          type="button"
                          disabled={act.disabled}
                          onClick={() => setActionType(act.id as 'SALE' | 'RECEIVE' | 'WASTE')}
                          className={`py-1.5 px-2 rounded-[6px] text-xs font-semibold border transition-all ${
                            act.disabled
                              ? 'opacity-40 cursor-not-allowed bg-[var(--surface-2)] text-[var(--muted)] border-[var(--border)]'
                              : actionType === act.id
                              ? 'bg-[var(--primary)] text-white border-[var(--primary)] shadow-xs'
                              : 'bg-[var(--surface-2)] text-[var(--muted)] border-[var(--border)] hover:text-[var(--text)]'
                          }`}
                        >
                          {act.label}
                        </button>
                      ))}
                    </div>
                    {isOffOnly && currentStock === 0 && (
                      <p className="text-[11px] text-[var(--muted)] mt-1">
                        POS Sale and Mark Waste are disabled until stock exists. Use Receive or Add to Inventory first.
                      </p>
                    )}
                  </div>

                  {/* Quantity Stepper */}
                  <div className="space-y-1.5">
                    <label className="block text-xs font-semibold text-[var(--text)]">
                      Quantity ({scannedResult.product?.unit || 'units'})
                    </label>
                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                        className="w-10 h-10 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-[var(--text)] flex items-center justify-center hover:bg-[var(--surface)] transition-colors"
                      >
                        <Minus className="w-4 h-4" />
                      </button>
                      <input
                        type="number"
                        min="1"
                        value={quantity}
                        onChange={(e) => setQuantity(Math.max(1, Number(e.target.value)))}
                        className="flex-1 text-center font-bold text-base tabular-nums rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] h-10 text-[var(--text)] outline-none"
                      />
                      <button
                        type="button"
                        onClick={() => setQuantity((q) => q + 1)}
                        className="w-10 h-10 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] text-[var(--text)] flex items-center justify-center hover:bg-[var(--surface)] transition-colors"
                      >
                        <Plus className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Submit Action Button */}
                  <Button
                    id="confirm-stock-action-btn"
                    variant="primary"
                    size="md"
                    onClick={handleExecuteStockAction}
                    disabled={
                      deductMutation.isPending ||
                      (isOffOnly && actionType !== 'RECEIVE') ||
                      (actionType !== 'RECEIVE' && currentStock === 0)
                    }
                    className="w-full gap-2 text-xs font-semibold"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>
                      {isOffOnly && actionType !== 'RECEIVE'
                        ? 'Sale/Waste Disabled (No Stock in Catalog)'
                        : `Confirm ${actionType} (${quantity} ${scannedResult.product?.unit || 'units'})`}
                    </span>
                  </Button>
                </div>
              )
            ) : (
              <div className="py-12 text-center space-y-3">
                <div className="w-12 h-12 rounded-full bg-[var(--surface-2)] text-[var(--muted)] flex items-center justify-center mx-auto">
                  <Package className="w-6 h-6 opacity-40" />
                </div>
                <div>
                  <h3 className="text-xs font-semibold text-[var(--text)]">No Active Barcode</h3>
                  <p className="text-[11px] text-[var(--muted)] mt-1 max-w-xs mx-auto">
                    Scan a product barcode or enter a number manually to look up stock, batches, and operations.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Troubleshooting Sheet */}
      <Sheet
        isOpen={showTroubleshooting}
        onClose={() => setShowTroubleshooting(false)}
        title="Camera Troubleshooting Guide"
      >
        <div className="space-y-4 text-xs text-[var(--text)] leading-relaxed">
          <div className="p-3.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] space-y-1.5">
            <h4 className="font-semibold text-sm flex items-center gap-1.5 text-[var(--primary)]">
              <HelpCircle className="w-4 h-4" />
              1. Camera Permission Blocked
            </h4>
            <p className="text-[var(--muted)]">
              Click the lock or camera icon in the address bar and choose &quot;Allow&quot;. In Windows Settings,
              ensure &quot;Let apps access your camera&quot; is turned On.
            </p>
          </div>

          <div className="p-3.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] space-y-1.5">
            <h4 className="font-semibold text-sm flex items-center gap-1.5 text-[var(--primary)]">
              <Camera className="w-4 h-4" />
              2. Camera in Use
            </h4>
            <p className="text-[var(--muted)]">
              Close Zoom, Teams, Skype, or any other browser tab that is currently using the camera.
            </p>
          </div>

          <div className="p-3.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] space-y-1.5">
            <h4 className="font-semibold text-sm flex items-center gap-1.5 text-[var(--primary)]">
              <ScanLine className="w-4 h-4" />
              3. No Camera Found
            </h4>
            <p className="text-[var(--muted)]">
              If your device does not have a webcam, use the manual barcode entry box or upload a photo of the barcode.
            </p>
          </div>

          <div className="p-3.5 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)] space-y-1.5">
            <h4 className="font-semibold text-sm flex items-center gap-1.5 text-[var(--primary)]">
              <AlertCircle className="w-4 h-4" />
              4. Insecure Origin
            </h4>
            <p className="text-[var(--muted)]">
              Browsers restrict camera access to HTTPS connections or localhost.
            </p>
          </div>
        </div>
      </Sheet>

      {/* 6. Product Creation Sheet with mapped categories and empty shelf-life when unknown */}
      <Sheet
        isOpen={isProductSheetOpen}
        onClose={() => setIsProductSheetOpen(false)}
        title="Add Product to Catalog"
      >
        <form onSubmit={handleSaveProduct} className="space-y-4 text-xs">
          <div>
            <label htmlFor="new-product-name" className="block font-semibold text-[var(--text)] mb-1">
              Product Name *
            </label>
            <input
              id="new-product-name"
              type="text"
              required
              placeholder="e.g. Nandini Toned Milk 500ml"
              value={newProduct.name}
              onChange={(e) => setNewProduct({ ...newProduct, name: e.target.value })}
              className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)] outline-none focus:border-[var(--primary)]"
            />
          </div>

          <div>
            <label htmlFor="new-product-category" className="block font-semibold text-[var(--text)] mb-1">
              Product Category
            </label>
            <select
              id="new-product-category"
              value={newProduct.category}
              onChange={(e) => setNewProduct({ ...newProduct, category: Number(e.target.value) })}
              className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)] outline-none focus:border-[var(--primary)]"
            >
              {(categories || []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="new-product-sku" className="block font-semibold text-[var(--text)] mb-1">
                SKU Code *
              </label>
              <input
                id="new-product-sku"
                type="text"
                required
                placeholder="e.g. PAN-500-ORG"
                value={newProduct.sku}
                onChange={(e) => setNewProduct({ ...newProduct, sku: e.target.value })}
                className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 font-mono text-[var(--text)] outline-none focus:border-[var(--primary)]"
              />
            </div>
            <div>
              <label htmlFor="new-product-barcode" className="block font-semibold text-[var(--text)] mb-1">
                Barcode (Prefilled)
              </label>
              <input
                id="new-product-barcode"
                type="text"
                value={newProduct.barcode}
                onChange={(e) => setNewProduct({ ...newProduct, barcode: e.target.value })}
                className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 font-mono text-[var(--text)] outline-none focus:border-[var(--primary)]"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="new-product-shelf" className="block font-semibold text-[var(--text)] mb-1">
                Shelf Life (Days)
              </label>
              <input
                id="new-product-shelf"
                type="number"
                min="1"
                placeholder="Leave empty if unknown"
                value={newProduct.shelf_life_days ?? ''}
                onChange={(e) =>
                  setNewProduct({
                    ...newProduct,
                    shelf_life_days: e.target.value === '' ? ('' as unknown as number) : Number(e.target.value),
                  })
                }
                className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)] outline-none focus:border-[var(--primary)]"
              />
            </div>
            <div>
              <label htmlFor="new-product-price" className="block font-semibold text-[var(--text)] mb-1">
                Selling Price (₹)
              </label>
              <input
                id="new-product-price"
                type="text"
                placeholder="Leave empty if not set"
                value={newProduct.selling_price}
                onChange={(e) => setNewProduct({ ...newProduct, selling_price: e.target.value })}
                className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)] outline-none focus:border-[var(--primary)]"
              />
            </div>
          </div>

          <div className="pt-4 flex items-center justify-end gap-2.5 border-t border-[var(--border)]">
            <Button variant="outline" size="sm" type="button" onClick={() => setIsProductSheetOpen(false)}>
              Cancel
            </Button>
            <Button
              id="submit-new-product-btn"
              variant="primary"
              size="sm"
              type="submit"
              disabled={createProductMutation.isPending}
            >
              {createProductMutation.isPending ? 'Registering...' : 'Register Product'}
            </Button>
          </div>
        </form>
      </Sheet>
    </div>
  );
};
