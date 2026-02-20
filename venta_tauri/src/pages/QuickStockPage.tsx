import { KeyboardEvent, useEffect, useRef, useState } from "react";

import { Icon } from "../components/Icon";
import {
  createProduct,
  listCategories,
  listRecentStockMovements,
  quickStockLookupByBarcode,
  quickStockAddByBarcode,
  reverseSale,
  reverseStockMovement,
} from "../tauri";
import { CategorySummary, QuickStockLookupProduct, StockMovementSummary } from "../types";
import { formatInteger, parseIntegerInput, roundInteger } from "../utils/number";

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
  autoPrice: true,
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

function canRevertMovement(row: StockMovementSummary): boolean {
  const referenceType = row.referenceType ?? "";
  if ((referenceType === "sale" || referenceType === "internal_consumption") && (row.referenceId ?? 0) > 0) {
    return true;
  }
  return row.movementType === "manual_in" || row.movementType === "manual_out" || row.movementType === "adjustment";
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
  const [reversingMovementId, setReversingMovementId] = useState<number | null>(null);
  const [createFormOpen, setCreateFormOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateFormState>(EMPTY_CREATE_FORM);
  const [confirmPopupOpen, setConfirmPopupOpen] = useState(false);
  const [confirmProduct, setConfirmProduct] = useState<QuickStockLookupProduct | null>(null);
  const [confirmQuantityInput, setConfirmQuantityInput] = useState("1");
  const [confirmCostInput, setConfirmCostInput] = useState("0");
  const [confirmingAdd, setConfirmingAdd] = useState(false);
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
      const lookup = await quickStockLookupByBarcode(cleanBarcode);

      if (!lookup.found || !lookup.product) {
        setCreateForm({
          ...EMPTY_CREATE_FORM,
          barcode: cleanBarcode,
          stock: formatInteger(quantity),
          categoryId: categories[0] ? String(categories[0].id) : "",
        });
        setCreateFormOpen(true);
        setNotice({ tone: "info", text: lookup.message });
        return;
      }

      const defaultCost = Math.max(roundInteger(lookup.product.cost), 0);
      setConfirmProduct(lookup.product);
      setConfirmQuantityInput(formatInteger(quantity));
      setConfirmCostInput(formatInteger(defaultCost > 0 ? defaultCost : 1));
      setConfirmPopupOpen(true);
      setNotice({
        tone: "info",
        text: `Producto ${lookup.product.name} encontrado. Confirma cantidad y costo para sumar stock.`,
      });
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setAddingStock(false);
    }
  }

  function closeConfirmPopup() {
    setConfirmPopupOpen(false);
    setConfirmProduct(null);
    setConfirmQuantityInput("1");
    setConfirmCostInput("0");
    barcodeInputRef.current?.focus();
  }

  async function handleConfirmPopupAddStock() {
    if (!confirmProduct) {
      setNotice({ tone: "error", text: "No hay producto seleccionado para confirmar stock." });
      return;
    }
    const quantity = parseDecimal(confirmQuantityInput);
    const unitCost = parseDecimal(confirmCostInput);
    if (quantity <= 0) {
      setNotice({ tone: "error", text: "La cantidad debe ser mayor a cero." });
      return;
    }
    if (unitCost <= 0) {
      setNotice({ tone: "error", text: "El precio de stock debe ser mayor a cero." });
      return;
    }

    setConfirmingAdd(true);
    try {
      const response = await quickStockAddByBarcode({
        barcode: confirmProduct.barcode ?? barcodeInput.trim(),
        quantity,
        unitCost,
        note: noteInput.trim() || undefined,
      });

      if (!response.found) {
        setNotice({ tone: "error", text: "El producto ya no existe. Recarga y vuelve a intentar." });
        return;
      }

      setNotice({
        tone: "ok",
        text: `${response.product?.name ?? "Producto"} actualizado correctamente.`,
      });
      setBarcodeInput("");
      setQuantityInput("1");
      setNoteInput("");
      closeConfirmPopup();
      await refreshMovements();
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setConfirmingAdd(false);
    }
  }

  function handleConfirmPopupKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    void handleConfirmPopupAddStock();
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
    if (cost <= 0) {
      setNotice({ tone: "error", text: "El costo inicial debe ser mayor a cero." });
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

  async function handleReverseMovement(movement: StockMovementSummary) {
    if (!canRevertMovement(movement)) {
      setNotice({
        tone: "info",
        text: "Ese movimiento no se revierte desde stock rapido.",
      });
      return;
    }

    const fromSale =
      (movement.referenceType === "sale" || movement.referenceType === "internal_consumption") &&
      (movement.referenceId ?? 0) > 0;
    const confirmed = window.confirm(fromSale
      ? `Revertir venta #${movement.referenceId}? Se restaura stock y se eliminan pagos/deuda de esa venta.`
      : `Revertir movimiento #${movement.id} de ${movement.productName}? Esta accion crea un movimiento inverso auditado.`,
    );
    if (!confirmed) {
      return;
    }

    setReversingMovementId(movement.id);
    try {
      if (fromSale && movement.referenceId) {
        const result = await reverseSale({
          saleId: movement.referenceId,
          reason: "Reversion desde movimientos de stock rapido",
        });
        setNotice({
          tone: "ok",
          text: `Venta #${result.saleId} revertida. Unidades restauradas: ${formatInteger(result.restoredUnits)}.`,
        });
        await refreshMovements();
      } else {
        const result = await reverseStockMovement({
          movementId: movement.id,
          reason: "Reversion manual desde stock rapido",
        });
        setNotice({
          tone: "ok",
          text: `Movimiento #${result.movementId} revertido. Stock actual de ${result.product.name}: ${formatInteger(result.product.stock)}.`,
        });
        await refreshMovements();
      }
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setReversingMovementId(null);
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
          <p>Escanea, confirma cantidad y costo, y guarda en segundos.</p>
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

      {confirmPopupOpen && confirmProduct && (
        <div className="quick-stock-modal-backdrop">
          <div className="quick-stock-modal" role="dialog" aria-modal="true" aria-label="Confirmar ingreso de stock">
            <header className="quick-stock-modal-header">
              <h3>Confirmar ingreso de stock</h3>
              <small>{confirmProduct.name}</small>
            </header>
            <div className="quick-stock-modal-grid">
              <label className="field">
                <span>Cantidad a agregar</span>
                <input
                  type="number"
                  min={1}
                  step="1"
                  value={confirmQuantityInput}
                  onChange={(event) => setConfirmQuantityInput(event.target.value)}
                  onKeyDown={handleConfirmPopupKeyDown}
                />
              </label>
              <label className="field">
                <span>Precio de stock (costo)</span>
                <input
                  type="number"
                  min={1}
                  step="1"
                  value={confirmCostInput}
                  onChange={(event) => setConfirmCostInput(event.target.value)}
                  onKeyDown={handleConfirmPopupKeyDown}
                />
              </label>
            </div>
            <div className="quick-stock-modal-actions">
              <button
                type="button"
                className="button-soft"
                onClick={closeConfirmPopup}
                disabled={confirmingAdd}
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => void handleConfirmPopupAddStock()}
                disabled={confirmingAdd}
              >
                {confirmingAdd ? "Guardando..." : "Confirmar y agregar"}
              </button>
            </div>
          </div>
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
            disabled={confirmPopupOpen}
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
            disabled={confirmPopupOpen}
          />
        </label>

        <button
          type="button"
          className="quick-stock-submit"
          onClick={handleAddStock}
          disabled={addingStock || loadingBoot || confirmPopupOpen}
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
            disabled={confirmPopupOpen}
          />
        </label>

        <button
          type="button"
          className="button-soft quick-stock-toggle-create"
          onClick={() => setCreateFormOpen((prev) => !prev)}
          disabled={confirmPopupOpen}
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
                <th>Accion</th>
              </tr>
            </thead>
            <tbody>
              {movements.length <= 0 ? (
                <tr>
                  <td colSpan={7} className="table-empty">
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
                    <td>
                      <button
                        type="button"
                        className="button-soft button-xs"
                        onClick={() => void handleReverseMovement(movement)}
                        disabled={
                          !canRevertMovement(movement) ||
                          reversingMovementId === movement.id
                        }
                      >
                        {reversingMovementId === movement.id ? "Revirtiendo..." : "Revertir"}
                      </button>
                    </td>
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
