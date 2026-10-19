import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { cn } from '../../lib/utils';

export interface MapMarker {
  id: string | number;
  latitude: number;
  longitude: number;
  title: string;
  subtitle?: string;
  badge?: string;
  isUserLocation?: boolean;
  onClick?: () => void;
}

interface MapViewProps {
  markers?: MapMarker[];
  center?: [number, number]; // [lat, lng]
  zoom?: number;
  className?: string;
  onMarkerSelect?: (marker: MapMarker) => void;
}

export const MapView: React.FC<MapViewProps> = ({
  markers = [],
  center = [12.9716, 77.5946], // Default Bengaluru
  zoom = 13,
  className,
  onMarkerSelect,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current) return;
    if (mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center,
      zoom,
      zoomControl: false,
    });

    // Add subtle OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    // Zoom control at bottom right
    L.control.zoom({ position: 'bottomright' }).addTo(map);

    const markersGroup = L.layerGroup().addTo(map);
    markersLayerRef.current = markersGroup;
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update Center and Zoom if changed
  useEffect(() => {
    if (mapInstanceRef.current && center) {
      mapInstanceRef.current.setView(center, zoom);
    }
  }, [center, zoom]);

  // Update Markers
  useEffect(() => {
    const map = mapInstanceRef.current;
    const layer = markersLayerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();

    markers.forEach((m) => {
      // Create modern custom SVG pin icon
      const isUser = !!m.isUserLocation;
      const color = isUser ? 'var(--primary)' : 'var(--accent)';
      const iconHtml = `
        <div style="
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;
          border-radius: 50%;
          background: ${color};
          color: #ffffff;
          box-shadow: 0 4px 12px rgba(0,0,0,0.3);
          border: 2px solid #ffffff;
          cursor: pointer;
          transform: translate(-50%, -50%);
          font-weight: 700;
          font-size: 13px;
        ">
          ${isUser ? '📍' : '🍲'}
        </div>
      `;

      const customIcon = L.divIcon({
        html: iconHtml,
        className: 'custom-map-pin',
        iconSize: [32, 32],
        iconAnchor: [16, 16],
      });

      const leafletMarker = L.marker([m.latitude, m.longitude], { icon: customIcon });

      const popupContent = `
        <div style="font-family: inherit; font-size: 12px; color: var(--text); padding: 4px;">
          <strong style="display: block; font-size: 13px; margin-bottom: 2px;">${m.title}</strong>
          ${m.subtitle ? `<span style="color: var(--muted); font-size: 11px;">${m.subtitle}</span>` : ''}
          ${m.badge ? `<div style="margin-top: 6px;"><span style="display: inline-block; padding: 2px 6px; border-radius: 6px; font-size: 10px; background: rgba(109, 91, 246, 0.15); color: var(--primary); font-weight: 600;">${m.badge}</span></div>` : ''}
        </div>
      `;

      leafletMarker.bindPopup(popupContent, {
        closeButton: false,
        className: 'custom-map-popup',
      });

      leafletMarker.on('click', () => {
        if (m.onClick) m.onClick();
        if (onMarkerSelect) onMarkerSelect(m);
      });

      layer.addLayer(leafletMarker);
    });
  }, [markers, onMarkerSelect]);

  return (
    <div
      ref={mapContainerRef}
      className={cn(
        'w-full h-full min-h-[300px] rounded-[12px] border border-[var(--border)] overflow-hidden z-0',
        className
      )}
      aria-label="Interactive Food Surplus Map"
    />
  );
};
