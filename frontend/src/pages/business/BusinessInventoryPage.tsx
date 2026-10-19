import React, { useState, useMemo } from 'react';
import {
  Package,
  Layers,
  Plus,
  Barcode,
  Tag,
} from 'lucide-react';
import { DataTable, type Column } from '../../components/ui/DataTable';
import { ExpiryPill } from '../../components/ui/ExpiryPill';
import { StatusBadge } from '../../components/ui/StatusBadge';
import { Button } from '../../components/ui/Button';
import { PageHeader } from '../../components/ui/PageHeader';
import { Sheet } from '../../components/ui/Sheet';
import {
  useBatches,
  useProducts,
  useCategories,
  useCreateBatch,
  useCreateProduct,
} from '../../hooks/useData';
import type { BatchWithProduct, Product } from '../../types';

interface BusinessInventoryPageProps {
  onTriggerToast: (msg: string) => void;
  onOpenCreateListing?: (batchId: number) => void;
}

export const BusinessInventoryPage: React.FC<BusinessInventoryPageProps> = ({
  onTriggerToast,
  onOpenCreateListing,
}) => {
  // Tabs: 'batches' | 'products'
  const [activeTab, setActiveTab] = useState<'batches' | 'products'>('batches');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');

  // Side Sheet state
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [sheetType, setSheetType] = useState<'batch' | 'product'>('batch');

  // Form states for Sheet
  const [newBatch, setNewBatch] = useState({
    product: 1,
    batch_code: '',
    initial_quantity: 20,
    current_quantity: 20,
    unit: 'kg',
    expiry_date: '',
    manufacturing_date: '',
    received_date: new Date().toISOString().split('T')[0],
  });

  const [newProduct, setNewProduct] = useState({
    name: '',
    sku: '',
    barcode: '',
    category: 1,
    unit: 'kg',
    cost_price: '50.00',
    selling_price: '70.00',
    min_stock_level: 10,
    shelf_life_days: 7,
  });

  // Queries & Mutations
  const { data: batches, isLoading: isBatchesLoading } = useBatches();
  const { data: products, isLoading: isProductsLoading } = useProducts();
  const { data: categories } = useCategories();
  const createBatchMutation = useCreateBatch();
  const createProductMutation = useCreateProduct();

  // Filtered Batches
  const filteredBatches = useMemo(() => {
    if (!batches) return [];
    return batches.filter((b: BatchWithProduct) => {
      const matchesStatus =
        statusFilter === 'ALL' || b.status === statusFilter;
      const matchesCategory =
        categoryFilter === 'ALL' ||
        (b.category && b.category.toLowerCase() === categoryFilter.toLowerCase());
      return matchesStatus && matchesCategory;
    });
  }, [batches, statusFilter, categoryFilter]);

  // Filtered Products
  const filteredProducts = useMemo(() => {
    if (!products) return [];
    return products.filter((p: Product) => {
      return (
        categoryFilter === 'ALL' ||
        (p.category_name && p.category_name.toLowerCase() === categoryFilter.toLowerCase())
      );
    });
  }, [products, categoryFilter]);

  // Handle Sheet Submit
  const handleSaveBatch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newBatch.batch_code || !newBatch.expiry_date) {
      onTriggerToast('Please complete batch code and expiry date');
      return;
    }
    createBatchMutation.mutate(
      {
        product: Number(newBatch.product),
        location: null,
        batch_code: newBatch.batch_code,
        quantity: String(newBatch.initial_quantity),
        initial_quantity: Number(newBatch.initial_quantity),
        current_quantity: Number(newBatch.initial_quantity),
        unit: newBatch.unit,
        expiry_date: newBatch.expiry_date,
        manufacturing_date: newBatch.manufacturing_date || newBatch.received_date,
        received_date: newBatch.received_date,
        status: 'ACTIVE',
      },
      {
        onSuccess: () => {
          setIsSheetOpen(false);
          onTriggerToast(`Added batch ${newBatch.batch_code} into FEFO rotation`);
        },
      }
    );
  };

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
        barcode: newProduct.barcode || Math.floor(100000000000 + Math.random() * 900000000000).toString(),
        category: Number(newProduct.category),
        unit: newProduct.unit,
        unit_cost: newProduct.cost_price || null,
        reorder_level: String(newProduct.min_stock_level || 10),
        is_active: true,
        cost_price: newProduct.cost_price,
        selling_price: newProduct.selling_price,
        min_stock_level: Number(newProduct.min_stock_level),
        shelf_life_days: Number(newProduct.shelf_life_days),
      },
      {
        onSuccess: () => {
          setIsSheetOpen(false);
          onTriggerToast(`Created product ${newProduct.name}`);
        },
      }
    );
  };

  // Batches Table Columns
  const batchColumns: Column<BatchWithProduct>[] = [
    {
      header: 'Product',
      accessor: (b) => (
        <div>
          <p className="font-semibold text-[var(--text)]">{b.product_name}</p>
          <span className="text-[11px] text-[var(--muted)]">{b.category || 'General Dairy'}</span>
        </div>
      ),
      sortable: true,
    },
    {
      header: 'Batch Code',
      accessor: (b) => <span className="font-mono text-xs">{b.batch_code}</span>,
      sortable: true,
    },
    {
      header: 'Barcode',
      accessor: (b) => (
        <span className="font-mono text-[11px] text-[var(--muted)] flex items-center gap-1">
          <Barcode className="w-3.5 h-3.5" />
          <span>{b.product_barcode || '8901030865421'}</span>
        </span>
      ),
    },
    {
      header: 'Available Stock',
      accessor: (b) => (
        <span className="tabular-nums font-semibold text-xs text-[var(--text)]">
          {b.quantity} {b.unit}
        </span>
      ),
      sortable: true,
    },
    {
      header: 'Expiry Date',
      accessor: (b) => <ExpiryPill expiryDate={b.expiry_date} />,
      sortable: true,
    },
    {
      header: 'Status',
      accessor: (b) => (
        <StatusBadge
          status={b.status}
          variant={
            b.status === 'ACTIVE'
              ? 'success'
              : b.status === 'EXPIRED'
              ? 'danger'
              : 'neutral'
          }
        >
          {b.status}
        </StatusBadge>
      ),
    },
  ];

  // Products Table Columns
  const productColumns: Column<Product>[] = [
    {
      header: 'Product Name',
      accessor: (p) => (
        <div>
          <p className="font-semibold text-[var(--text)]">{p.name}</p>
          <span className="text-[11px] text-[var(--muted)]">{p.category_name || 'Produce'}</span>
        </div>
      ),
      sortable: true,
    },
    {
      header: 'SKU',
      accessor: (p) => <span className="font-mono text-xs text-[var(--text)]">{p.sku}</span>,
      sortable: true,
    },
    {
      header: 'Barcode',
      accessor: (p) => (
        <span className="font-mono text-[11px] text-[var(--muted)] flex items-center gap-1">
          <Barcode className="w-3.5 h-3.5" />
          <span>{p.barcode || 'N/A'}</span>
        </span>
      ),
    },
    {
      header: 'Default Shelf Life',
      accessor: (p) => (
        <span className="text-xs text-[var(--text)] tabular-nums">
          {p.shelf_life_days} days
        </span>
      ),
    },
    {
      header: 'Unit Price',
      accessor: (p) => (
        <span className="text-xs font-semibold tabular-nums text-[var(--text)]">
          ₹{p.selling_price} / {p.unit}
        </span>
      ),
    },
    {
      header: 'Min Stock',
      accessor: (p) => (
        <span className="text-xs tabular-nums text-[var(--muted)]">
          {p.min_stock_level} {p.unit}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Header */}
      <PageHeader
        title="Inventory & Batches"
        description="Maintain FEFO inventory integrity, inspect batch shelf horizons, and manage registered SKUs."
        action={
          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSheetType('product');
                setIsSheetOpen(true);
              }}
              className="gap-1.5"
            >
              <Tag className="w-4 h-4" />
              <span>New Product SKU</span>
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setSheetType('batch');
                setIsSheetOpen(true);
              }}
              className="gap-1.5"
            >
              <Plus className="w-4 h-4" />
              <span>Inward Batch</span>
            </Button>
          </div>
        }
      />

      {/* Primary Tabs Control */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--border)] pb-3">
        <div className="inline-flex p-1 rounded-[8px] bg-[var(--surface-2)] border border-[var(--border)]">
          <button
            type="button"
            onClick={() => setActiveTab('batches')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-[6px] text-xs font-semibold transition-all ${
              activeTab === 'batches'
                ? 'bg-[var(--surface)] text-[var(--text)] shadow-xs'
                : 'text-[var(--muted)] hover:text-[var(--text)]'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Batches ({batches?.length || 0})</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('products')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-[6px] text-xs font-semibold transition-all ${
              activeTab === 'products'
                ? 'bg-[var(--surface)] text-[var(--text)] shadow-xs'
                : 'text-[var(--muted)] hover:text-[var(--text)]'
            }`}
          >
            <Package className="w-3.5 h-3.5" />
            <span>Products ({products?.length || 0})</span>
          </button>
        </div>

        {/* Filter Chips */}
        <div className="flex items-center gap-2 flex-wrap text-xs">
          {activeTab === 'batches' && (
            <div className="flex items-center gap-1.5">
              <span className="text-[var(--muted)] text-[11px] font-medium mr-1">Status:</span>
              {['ALL', 'ACTIVE', 'EXPIRED'].map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => setStatusFilter(st)}
                  className={`px-2.5 py-1 rounded-[6px] text-[11px] font-semibold border transition-colors ${
                    statusFilter === st
                      ? 'bg-[var(--primary)] text-white border-[var(--primary)]'
                      : 'bg-[var(--surface)] text-[var(--muted)] border-[var(--border)] hover:text-[var(--text)]'
                  }`}
                >
                  {st}
                </button>
              ))}
            </div>
          )}

          <div className="flex items-center gap-1.5">
            <span className="text-[var(--muted)] text-[11px] font-medium mr-1">Category:</span>
            {['ALL', 'Dairy', 'Produce', 'Prepared Foods'].map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setCategoryFilter(cat)}
                className={`px-2.5 py-1 rounded-[6px] text-[11px] font-semibold border transition-colors ${
                  categoryFilter === cat
                    ? 'bg-[var(--surface-2)] text-[var(--text)] border-[var(--primary)]'
                    : 'bg-[var(--surface)] text-[var(--muted)] border-[var(--border)] hover:text-[var(--text)]'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Data Table */}
      {activeTab === 'batches' ? (
        <DataTable
          data={filteredBatches}
          columns={batchColumns}
          keyExtractor={(b) => b.id}
          searchPlaceholder="Search product name, batch code, or barcode..."
          pageSize={10}
          isLoading={isBatchesLoading}
          actionsRenderer={(b) => (
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => onTriggerToast(`FEFO allocation prioritized for batch ${b.batch_code}`)}
                className="text-[11px] h-7 px-2"
              >
                Allocate
              </Button>
              {onOpenCreateListing && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onOpenCreateListing(b.id)}
                  className="text-[11px] h-7 px-2 text-[var(--accent)] hover:text-[var(--accent)]"
                >
                  List
                </Button>
              )}
            </div>
          )}
        />
      ) : (
        <DataTable
          data={filteredProducts}
          columns={productColumns}
          keyExtractor={(p) => p.id}
          searchPlaceholder="Search SKU, name, or barcode..."
          pageSize={10}
          isLoading={isProductsLoading}
          actionsRenderer={(p) => (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onTriggerToast(`Editing product SKU ${p.sku}`)}
              className="text-[11px] h-7 px-2"
            >
              Edit
            </Button>
          )}
        />
      )}

      {/* Side Sheet Drawer: Inward Batch or New Product */}
      <Sheet
        isOpen={isSheetOpen}
        onClose={() => setIsSheetOpen(false)}
        title={sheetType === 'batch' ? 'Inward Stock Batch' : 'Register Product SKU'}
        description={
          sheetType === 'batch'
            ? 'Add an inward food batch under strict FEFO horizon rotation'
            : 'Add a new perishable inventory catalog item'
        }
      >
        {sheetType === 'batch' ? (
          <form onSubmit={handleSaveBatch} className="space-y-4 text-xs">
            <div>
              <label className="block font-semibold text-[var(--text)] mb-1">Select Product</label>
              <select
                value={newBatch.product}
                onChange={(e) => setNewBatch({ ...newBatch, product: Number(e.target.value) })}
                className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)]"
              >
                {(products || []).map((p: Product) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.sku})
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-[var(--text)] mb-1">Batch Code</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. BTH-202610-91"
                  value={newBatch.batch_code}
                  onChange={(e) => setNewBatch({ ...newBatch, batch_code: e.target.value })}
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 font-mono text-[var(--text)]"
                />
              </div>
              <div>
                <label className="block font-semibold text-[var(--text)] mb-1">Quantity (kg / units)</label>
                <input
                  type="number"
                  required
                  min="1"
                  value={newBatch.initial_quantity}
                  onChange={(e) =>
                    setNewBatch({
                      ...newBatch,
                      initial_quantity: Number(e.target.value),
                      current_quantity: Number(e.target.value),
                    })
                  }
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)]"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-[var(--text)] mb-1">Expiry Date</label>
                <input
                  type="date"
                  required
                  value={newBatch.expiry_date}
                  onChange={(e) => setNewBatch({ ...newBatch, expiry_date: e.target.value })}
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)]"
                />
              </div>
              <div>
                <label className="block font-semibold text-[var(--text)] mb-1">Received Date</label>
                <input
                  type="date"
                  value={newBatch.received_date}
                  onChange={(e) => setNewBatch({ ...newBatch, received_date: e.target.value })}
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)]"
                />
              </div>
            </div>

            <div className="pt-4 flex items-center justify-end gap-2.5 border-t border-[var(--border)]">
              <Button variant="outline" size="sm" type="button" onClick={() => setIsSheetOpen(false)}>
                Cancel
              </Button>
              <Button variant="primary" size="sm" type="submit">
                Save Batch
              </Button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleSaveProduct} className="space-y-4 text-xs">
            <div>
              <label className="block font-semibold text-[var(--text)] mb-1">Product Name</label>
              <input
                type="text"
                required
                placeholder="e.g. Organic Farm Paneer 500g"
                value={newProduct.name}
                onChange={(e) => setNewProduct({ ...newProduct, name: e.target.value })}
                className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)]"
              />
            </div>

            <div>
              <label className="block font-semibold text-[var(--text)] mb-1">Product Category</label>
              <select
                value={newProduct.category}
                onChange={(e) => setNewProduct({ ...newProduct, category: Number(e.target.value) })}
                className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)]"
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
                <label className="block font-semibold text-[var(--text)] mb-1">SKU Code</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. PAN-500-ORG"
                  value={newProduct.sku}
                  onChange={(e) => setNewProduct({ ...newProduct, sku: e.target.value })}
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 font-mono text-[var(--text)]"
                />
              </div>
              <div>
                <label className="block font-semibold text-[var(--text)] mb-1">Barcode (EAN-13)</label>
                <input
                  type="text"
                  placeholder="e.g. 8901030865421"
                  value={newProduct.barcode}
                  onChange={(e) => setNewProduct({ ...newProduct, barcode: e.target.value })}
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 font-mono text-[var(--text)]"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-[var(--text)] mb-1">Shelf Life (Days)</label>
                <input
                  type="number"
                  min="1"
                  value={newProduct.shelf_life_days}
                  onChange={(e) => setNewProduct({ ...newProduct, shelf_life_days: Number(e.target.value) })}
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)]"
                />
              </div>
              <div>
                <label className="block font-semibold text-[var(--text)] mb-1">Selling Price (₹)</label>
                <input
                  type="text"
                  value={newProduct.selling_price}
                  onChange={(e) => setNewProduct({ ...newProduct, selling_price: e.target.value })}
                  className="w-full rounded-[8px] border border-[var(--border)] bg-[var(--surface-2)] p-2.5 text-[var(--text)]"
                />
              </div>
            </div>

            <div className="pt-4 flex items-center justify-end gap-2.5 border-t border-[var(--border)]">
              <Button variant="outline" size="sm" type="button" onClick={() => setIsSheetOpen(false)}>
                Cancel
              </Button>
              <Button variant="primary" size="sm" type="submit">
                Register Product
              </Button>
            </div>
          </form>
        )}
      </Sheet>
    </div>
  );
};
