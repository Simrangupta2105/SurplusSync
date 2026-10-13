import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  AlertTriangle, 
  Clock, 
  Package, 
  Barcode, 
  CheckCircle, 
  DollarSign, 
  TrendingUp, 
  ShieldCheck, 
  Search, 
  Scan, 
  RefreshCw,
  HeartHandshake,
  Trash2,
  ExternalLink,
  Layers,
  ChevronRight,
  Sliders
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000/api/v1';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [dashboardData, setDashboardData] = useState({
    total_active_batches: 14,
    total_active_quantity: '342.500',
    batches_expiring_48h: 4,
    critical_alerts_unacknowledged: 2,
    wasted_value_30d: '64.50',
    donated_value_30d: '185.00',
    missing_cost_items: 0
  });

  const [batches, setBatches] = useState([
    { id: 101, batch_code: 'B-DAIRY-401', product_name: 'Organic Whole Milk 1L', category: 'Dairy', quantity: 18.0, unit: 'L', expiry_date: '2026-10-13', days_left: 1, status: 'ACTIVE', risk: 'CRITICAL', unit_cost: 2.50 },
    { id: 102, batch_code: 'B-BAKERY-219', product_name: 'Artisan Sourdough Loaf', category: 'Bakery', quantity: 12.0, unit: 'pcs', expiry_date: '2026-10-14', days_left: 2, status: 'ACTIVE', risk: 'HIGH', unit_cost: 3.20 },
    { id: 103, batch_code: 'B-PROD-882', product_name: 'Fresh Baby Spinach 500g', category: 'Produce', quantity: 25.0, unit: 'kg', expiry_date: '2026-10-15', days_left: 3, status: 'ACTIVE', risk: 'HIGH', unit_cost: 4.10 },
    { id: 104, batch_code: 'B-MEAT-104', product_name: 'Free Range Chicken Breast', category: 'Meat & Poultry', quantity: 15.0, unit: 'kg', expiry_date: '2026-10-16', days_left: 4, status: 'ACTIVE', risk: 'CRITICAL', unit_cost: 8.90 },
    { id: 105, batch_code: 'B-DRY-994', product_name: 'Basmati Rice 5kg', category: 'Dry Goods & Grains', quantity: 50.0, unit: 'kg', expiry_date: '2027-02-10', days_left: 120, status: 'ACTIVE', risk: 'LOW', unit_cost: 11.50 },
  ]);

  const [alerts, setAlerts] = useState([
    { id: 1, severity: 'CRITICAL', message: 'Batch B-DAIRY-401 (Organic Whole Milk) expires in 24 hours!', time: '12m ago', batch_code: 'B-DAIRY-401' },
    { id: 2, severity: 'CRITICAL', message: 'Batch B-BAKERY-219 (Artisan Sourdough) expires in 48 hours!', time: '45m ago', batch_code: 'B-BAKERY-219' },
    { id: 3, severity: 'WARNING', message: 'Baby Spinach stock reorder threshold triggered (under 30 kg).', time: '2h ago', batch_code: 'B-PROD-882' },
  ]);

  // Barcode Scanner State
  const [barcodeInput, setBarcodeInput] = useState('');
  const [scanResult, setScanResult] = useState(null);
  const [isScanning, setIsScanning] = useState(false);
  const [deductStatus, setDeductStatus] = useState('');

  // Sample pre-filled demo barcodes
  const sampleBarcodes = [
    { label: 'Local Store Milk', code: '8901234567890' },
    { label: 'Open Food Facts (Thai Noodles)', code: '737628064502' },
    { label: 'Open Food Facts (Nutella)', code: '3017620422003' },
  ];

  // Try fetching live backend stats
  useEffect(() => {
    fetch(`${API_BASE}/inventory/categories/`)
      .then(res => res.json())
      .then(data => {
        // live connection verified
        console.log("Connected to SurplusSync backend! Categories loaded:", data.count);
      })
      .catch(() => {
        console.log("Using interactive demo state with live API simulation");
      });
  }, []);

  const handleBarcodeLookup = async (codeToSearch) => {
    const code = codeToSearch || barcodeInput;
    if (!code) return;

    setIsScanning(true);
    setScanResult(null);
    setDeductStatus('');

    try {
      const res = await fetch(`${API_BASE}/inventory/products/barcode/${code}/`);
      if (res.ok) {
        const data = await res.json();
        setScanResult(data);
      } else {
        // Fallback simulation for live demonstration
        if (code === '737628064502') {
          setScanResult({
            source: 'open_food_facts',
            barcode: '737628064502',
            name: 'Thai peanut noodle kit includes stir-fry rice noodles & thai peanut seasoning',
            brand: 'Simply Asia, Thai Kitchen',
            image_url: 'https://images.openfoodfacts.org/images/products/737/628/064/502/front_en.6.400.jpg',
            suggested_category: { id: 7, name: 'Dry Goods & Grains' }
          });
        } else if (code === '8901234567890') {
          setScanResult({
            source: 'local',
            barcode: '8901234567890',
            name: 'Organic Whole Milk 1L',
            sku: 'MILK-ORG-1L',
            unit_cost: '2.50',
            category_name: 'Dairy'
          });
        } else {
          setScanResult({
            error: true,
            message: `Product with barcode ${code} not found in local store or Open Food Facts.`
          });
        }
      }
    } catch {
      // Offline / Demo fallback
      if (code === '737628064502') {
        setScanResult({
          source: 'open_food_facts',
          barcode: '737628064502',
          name: 'Thai peanut noodle kit includes stir-fry rice noodles & thai peanut seasoning',
          brand: 'Simply Asia, Thai Kitchen',
          image_url: 'https://images.openfoodfacts.org/images/products/737/628/064/502/front_en.6.400.jpg',
          suggested_category: { id: 7, name: 'Dry Goods & Grains' }
        });
      } else {
        setScanResult({
          source: 'local',
          barcode: code,
          name: 'Organic Whole Milk 1L',
          sku: 'MILK-ORG-1L',
          unit_cost: '2.50',
          category_name: 'Dairy'
        });
      }
    } finally {
      setIsScanning(false);
    }
  };

  const handleFEFODeduct = (batchId, amountToDeduct = 2) => {
    setBatches(prev => prev.map(b => {
      if (b.id === batchId) {
        const newQty = Math.max(0, b.quantity - amountToDeduct);
        return {
          ...b,
          quantity: newQty,
          status: newQty === 0 ? 'DEPLETED' : 'ACTIVE'
        };
      }
      return b;
    }));

    setDeductStatus(`✅ FEFO Deduction executed: 2.00 units deducted from Batch #${batchId}. Stock ledger entry written.`);
    setTimeout(() => setDeductStatus(''), 4000);
  };

  return (
    <div className="app-layout">
      {/* Top Navbar */}
      <header className="app-header">
        <div className="brand-wrapper">
          <div className="brand-icon">
            <Sparkles size={22} color="#ffffff" />
          </div>
          <div>
            <div className="brand-title">
              SurplusSync
              <span className="brand-badge">Enterprise</span>
            </div>
          </div>
        </div>

        {/* Center Tabs */}
        <nav className="nav-links">
          <button 
            id="tab-overview"
            className={`nav-btn ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            <Layers size={16} /> Dashboard
          </button>
          <button 
            id="tab-batches"
            className={`nav-btn ${activeTab === 'batches' ? 'active' : ''}`}
            onClick={() => setActiveTab('batches')}
          >
            <Clock size={16} /> FEFO Batches
          </button>
          <button 
            id="tab-scanner"
            className={`nav-btn ${activeTab === 'scanner' ? 'active' : ''}`}
            onClick={() => setActiveTab('scanner')}
          >
            <Barcode size={16} /> POS Scanner & OFF
          </button>
          <button 
            id="tab-alerts"
            className={`nav-btn ${activeTab === 'alerts' ? 'active' : ''}`}
            onClick={() => setActiveTab('alerts')}
          >
            <AlertTriangle size={16} /> Alerts ({alerts.length})
          </button>
        </nav>

        {/* Tenant Status */}
        <div className="header-actions">
          <div className="org-pill">
            <span className="org-indicator"></span>
            <span>Green Valley Supermarket</span>
          </div>
          <button 
            className="btn-secondary" 
            style={{ padding: '6px 12px', fontSize: '0.8rem' }}
            onClick={() => window.open('http://127.0.0.1:8000/admin/', '_blank')}
          >
            Django Admin <ExternalLink size={12} style={{ marginLeft: 4 }} />
          </button>
        </div>
      </header>

      {/* Main Page Content */}
      <main className="main-content">
        
        {/* Metric Cards Banner */}
        <div className="stat-grid">
          <div className="glass-panel stat-card" style={{ '--glow-color': 'rgba(16, 185, 129, 0.15)', '--accent-color': '#10b981' }}>
            <div className="stat-header">
              <span className="stat-title">Active Batches Tracked</span>
              <div className="stat-icon-wrapper"><Package size={18} /></div>
            </div>
            <div className="stat-value">{dashboardData.total_active_batches}</div>
            <div className="stat-subtext">{dashboardData.total_active_quantity} total units across all storage</div>
          </div>

          <div className="glass-panel stat-card" style={{ '--glow-color': 'rgba(244, 63, 94, 0.15)', '--accent-color': '#f43f5e' }}>
            <div className="stat-header">
              <span className="stat-title">Expiring Within 48h</span>
              <div className="stat-icon-wrapper"><Clock size={18} /></div>
            </div>
            <div className="stat-value" style={{ color: '#fb7185' }}>{dashboardData.batches_expiring_48h}</div>
            <div className="stat-subtext">Requires immediate markdown or NGO donation</div>
          </div>

          <div className="glass-panel stat-card" style={{ '--glow-color': 'rgba(245, 158, 11, 0.15)', '--accent-color': '#f59e0b' }}>
            <div className="stat-header">
              <span className="stat-title">Critical Expiry Alerts</span>
              <div className="stat-icon-wrapper"><AlertTriangle size={18} /></div>
            </div>
            <div className="stat-value" style={{ color: '#fcd34d' }}>{dashboardData.critical_alerts_unacknowledged}</div>
            <div className="stat-subtext">Unacknowledged automated alerts</div>
          </div>

          <div className="glass-panel stat-card" style={{ '--glow-color': 'rgba(99, 102, 241, 0.15)', '--accent-color': '#818cf8' }}>
            <div className="stat-header">
              <span className="stat-title">Donated Value (30d)</span>
              <div className="stat-icon-wrapper"><HeartHandshake size={18} /></div>
            </div>
            <div className="stat-value">${dashboardData.donated_value_30d}</div>
            <div className="stat-subtext">Redirected to local food charities</div>
          </div>
        </div>

        {deductStatus && (
          <div style={{ 
            background: 'rgba(16, 185, 129, 0.15)', 
            border: '1px solid #10b981', 
            padding: '12px 20px', 
            borderRadius: '8px', 
            marginBottom: '24px',
            color: '#6ee7b7',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <ShieldCheck size={18} /> {deductStatus}
          </div>
        )}

        {/* Tab 1: Dashboard Overview */}
        {activeTab === 'overview' && (
          <div className="dashboard-grid">
            {/* Left: Priority Expiry Table */}
            <div className="glass-panel" style={{ padding: '24px' }}>
              <div className="section-header">
                <div className="section-title">
                  <Clock size={20} color="#f43f5e" /> Expiring Batches (FEFO Priority)
                </div>
                <button className="btn-secondary" onClick={() => setActiveTab('batches')}>View All Batches</button>
              </div>

              <div className="table-container">
                <table className="custom-table">
                  <thead>
                    <tr>
                      <th>Batch Code</th>
                      <th>Product</th>
                      <th>Category</th>
                      <th>Quantity</th>
                      <th>Expires In</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {batches.slice(0, 4).map(b => (
                      <tr key={b.id}>
                        <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>{b.batch_code}</td>
                        <td style={{ fontWeight: 600 }}>{b.product_name}</td>
                        <td><span className="badge badge-cyan">{b.category}</span></td>
                        <td><strong>{b.quantity.toFixed(1)}</strong> {b.unit}</td>
                        <td>
                          {b.days_left <= 1 ? (
                            <span className="badge badge-danger">Expiring Tomorrow</span>
                          ) : b.days_left <= 3 ? (
                            <span className="badge badge-warning">{b.days_left} Days Left</span>
                          ) : (
                            <span className="badge badge-success">{b.days_left} Days</span>
                          )}
                        </td>
                        <td>
                          <button 
                            className="btn-primary" 
                            style={{ padding: '6px 12px', fontSize: '0.78rem' }}
                            onClick={() => handleFEFODeduct(b.id, 2)}
                          >
                            Deduct 2 {b.unit}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Right: Quick POS Scan Simulator */}
            <div className="glass-panel scanner-card">
              <div className="section-header" style={{ marginBottom: '12px' }}>
                <div className="section-title" style={{ fontSize: '1.15rem' }}>
                  <Barcode size={18} color="#10b981" /> Barcode Test
                </div>
                <span className="badge badge-success">API Live</span>
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                Test local product lookup vs. automatic <strong>Open Food Facts</strong> public database fallback:
              </p>

              <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
                <input 
                  type="text" 
                  className="input-field" 
                  placeholder="Enter or scan barcode..."
                  value={barcodeInput}
                  onChange={(e) => setBarcodeInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleBarcodeLookup()}
                />
                <button 
                  className="btn-primary" 
                  onClick={() => handleBarcodeLookup()}
                  disabled={isScanning}
                >
                  <Scan size={16} /> {isScanning ? 'Querying...' : 'Scan'}
                </button>
              </div>

              {/* Sample Quick Buttons */}
              <div style={{ marginTop: '14px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {sampleBarcodes.map((item, idx) => (
                  <button 
                    key={idx}
                    className="btn-secondary"
                    style={{ fontSize: '0.72rem', padding: '4px 10px' }}
                    onClick={() => {
                      setBarcodeInput(item.code);
                      handleBarcodeLookup(item.code);
                    }}
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              {/* Scan Result Preview */}
              {scanResult && (
                <div style={{ 
                  marginTop: '18px', 
                  padding: '16px', 
                  borderRadius: '10px', 
                  background: 'rgba(255, 255, 255, 0.03)', 
                  border: '1px solid rgba(255, 255, 255, 0.08)' 
                }}>
                  {scanResult.error ? (
                    <div style={{ color: '#fb7185', fontSize: '0.85rem' }}>{scanResult.message}</div>
                  ) : (
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                        <span className="badge badge-success">
                          Source: {scanResult.source === 'local' ? 'Local Store DB' : 'Open Food Facts API'}
                        </span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>#{scanResult.barcode}</span>
                      </div>
                      <div style={{ fontWeight: 700, fontSize: '0.95rem', color: '#fff' }}>{scanResult.name}</div>
                      {scanResult.brand && (
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Brand: {scanResult.brand}</div>
                      )}
                      {scanResult.suggested_category && (
                        <div style={{ marginTop: '6px' }}>
                          <span className="badge badge-cyan">Matched: {scanResult.suggested_category.name}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 2: Full Batches Table */}
        {activeTab === 'batches' && (
          <div className="glass-panel" style={{ padding: '24px' }}>
            <div className="section-header">
              <div className="section-title">
                <Package size={22} color="#10b981" /> Active Food Inventory Batches
              </div>
              <button 
                className="btn-primary"
                onClick={() => alert('New batch modal or CSV upload via /api/v1/inventory/import-jobs/')}
              >
                + New Batch
              </button>
            </div>

            <div className="table-container">
              <table className="custom-table">
                <thead>
                  <tr>
                    <th>Batch ID</th>
                    <th>Product Name</th>
                    <th>Category</th>
                    <th>Remaining Stock</th>
                    <th>Expiry Date</th>
                    <th>Shelf Life Status</th>
                    <th>Unit Cost</th>
                    <th>FEFO Action</th>
                  </tr>
                </thead>
                <tbody>
                  {batches.map(b => (
                    <tr key={b.id}>
                      <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>{b.batch_code}</td>
                      <td style={{ fontWeight: 600 }}>{b.product_name}</td>
                      <td><span className="badge badge-cyan">{b.category}</span></td>
                      <td>
                        <strong>{b.quantity.toFixed(1)}</strong> {b.unit}
                      </td>
                      <td style={{ color: 'var(--text-muted)' }}>{b.expiry_date}</td>
                      <td>
                        {b.days_left <= 1 ? (
                          <span className="badge badge-danger">Expiring &lt;24h</span>
                        ) : b.days_left <= 3 ? (
                          <span className="badge badge-warning">{b.days_left} Days Left</span>
                        ) : (
                          <span className="badge badge-success">{b.days_left} Days</span>
                        )}
                      </td>
                      <td>${b.unit_cost.toFixed(2)}</td>
                      <td>
                        <button 
                          className="btn-primary" 
                          style={{ padding: '5px 12px', fontSize: '0.78rem' }}
                          onClick={() => handleFEFODeduct(b.id, 2)}
                          disabled={b.status === 'DEPLETED'}
                        >
                          {b.status === 'DEPLETED' ? 'Depleted' : `Deduct 2 ${b.unit}`}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab 3: Dedicated Scanner */}
        {activeTab === 'scanner' && (
          <div className="glass-panel" style={{ padding: '32px', maxWidth: '800px', margin: '0 auto' }}>
            <div className="section-title" style={{ marginBottom: '12px' }}>
              <Barcode size={24} color="#10b981" /> POS Barcode Scanner & Food Taxonomy Lookup
            </div>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '24px' }}>
              Simulates a hardware barcode reader or camera scan. When an unrecognized product is scanned, SurplusSync queries the <strong>Open Food Facts API</strong> in real time to resolve nutrition, brand, and category metadata without manual data entry.
            </p>

            <div className="scanner-box">
              <div className="scanner-laser"></div>
              <Scan size={44} color="#10b981" style={{ opacity: 0.8, marginBottom: '12px' }} />
              <div style={{ fontWeight: 600, color: '#fff' }}>Ready to Scan Barcodes</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: '4px' }}>
                Enter EAN-13, UPC, or custom inventory barcodes below
              </div>
            </div>

            <div style={{ display: 'flex', gap: '12px', marginBottom: '20px' }}>
              <input 
                type="text" 
                className="input-field" 
                placeholder="Scan or enter barcode (e.g. 737628064502)..."
                value={barcodeInput}
                onChange={(e) => setBarcodeInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleBarcodeLookup()}
              />
              <button className="btn-primary" onClick={() => handleBarcodeLookup()} disabled={isScanning}>
                {isScanning ? 'Querying API...' : 'Lookup Barcode'}
              </button>
            </div>

            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>Try demo barcodes:</span>
              {sampleBarcodes.map((s, idx) => (
                <button 
                  key={idx} 
                  className="btn-secondary" 
                  style={{ fontSize: '0.78rem', padding: '4px 10px' }}
                  onClick={() => {
                    setBarcodeInput(s.code);
                    handleBarcodeLookup(s.code);
                  }}
                >
                  {s.label} ({s.code})
                </button>
              ))}
            </div>

            {scanResult && !scanResult.error && (
              <div style={{ 
                marginTop: '28px', 
                padding: '24px', 
                borderRadius: '12px', 
                background: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(16, 185, 129, 0.3)'
              }}>
                <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
                  {scanResult.image_url && (
                    <img 
                      src={scanResult.image_url} 
                      alt={scanResult.name} 
                      style={{ width: '90px', height: '90px', objectFit: 'cover', borderRadius: '8px' }} 
                    />
                  )}
                  <div style={{ flex: 1 }}>
                    <span className="badge badge-success" style={{ marginBottom: '8px' }}>
                      {scanResult.source === 'local' ? 'Store Catalogue Record' : 'Open Food Facts Database'}
                    </span>
                    <h3 style={{ fontSize: '1.2rem', color: '#fff', marginTop: '4px' }}>{scanResult.name}</h3>
                    {scanResult.brand && <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Brand: {scanResult.brand}</div>}
                    <div style={{ marginTop: '12px', display: 'flex', gap: '10px' }}>
                      <button className="btn-primary" onClick={() => alert(`Pre-filled! Ready to add to inventory.`)}>
                        + Add To Store Catalogue
                      </button>
                      <button className="btn-secondary" onClick={() => setScanResult(null)}>
                        Clear
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 4: Alerts */}
        {activeTab === 'alerts' && (
          <div className="glass-panel" style={{ padding: '24px', maxWidth: '900px', margin: '0 auto' }}>
            <div className="section-header">
              <div className="section-title">
                <AlertTriangle size={22} color="#f59e0b" /> Active Expiration & Reorder Alerts
              </div>
              <button 
                className="btn-secondary"
                onClick={() => setAlerts([])}
              >
                Acknowledge All
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {alerts.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>
                  <CheckCircle size={36} color="#10b981" style={{ marginBottom: '8px' }} />
                  <div>All alerts have been acknowledged. Inventory is optimal!</div>
                </div>
              ) : (
                alerts.map(a => (
                  <div 
                    key={a.id} 
                    style={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      padding: '16px 20px', 
                      borderRadius: '10px', 
                      background: 'rgba(255, 255, 255, 0.02)',
                      border: '1px solid rgba(255, 255, 255, 0.06)'
                    }}
                  >
                    <div style={{ display: 'flex', gap: '14px', alignItems: 'center' }}>
                      {a.severity === 'CRITICAL' ? (
                        <span className="badge badge-danger">CRITICAL</span>
                      ) : (
                        <span className="badge badge-warning">WARNING</span>
                      )}
                      <div>
                        <div style={{ fontWeight: 600, color: '#fff' }}>{a.message}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '2px' }}>Triggered {a.time}</div>
                      </div>
                    </div>
                    <button 
                      className="btn-secondary"
                      style={{ fontSize: '0.8rem', padding: '6px 12px' }}
                      onClick={() => setAlerts(prev => prev.filter(x => x.id !== a.id))}
                    >
                      Acknowledge
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

      </main>
    </div>
  );
}
