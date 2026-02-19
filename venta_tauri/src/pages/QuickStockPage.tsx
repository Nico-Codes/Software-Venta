import { KeyboardEvent, useEffect, useRef, useState } from "react";

import { Icon } from "../components/Icon";
import {
  createProduct,
  listCategories,
  listRecentStockMovements,
  quickStockAddByBarcode,
} from "../tauri";
import { CategorySummary, StockMovementSummary } from "../types";
import { formatInteger, parseIntegerInput } from "../utils/number";

type Notice = {
  tone: "ok" | "error" | "info";
  text: string;
};

type CreateFormState = {
  name: string;
  barcode: string;
  categoryId: string;
  cost: string;
  salePrice: string;
  stock: string;
  minStock: string;
  autoPrice: boolean;
};

const EMPTY_CREATE_FORM: CreateFormState = {
  name: "",
  barcode: "",
  categoryId: "",
  cost: "0",
  salePrice: "0",
  stock: "1",
  minStock: "0",
  autoPrice: false,
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

function parseDecimal(raw: string): number {
  return parseIntegerInput(raw);
}

function formatMovementDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(parsed);
}

function movementLabel(type: string): string {
  if (type === "manual_in") {
    return "Entrada";
  }
  if (type === "manual_out") {
    return "Salida";
  }
  if (type === "sale") {
    return "Venta";
  }
  return type;
}

export function QuickStockPage() {
  const barcodeInputRef = useRef<HTMLInputElement | null>(null);

  const [barcodeInput, setBarcodeInput] = useState("");
  const [quantityInput, setQuantityInput] = useState("1");
  const [noteInput, setNoteInput] = useState("");
  const [loadingBoot, setLoadingBoot] = useState(true);
  const [loadingMovement, setLoadingMovement] = useState(false);
  const [addingStock, setAddingStock] = useState(false);
  const [creatingProduct, setCreatingProduct] = useState(false);
  const [createFormOpen, setCreateFormOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateFormState>(EMPTY_CREATE_FORM);
  const [movements, setMovements] = useState<StockMovementSummary[]>([]);
  const [categories, setCategories] = useState<CategorySummary[]>([]);
  const [notice, setNotice] = useState<Notice | null>(null);

  async function refreshMovements() {
    setLoadingMovement(true);
    try {
      const rows = await listRecentStockMovements(40);
      setMovements(rows);
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setLoadingMovement(false);
    }
  }

  async function refreshCategories() {
    const rows = await listCategories();
    setCategories(rows);
  }

  useEffect(() => {
    barcodeInputRef.current?.focus();
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [categoryRows, movementRows] = await Promise.all([
          listCategories(),
          listRecentStockMovements(40),
        ]);
        if (!active) {
          return;
        }
        setCategories(categoryRows);
        setMovements(movementRows);
      } catch (error) {
        if (!active) {
          return;
        }
        setNotice({ tone: "error", text: toErrorMessage(error) });
      } finally {
        if (active) {
          setLoadingBoot(false);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  async function handleAddStock() {
    const cleanBarcode = barcodeInput.trim();
    if (!cleanBarcode) {
      setNotice({ tone: "error", text: "Escanea o ingresa un codigo de barras." });
      barcodeInputRef.current?.focus();
      return;
    }
    const quantity = parseDecimal(quantityInput);
    if (quantity <= 0) {
      setNotice({ tone: "error", text: "La cantidad debe ser mayor a cero." });
      return;
    }

    setAddingStock(true);
    try {
      const response = await quickStockAddByBarcode({
        barcode: cleanBarcode,
        quantity,
        note: noteInput.trim() || undefined,
      });

      if (!response.found) {
        setCreateForm({
          ...EMPTY_CREATE_FORM,
          barcode: cleanBarcode,
          stock: formatInteger(quantity),
          categoryId: categories[0] ? String(categories[0].id) : "",
        });
        setCreateFormOpen(true);
        setNotice({ tone: "info", text: response.message });
        return;
      }

      setNotice({
        tone: "ok",
        text: `${response.product?.name ?? "Producto"} actualizado correctamente.`,
      });
      setBarcodeInput("");
      setQuantityInput("1");
      setNoteInput("");
      await refreshMovements();
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setAddingStock(false);
      barcodeInputRef.current?.focus();
    }
  }

  async function handleCreateProduct() {
    const cleanName = createForm.name.trim();
    const cleanBarcode = createForm.barcode.trim();
    const categoryId = Number.parseInt(createForm.categoryId, 10);
    const cost = parseDecimal(createForm.cost);
    const salePrice = parseDecimal(createForm.salePrice);
    const stock = parseDecimal(createForm.stock);
    const minStock = parseDecimal(createForm.minStock);
    if (!cleanName) {
      setNotice({ tone: "error", text: "Ingresa nombre para el producto nuevo." });
      return;
    }
    if (!cleanBarcode) {
      setNotice({ tone: "error", text: "El codigo de barras es obligatorio." });
      return;
    }
    if (!Number.isFinite(categoryId)) {
      setNotice({ tone: "error", text: "Selecciona categoria para el producto." });
      return;
    }
    if (cost < 0) {
      setNotice({ tone: "error", text: "El costo no puede ser negativo." });
      return;
    }
    if (!createForm.autoPrice && salePrice <= 0) {
      setNotice({ tone: "error", text: "El precio de venta debe ser mayor a cero." });
      return;
    }
    if (stock <= 0) {
      setNotice({ tone: "error", text: "El stock inicial debe ser mayor a cero." });
      return;
    }
    if (minStock < 0) {
      setNotice({ tone: "error", text: "El stock minimo no puede ser negativo." });
      return;
    }

    setCreatingProduct(true);
    try {
      const created = await createProduct({
        name: cleanName,
        barcode: cleanBarcode,
        categoryId,
        cost,
        salePrice,
        stock,
        minStock,
        autoPrice: createForm.autoPrice,
      });
      setNotice({
        tone: "ok",
        text: `Producto ${created.name} creado. Ya puedes seguir cargando stock.`,
      });
      setCreateFormOpen(false);
      setCreateForm(EMPTY_CREATE_FORM);
      setBarcodeInput(created.barcode ?? "");
      setQuantityInput("1");
      await refreshMovements();
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setCreatingProduct(false);
      barcodeInputRef.current?.focus();
    }
  }

  function handleBarcodeKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    void handleAddStock();
  }

  function handleFastInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    void handleAddStock();
  }

  return (
    <section className="panel quick-stock-panel">
      <header className="panel-header-row">
        <div>
          <h2>Agregar stock rapido</h2>
          <p>Escanea, confirma cantidad y guarda en segundos.</p>
        </div>
        <div className="quick-stock-header-tools">
          <span className="chip chip-secondary">
            <Icon name="stock" size={16} />
            Reposicion
          </span>
          <button
            type="button"
            className="button-soft button-xs"
            onClick={() => void refreshMovements()}
            disabled={loadingBoot || loadingMovement}
          >
            {loadingMovement ? "Actualizando..." : "Actualizar"}
          </button>
        </div>
      </header>

      {notice && (
        <div className={`notice-strip notice-${notice.tone}`}>
          <span>{notice.text}</span>
        </div>
      )}

      <div className="quick-stock-fastbar">
        <label className="field field-scan quick-stock-barcode">
          <span>Codigo de barras</span>
          <input
            ref={barcodeInputRef}
            value={barcodeInput}
            onChange={(event) => setBarcodeInput(event.target.value)}
            onKeyDown={handleBarcodeKeyDown}
            placeholder="Escanear producto"
            autoComplete="off"
          />
        </label>

        <label className="field field-qty quick-stock-quantity">
          <span>Cantidad</span>
          <input
            type="number"
            min={1}
            step="1"
            value={quantityInput}
            onChange={(event) => setQuantityInput(event.target.value)}
            onKeyDown={handleFastInputKeyDown}
          />
        </label>

        <button
          type="button"
          className="quick-stock-submit"
          onClick={handleAddStock}
          disabled={addingStock || loadingBoot}
        >
          {addingStock ? "Guardando..." : "Agregar stock"}
        </button>
      </div>

      <div className="quick-stock-meta">
        <label className="field quick-stock-note">
          <span>Nota opcional</span>
          <input
            value={noteInput}
            onChange={(event) => setNoteInput(event.target.value)}
            onKeyDown={handleFastInputKeyDown}
            placeholder="Compra, ajuste, etc."
          />
        </label>

        <button
          type="button"
          className="button-soft quick-stock-toggle-create"
          onClick={() => setCreateFormOpen((prev) => !prev)}
        >
          {createFormOpen ? "Ocultar alta completa" : "Alta completa"}
        </button>
      </div>

      {createFormOpen && (
        <section className="quick-stock-create">
          <header className="quick-stock-create-header">
            <h3>Alta completa de producto</h3>
            <p>Usa este bloque solo cuando el codigo no existe.</p>
          </header>

          <div className="quick-stock-create-grid">
            <label className="field create-col-2">
              <span>Nombre</span>
              <input
                value={createForm.name}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, name: event.target.value }))}
                placeholder="Nombre del producto"
              />
            </label>

            <label className="field">
              <span>Codigo de barras</span>
              <input
                value={createForm.barcode}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, barcode: event.target.value }))}
              />
            </label>

            <label className="field">
              <span>Categoria</span>
              <div className="select-wrap">
                <select
                  value={createForm.categoryId}
                  onChange={(event) => setCreateForm((prev) => ({ ...prev, categoryId: event.target.value }))}
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

            <label className="field">
              <span>Costo</span>
              <input
                type="number"
                min={0}
                step="1"
                value={createForm.cost}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, cost: event.target.value }))}
              />
            </label>

            <label className="field">
              <span>Precio venta</span>
              <input
                type="number"
                min={0}
                step="1"
                value={createForm.salePrice}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, salePrice: event.target.value }))}
              />
            </label>

            <label className="field">
              <span>Stock inicial</span>
              <input
                type="number"
                min={1}
                step="1"
                value={createForm.stock}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, stock: event.target.value }))}
              />
            </label>

            <label className="field">
              <span>Stock minimo</span>
              <input
                type="number"
                min={0}
                step="1"
                value={createForm.minStock}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, minStock: event.target.value }))}
              />
            </label>
          </div>

          <label className="switch-row quick-stock-create-switch">
            <input
              type="checkbox"
              checked={createForm.autoPrice}
              onChange={(event) => setCreateForm((prev) => ({ ...prev, autoPrice: event.target.checked }))}
            />
            <span>Calcular precio automatico por margen</span>
          </label>

          {categories.length <= 0 && (
            <div className="notice-strip notice-info">
              <span>Necesitas al menos una categoria para crear productos.</span>
            </div>
          )}

          <div className="action-row quick-stock-create-actions">
            <button
              type="button"
              className="button-soft"
              onClick={() => setCreateFormOpen(false)}
              disabled={creatingProduct}
            >
              Cancelar
            </button>
            <button type="button" onClick={handleCreateProduct} disabled={creatingProduct || categories.length <= 0}>
              {creatingProduct ? "Creando..." : "Crear producto"}
            </button>
          </div>
        </section>
      )}

      <section className="quick-stock-movements">
        <div className="quick-stock-movements-header">
          <h3>Movimientos recientes</h3>
          <span>{movements.length} registro(s)</span>
        </div>

        <div className="table-shell quick-stock-table-shell">
          <table>
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Producto</th>
                <th>Tipo</th>
                <th>Cantidad</th>
                <th>Antes</th>
                <th>Despues</th>
              </tr>
            </thead>
            <tbody>
              {movements.length <= 0 ? (
                <tr>
                  <td colSpan={6} className="table-empty">
                    {loadingMovement ? "Cargando movimientos..." : "Sin movimientos recientes."}
                  </td>
                </tr>
              ) : (
                movements.map((movement) => (
                  <tr key={movement.id}>
                    <td>{formatMovementDate(movement.createdAt)}</td>
                    <td>{movement.productName}</td>
                    <td>{movementLabel(movement.movementType)}</td>
                    <td>{formatInteger(movement.quantity)}</td>
                    <td>{formatInteger(movement.stockBefore)}</td>
                    <td>{formatInteger(movement.stockAfter)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}
