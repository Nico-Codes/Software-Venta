import { KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  createCombo,
  deleteCombo,
  listCombosAdmin,
  listProductsAdmin,
  updateCombo,
} from "../tauri";
import { ComboAdminRow, ProductAdminRow } from "../types";
import { formatInteger, formatMoney, parseIntegerInput } from "../utils/number";

type Notice = {
  tone: "ok" | "error" | "info";
  text: string;
};

type ComboFormItem = {
  productId: number;
  quantity: number;
};

function toErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  return "No se pudo completar la operacion";
}

function toItemsPayload(items: ComboFormItem[]): { productId: number; quantity: number }[] {
  return items
    .filter((item) => item.productId > 0 && item.quantity > 0)
    .map((item) => ({
      productId: item.productId,
      quantity: item.quantity,
    }));
}

export function CombosPage() {
  const barcodeInputRef = useRef<HTMLInputElement | null>(null);

  const [combos, setCombos] = useState<ComboAdminRow[]>([]);
  const [products, setProducts] = useState<ProductAdminRow[]>([]);
  const [selectedComboId, setSelectedComboId] = useState("");
  const [nameInput, setNameInput] = useState("");
  const [discountInput, setDiscountInput] = useState("5");
  const [activeInput, setActiveInput] = useState(true);
  const [formItems, setFormItems] = useState<ComboFormItem[]>([]);
  const [newItemProductId, setNewItemProductId] = useState("");
  const [newItemQty, setNewItemQty] = useState("1");
  const [barcodeInput, setBarcodeInput] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);

  const productMap = useMemo(() => {
    const map = new Map<number, ProductAdminRow>();
    for (const product of products) {
      map.set(product.id, product);
    }
    return map;
  }, [products]);

  const selectedCombo = useMemo(
    () => combos.find((combo) => String(combo.id) === selectedComboId) ?? null,
    [combos, selectedComboId],
  );

  const quickSearchRows = useMemo(() => {
    const term = searchInput.trim().toLowerCase();
    if (term.length <= 0) {
      return [];
    }
    return products
      .filter((product) => {
        const byName = product.name.toLowerCase().includes(term);
        const byBarcode = (product.barcode ?? "").toLowerCase().includes(term);
        return byName || byBarcode;
      })
      .slice(0, 10);
  }, [products, searchInput]);

  function syncFormFromCombo(combo: ComboAdminRow | null) {
    if (!combo) {
      setNameInput("");
      setDiscountInput("5");
      setActiveInput(true);
      setFormItems([]);
      return;
    }
    setNameInput(combo.name);
    setDiscountInput(formatInteger(combo.discountPercent));
    setActiveInput(combo.active);
    setFormItems(
      combo.items.map((item) => ({
        productId: item.productId,
        quantity: parseIntegerInput(String(item.quantity)),
      })),
    );
  }

  async function reloadData(preferComboId?: string) {
    setLoading(true);
    try {
      const [comboRows, productRows] = await Promise.all([
        listCombosAdmin(),
        listProductsAdmin(undefined, undefined, false, 1400),
      ]);
      setCombos(comboRows);
      setProducts(productRows);

      const target =
        comboRows.find((combo) => String(combo.id) === (preferComboId ?? selectedComboId)) ??
        comboRows[0] ??
        null;
      if (target) {
        setSelectedComboId(String(target.id));
        syncFormFromCombo(target);
      } else {
        setSelectedComboId("");
        syncFormFromCombo(null);
      }
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
      setCombos([]);
      setProducts([]);
      setSelectedComboId("");
      syncFormFromCombo(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reloadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    barcodeInputRef.current?.focus();
  }, []);

  function handleNewCombo() {
    setSelectedComboId("");
    syncFormFromCombo(null);
    if (products[0]) {
      setNewItemProductId(String(products[0].id));
    }
    setNewItemQty("1");
    setBarcodeInput("");
    setSearchInput("");
    barcodeInputRef.current?.focus();
  }

  function addItemToCombo(productId: number, quantity: number): boolean {
    if (!Number.isFinite(productId) || productId <= 0) {
      setNotice({ tone: "error", text: "Selecciona un producto para el combo." });
      return false;
    }
    if (quantity <= 0) {
      setNotice({ tone: "error", text: "La cantidad del combo debe ser mayor a cero." });
      return false;
    }
    if (!productMap.has(productId)) {
      setNotice({ tone: "error", text: "Ese producto no esta disponible para combos." });
      return false;
    }

    setFormItems((current) => {
      const index = current.findIndex((item) => item.productId === productId);
      if (index < 0) {
        return [...current, { productId, quantity }];
      }
      const next = [...current];
      next[index] = {
        ...next[index],
        quantity: parseIntegerInput(String(next[index].quantity + quantity)),
      };
      return next;
    });
    return true;
  }

  function handleAddItem() {
    const productId = Number.parseInt(newItemProductId, 10);
    const quantity = parseIntegerInput(newItemQty);
    const added = addItemToCombo(productId, quantity);
    if (!added) {
      return;
    }
    const product = productMap.get(productId);
    setNotice({
      tone: "ok",
      text: `${product?.name ?? "Producto"} agregado al combo.`,
    });
    setNewItemQty("1");
  }

  function handleScanBarcode() {
    const clean = barcodeInput.trim();
    const quantity = parseIntegerInput(newItemQty);
    if (!clean) {
      setNotice({ tone: "error", text: "Escanea un codigo para agregar al combo." });
      barcodeInputRef.current?.focus();
      return;
    }
    const found = products.find((product) => (product.barcode ?? "").trim() === clean);
    if (!found) {
      setNotice({ tone: "error", text: `No existe producto con codigo ${clean}.` });
      barcodeInputRef.current?.focus();
      return;
    }
    const added = addItemToCombo(found.id, quantity);
    if (!added) {
      return;
    }
    setNotice({
      tone: "ok",
      text: `${found.name} agregado desde lector.`,
    });
    setBarcodeInput("");
    setSearchInput(found.name);
    setNewItemProductId(String(found.id));
    setNewItemQty("1");
    barcodeInputRef.current?.focus();
  }

  function handleAddFromSearch(productId: number) {
    const quantity = parseIntegerInput(newItemQty);
    const added = addItemToCombo(productId, quantity);
    if (!added) {
      return;
    }
    const product = productMap.get(productId);
    setNotice({
      tone: "ok",
      text: `${product?.name ?? "Producto"} agregado por busqueda.`,
    });
    setNewItemProductId(String(productId));
    setNewItemQty("1");
    barcodeInputRef.current?.focus();
  }

  function handleScanBarcodeKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    handleScanBarcode();
  }

  function handleSearchInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    const first = quickSearchRows[0];
    if (!first) {
      setNotice({ tone: "info", text: "No hay productos para esa busqueda." });
      return;
    }
    handleAddFromSearch(first.id);
  }

  function handleSaveComboItemQuantity(productId: number, raw: string) {
    const quantity = parseIntegerInput(raw);
    setFormItems((current) =>
      current.map((item) =>
        item.productId === productId ? { ...item, quantity: Math.max(quantity, 1) } : item,
      ),
    );
  }

  function handleRemoveComboItem(productId: number) {
    setFormItems((current) => current.filter((item) => item.productId !== productId));
  }

  async function handleSaveCombo() {
    const cleanName = nameInput.trim();
    const discountPercent = parseIntegerInput(discountInput);
    const payloadItems = toItemsPayload(formItems);
    if (!cleanName) {
      setNotice({ tone: "error", text: "Ingresa un nombre para el combo." });
      return;
    }
    if (discountPercent <= 0 || discountPercent > 100) {
      setNotice({ tone: "error", text: "El descuento debe estar entre 1 y 100." });
      return;
    }
    if (payloadItems.length <= 0) {
      setNotice({ tone: "error", text: "Agrega al menos un producto al combo." });
      return;
    }

    setSaving(true);
    try {
      if (selectedComboId) {
        const updated = await updateCombo({
          id: Number.parseInt(selectedComboId, 10),
          name: cleanName,
          discountPercent,
          active: activeInput,
          items: payloadItems,
        });
        setNotice({ tone: "ok", text: `Combo ${updated.name} actualizado.` });
        await reloadData(String(updated.id));
      } else {
        const created = await createCombo({
          name: cleanName,
          discountPercent,
          active: activeInput,
          items: payloadItems,
        });
        setNotice({ tone: "ok", text: `Combo ${created.name} creado.` });
        await reloadData(String(created.id));
      }
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteCombo() {
    if (!selectedCombo) {
      return;
    }
    const confirmed = window.confirm(`Eliminar combo "${selectedCombo.name}"?`);
    if (!confirmed) {
      return;
    }

    setDeleting(true);
    try {
      await deleteCombo(selectedCombo.id);
      setNotice({ tone: "ok", text: `Combo ${selectedCombo.name} eliminado.` });
      setSelectedComboId("");
      syncFormFromCombo(null);
      await reloadData();
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setDeleting(false);
    }
  }

  return (
    <section className="combos-grid">
      <aside className="panel combos-list-panel">
        <header className="section-head">
          <h2>Combos</h2>
          <p>Combina productos y aplica descuento automatico en venta rapida.</p>
        </header>

        {notice && (
          <div className={`notice-strip notice-${notice.tone}`}>
            <span>{notice.text}</span>
          </div>
        )}

        <div className="combos-actions-row">
          <button type="button" className="button-soft" onClick={handleNewCombo}>
            Nuevo combo
          </button>
          <button type="button" onClick={() => void reloadData()} disabled={loading}>
            {loading ? "Actualizando..." : "Refrescar"}
          </button>
        </div>

        <div className="combos-list">
          {combos.length <= 0 ? (
            <p className="empty-copy">No hay combos configurados.</p>
          ) : (
            combos.map((combo) => (
              <button
                key={combo.id}
                type="button"
                className={`combo-row ${String(combo.id) === selectedComboId ? "active" : ""}`}
                onClick={() => {
                  setSelectedComboId(String(combo.id));
                  syncFormFromCombo(combo);
                }}
              >
                <span className="row-main">
                  <strong>{combo.name}</strong>
                  <small>{formatInteger(combo.discountPercent)}%</small>
                </span>
                <span className={`row-badge ${combo.active ? "" : "alert"}`}>
                  {combo.active ? "Activo" : "Inactivo"} | {combo.items.length} item(s)
                </span>
              </button>
            ))
          )}
        </div>
      </aside>

      <section className="panel combos-editor-panel">
        <header className="section-head">
          <h2>{selectedCombo ? "Editar combo" : "Crear combo"}</h2>
          <p>Al detectar todos los productos del combo en carrito, se aplica descuento.</p>
        </header>

        <div className="combos-form">
          <label className="field">
            <span>Nombre combo</span>
            <input value={nameInput} onChange={(event) => setNameInput(event.target.value)} />
          </label>

          <div className="split-grid">
            <label className="field">
              <span>Descuento %</span>
              <input
                type="number"
                min={1}
                max={100}
                step="1"
                value={discountInput}
                onChange={(event) => setDiscountInput(event.target.value)}
              />
            </label>

            <label className="switch-row combos-active-switch">
              <input
                type="checkbox"
                checked={activeInput}
                onChange={(event) => setActiveInput(event.target.checked)}
              />
              <span>Combo activo</span>
            </label>
          </div>

          <div className="combos-add-item">
            <label className="field combos-scan-field">
              <span>Escanear codigo (lector)</span>
              <input
                ref={barcodeInputRef}
                value={barcodeInput}
                onChange={(event) => setBarcodeInput(event.target.value)}
                onKeyDown={handleScanBarcodeKeyDown}
                placeholder="Escanear y Enter"
                autoComplete="off"
              />
            </label>

            <label className="field combos-search-field">
              <span>Buscar por nombre</span>
              <input
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                onKeyDown={handleSearchInputKeyDown}
                placeholder="Nombre de producto"
                autoComplete="off"
              />
            </label>

            <label className="field">
              <span>Producto</span>
              <div className="select-wrap">
                <select
                  value={newItemProductId}
                  onChange={(event) => setNewItemProductId(event.target.value)}
                >
                  <option value="">Seleccionar</option>
                  {products.map((product) => (
                    <option key={product.id} value={product.id}>
                      {product.name}
                    </option>
                  ))}
                </select>
              </div>
            </label>

            <label className="field">
              <span>Cantidad</span>
              <input
                type="number"
                min={1}
                step="1"
                value={newItemQty}
                onChange={(event) => setNewItemQty(event.target.value)}
              />
            </label>

            <button type="button" className="button-soft" onClick={handleScanBarcode}>
              Agregar por lector
            </button>

            <button
              type="button"
              className="button-soft"
              onClick={() => {
                const first = quickSearchRows[0];
                if (!first) {
                  setNotice({ tone: "info", text: "No hay productos para esa busqueda." });
                  return;
                }
                handleAddFromSearch(first.id);
              }}
            >
              Agregar 1ro busqueda
            </button>

            <button type="button" onClick={handleAddItem}>
              Agregar manual
            </button>
          </div>

          {quickSearchRows.length > 0 && (
            <div className="combos-search-results">
              {quickSearchRows.map((product) => (
                <button
                  key={`search-${product.id}`}
                  type="button"
                  className="button-soft button-xs"
                  onClick={() => handleAddFromSearch(product.id)}
                >
                  {product.name}
                </button>
              ))}
            </div>
          )}

          <div className="table-shell combos-table-shell">
            <table>
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Cantidad</th>
                  <th>Precio</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {formItems.length <= 0 ? (
                  <tr>
                    <td colSpan={4} className="table-empty">
                      Agrega productos para armar el combo.
                    </td>
                  </tr>
                ) : (
                  formItems.map((item) => {
                    const product = productMap.get(item.productId);
                    return (
                      <tr key={item.productId}>
                        <td>{product?.name ?? `Producto #${item.productId}`}</td>
                        <td>
                          <input
                            type="number"
                            min={1}
                            step="1"
                            value={formatInteger(item.quantity)}
                            onChange={(event) =>
                              handleSaveComboItemQuantity(item.productId, event.target.value)
                            }
                          />
                        </td>
                        <td>{product ? formatMoney(product.salePrice) : "-"}</td>
                        <td>
                          <button
                            type="button"
                            className="button-soft button-xs"
                            onClick={() => handleRemoveComboItem(item.productId)}
                          >
                            Quitar
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          <div className="combos-editor-actions">
            <button type="button" onClick={handleSaveCombo} disabled={saving}>
              {saving ? "Guardando..." : selectedCombo ? "Actualizar combo" : "Crear combo"}
            </button>
            <button
              type="button"
              className="button-soft"
              onClick={handleDeleteCombo}
              disabled={!selectedCombo || deleting}
            >
              {deleting ? "Eliminando..." : "Eliminar"}
            </button>
          </div>
        </div>
      </section>
    </section>
  );
}
