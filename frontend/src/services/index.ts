import { LiveSource } from './liveSource';
import { DemoSource, demoSource } from './demoSource';
import type { DataSource, FeatureKey } from './dataSource';

export * from './dataSource';
export * from './auth';
export { LiveSource } from './liveSource';
export { DemoSource, demoSource };

const envMode = (import.meta.env.VITE_DATA_MODE || 'demo').toLowerCase();
const storedMode = typeof window !== 'undefined' ? localStorage.getItem('surplussync_data_mode') : null;

export const defaultMode: 'live' | 'demo' = storedMode === 'live' || storedMode === 'demo'
  ? storedMode
  : (envMode === 'live' ? 'live' : 'demo');

export const liveSource = new LiveSource();

let currentSource: DataSource = defaultMode === 'live' ? liveSource : demoSource;

export function getDataSource(): DataSource {
  return currentSource;
}

export function setDataSourceMode(mode: 'live' | 'demo'): void {
  currentSource = mode === 'live' ? liveSource : demoSource;
  if (typeof window !== 'undefined') {
    localStorage.setItem('surplussync_data_mode', mode);
    window.dispatchEvent(new Event('surplussync_mode_change'));
  }
}

export function isFeatureLive(feature: FeatureKey): boolean {
  return currentSource.isFeatureLive(feature);
}

export const dataSource = new Proxy({} as DataSource, {
  get(_target, prop) {
    const src = getDataSource();
    const val = (src as unknown as Record<string, unknown>)[prop as string];
    if (typeof val === 'function') {
      return val.bind(src);
    }
    return val;
  },
});
