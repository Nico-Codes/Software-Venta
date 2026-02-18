import { useEffect, useState } from "react";

import {
  createProduct,
  listCategoriesAdmin,
  listProductsAdmin,
  updateProduct,
} from "../tauri";
import { CategoryAdminSummary, ProductAdminRow } from "../types";

type Notice = {
  tone: "ok" | "error" | "info";
  text: string;
};

type ProductFormState = {
  name: string;
  barcode: string;
  categoryId: string;
  cost: string;
  salePrice: string;
  stock: string;
  minStock: string;
  autoPrice: boolean;
  active: boolean;
};

const EMPTY_FORM: ProductFormState = {
  name: "",
  barcode: "",
  categoryId: "",
  cost: "0",
  salePrice: "0",
  stock: "1",
  minStock: "0",
  autoPrice: true,
  active: true,
};

const moneyFormatter = new Intl.NumberFormat("es-AR", {
  style: "currency",
  currency: "ARS",
  maximumFractionDigits: 2,
});

function toErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  return "No se pudo completar la operacion";
}

function parseDecimal(raw: string): number {
  const parsed = Number.parseFloat(raw.replace(",", "."));
  if (!Number.isFinite(parsed)) {
    return 0;
  }
  return parsed;
}

function mapProductToForm(product: ProductAdminRow): ProductFormState {
  return {
    name: product.name,
    barcode: product.barcode ?? "",
    categoryId: String(product.categoryId),
    cost: product.cost.toFixed(2),
    salePrice: product.salePrice.toFixed(2),
    stock: product.stock.toFixed(2),
    minStock: product.minStock.toFixed(2),
    autoPrice: product.autoPrice,
    active: product.active,
  };
}

export function ProductsPage() {
  const [categories, setCategories] = useState<CategoryAdminSummary[]>([]);
  const [products, setProducts] = useState<ProductAdminRow[]>([]);
  const [selectedProductId, setSelectedProductId] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [form, setForm] = useState<ProductFormState>(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);

  async function reloadCategories() {
    const rows = await listCategoriesAdmin();
    setCategories(rows);
    setForm((current) => {
      if (current.categoryId || !rows[0]) {
        return current;
      }
      return { ...current, categoryId: String(rows[0].id) };
    });
  }

  async function reloadProducts(preferProductId?: string) {
    setLoading(true);
    try {
      const rows = await listProductsAdmin(
        searchTerm.trim() || undefined,
        categoryFilter ? Number.parseInt(categoryFilter, 10) : undefined,
        includeInactive,
        500,
      );
      setProducts(rows);

      const selected =
        rows.find((row) => String(row.id) === (preferProductId ?? selectedProductId)) ??
        null;
      if (selected) {
        setSelectedProductId(String(selected.id));
        setForm(mapProductToForm(selected));
      } else {
        setSelectedProductId("");
      }
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
      setProducts([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        await reloadCategories();
        await reloadProducts();
      } catch (error) {
        if (!mounted) {
          return;
        }
        setNotice({ tone: "error", text: toErrorMessage(error) });
      }
    })();
    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleNew() {
    setSelectedProductId("");
    setForm((current) => ({
      ...EMPTY_FORM,
      categoryId: current.categoryId || (categories[0] ? String(categories[0].id) : ""),
    }));
  }

  async function handleSave() {
    const cleanName = form.name.trim();
    const cleanBarcode = form.barcode.trim();
    const categoryId = Number.parseInt(form.categoryId, 10);
    const cost = parseDecimal(form.cost);
    const salePrice = parseDecimal(form.salePrice);
    const stock = parseDecimal(form.stock);
    const minStock = parseDecimal(form.minStock);

    if (!cleanName) {
      setNotice({ tone: "error", text: "Ingresa nombre del producto." });
      return;
    }
    if (!Number.isFinite(categoryId)) {
      setNotice({ tone: "error", text: "Selecciona una categoria." });
      return;
    }
    if (cost < 0) {
      setNotice({ tone: "error", text: "El costo no puede ser negativo." });
      return;
    }
    if (minStock < 0) {
      setNotice({ tone: "error", text: "El stock minimo no puede ser negativo." });
      return;
    }
    if (stock < 0 || (!selectedProductId && stock <= 0)) {
      setNotice({
        tone: "error",
        text: selectedProductId
          ? "El stock no puede ser negativo."
          : "El stock inicial debe ser mayor a cero.",
      });
      return;
    }
    if (!form.autoPrice && salePrice < 0) {
      setNotice({ tone: "error", text: "El precio de venta no puede ser negativo." });
      return;
    }

    setSaving(true);
    try {
      if (!selectedProductId) {
        const created = await createProduct({
          name: cleanName,
          barcode: cleanBarcode,
          categoryId,
          cost,
          salePrice,
          stock,
          minStock,
          autoPrice: form.autoPrice,
        });
        setNotice({ tone: "ok", text: `Producto ${created.name} creado.` });
        await reloadProducts(String(created.id));
      } else {
        const updated = await updateProduct({
          id: Number.parseInt(selectedProductId, 10),
          name: cleanName,
          barcode: cleanBarcode,
          categoryId,
          cost,
          salePrice,
          stock,
          minStock,
          autoPrice: form.autoPrice,
          active: form.active,
        });
        setNotice({ tone: "ok", text: `Producto ${updated.name} actualizado.` });
        await reloadProducts(String(updated.id));
      }
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="products-grid">
      <section className="panel products-list-panel">
        <header className="section-head">
          <h2>Productos</h2>
          <p>ABM completo con control de precios automaticos y stock.</p>
        </header>

        {notice && (
          <div className={`notice-strip notice-${notice.tone}`}>
            <span>{notice.text}</span>
          </div>
        )}

        <div className="products-toolbar">
          <label className="field">
            <span>Buscar</span>
            <input
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Nombre o codigo"
            />
          </label>
          <label className="field">
            <span>Categoria</span>
            <div className="select-wrap">
              <select
                value={categoryFilter}
                onChange={(event) => setCategoryFilter(event.target.value)}
              >
                <option value="">Todas</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </div>
          </label>
          <label className="switch-row">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(event) => setIncludeInactive(event.target.checked)}
            />
            <span>Mostrar inactivos</span>
          </label>
          <button type="button" onClick={() => void reloadProducts()} disabled={loading}>
            {loading ? "Cargando..." : "Filtrar"}
          </button>
          <button type="button" className="button-soft" onClick={handleNew}>
            Nuevo producto
          </button>
        </div>

        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>Producto</th>
                <th>Categoria</th>
                <th>Precio</th>
                <th>Stock</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {products.length <= 0 ? (
                <tr>
                  <td colSpan={5} className="table-empty">
                    No hay productos para mostrar.
                  </td>
                </tr>
              ) : (
                products.map((product) => (
                  <tr
                    key={product.id}
                    className={String(product.id) === selectedProductId ? "row-selected" : ""}
                    onClick={() => {
                      setSelectedProductId(String(product.id));
                      setForm(mapProductToForm(product));
                    }}
                  >
                    <td>{product.name}</td>
                    <td>{product.categoryName}</td>
                    <td>{moneyFormatter.format(product.salePrice)}</td>
                    <td>{product.stock.toFixed(2)}</td>
                    <td>{product.active ? "Activo" : "Inactivo"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <aside className="panel products-editor-panel">
        <header className="section-head">
          <h2>{selectedProductId ? "Editar producto" : "Crear producto"}</h2>
          <p>Precio automatico usa margen de categoria + redondeo configurado.</p>
        </header>

        <div className="products-form">
          <label className="field">
            <span>Nombre</span>
            <input
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
            />
          </label>

          <label className="field">
            <span>Codigo de barras</span>
            <input
              value={form.barcode}
              onChange={(event) => setForm((prev) => ({ ...prev, barcode: event.target.value }))}
            />
          </label>

          <label className="field">
            <span>Categoria</span>
            <div className="select-wrap">
              <select
                value={form.categoryId}
                onChange={(event) => setForm((prev) => ({ ...prev, categoryId: event.target.value }))}
              >
                <option value="">Seleccionar</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </div>
          </label>

          <div className="split-grid">
            <label className="field">
              <span>Costo</span>
              <input
                type="number"
                min={0}
                step="0.01"
                value={form.cost}
                onChange={(event) => setForm((prev) => ({ ...prev, cost: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Precio venta</span>
              <input
                type="number"
                min={0}
                step="0.01"
                value={form.salePrice}
                disabled={form.autoPrice}
                onChange={(event) => setForm((prev) => ({ ...prev, salePrice: event.target.value }))}
              />
            </label>
          </div>

          <div className="split-grid">
            <label className="field">
              <span>Stock</span>
              <input
                type="number"
                min={0}
                step="0.01"
                value={form.stock}
                onChange={(event) => setForm((prev) => ({ ...prev, stock: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Stock minimo</span>
              <input
                type="number"
                min={0}
                step="0.01"
                value={form.minStock}
                onChange={(event) => setForm((prev) => ({ ...prev, minStock: event.target.value }))}
              />
            </label>
          </div>

          <label className="switch-row">
            <input
              type="checkbox"
              checked={form.autoPrice}
              onChange={(event) => setForm((prev) => ({ ...prev, autoPrice: event.target.checked }))}
            />
            <span>Precio automatico por categoria</span>
          </label>

          <label className="switch-row">
            <input
              type="checkbox"
              checked={form.active}
              onChange={(event) => setForm((prev) => ({ ...prev, active: event.target.checked }))}
            />
            <span>Producto activo</span>
          </label>

          <button type="button" onClick={handleSave} disabled={saving}>
            {saving ? "Guardando..." : selectedProductId ? "Actualizar producto" : "Crear producto"}
          </button>
        </div>
      </aside>
    </section>
  );
}
