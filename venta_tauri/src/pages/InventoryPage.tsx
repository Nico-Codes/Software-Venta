import { useEffect, useMemo, useState } from "react";

import {
  inventoryListMovements,
  listProductsAdmin,
  registerInventoryMovement,
  reverseSale,
  reverseStockMovement,
} from "../tauri";
import { InventoryMovementRow, ProductAdminRow } from "../types";
import { formatInteger, parseIntegerInput } from "../utils/number";

type MovementTypeFilter = "todos" | "manual_in" | "manual_out" | "adjustment" | "sale";
type MovementTypeForm = "manual_in" | "manual_out" | "adjustment";

type Notice = {
  tone: "ok" | "error" | "info";
  text: string;
};

const movementTypeLabel: Record<string, string> = {
  manual_in: "Entrada",
  manual_out: "Salida",
  adjustment: "Ajuste",
  sale: "Venta",
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

function formatDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(parsed);
}

function canRevertMovement(row: InventoryMovementRow): boolean {
  const referenceType = row.referenceType ?? "";
  if ((referenceType === "sale" || referenceType === "internal_consumption") && (row.referenceId ?? 0) > 0) {
    return true;
  }
  return row.movementType === "manual_in" || row.movementType === "manual_out" || row.movementType === "adjustment";
}

export function InventoryPage() {
  const [products, setProducts] = useState<ProductAdminRow[]>([]);
  const [movements, setMovements] = useState<InventoryMovementRow[]>([]);
  const [selectedProductId, setSelectedProductId] = useState("");
  const [movementType, setMovementType] = useState<MovementTypeForm>("manual_in");
  const [quantityInput, setQuantityInput] = useState("1");
  const [targetStockInput, setTargetStockInput] = useState("");
  const [noteInput, setNoteInput] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [movementFilter, setMovementFilter] = useState<MovementTypeFilter>("todos");
  const [loadingBoot, setLoadingBoot] = useState(true);
  const [loadingMovements, setLoadingMovements] = useState(false);
  const [saving, setSaving] = useState(false);
  const [revertingMovementId, setRevertingMovementId] = useState<number | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);

  async function reloadProducts(preferProductId?: string) {
    const rows = await listProductsAdmin(undefined, undefined, true, 800);
    setProducts(rows);
    if (rows.length <= 0) {
      setSelectedProductId("");
      return;
    }

    const target =
      rows.find((row) => String(row.id) === (preferProductId ?? selectedProductId)) ?? rows[0];
    setSelectedProductId(String(target.id));
  }

  async function reloadMovements() {
    setLoadingMovements(true);
    try {
      const rows = await inventoryListMovements(
        searchInput.trim() || undefined,
        movementFilter === "todos" ? undefined : movementFilter,
        500,
      );
      setMovements(rows);
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
      setMovements([]);
    } finally {
      setLoadingMovements(false);
    }
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        await Promise.all([reloadProducts(), reloadMovements()]);
      } catch (error) {
        if (!mounted) {
          return;
        }
        setNotice({ tone: "error", text: toErrorMessage(error) });
      } finally {
        if (mounted) {
          setLoadingBoot(false);
        }
      }
    })();

    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedProduct =
    products.find((product) => String(product.id) === selectedProductId) ?? null;

  const lowStockProducts = useMemo(
    () =>
      products
        .filter((product) => product.active && product.stock <= product.minStock)
        .sort((a, b) => b.minStock - b.stock - (a.minStock - a.stock))
        .slice(0, 18),
    [products],
  );

  async function handleApplyMovement() {
    const productId = Number.parseInt(selectedProductId, 10);
    if (!Number.isFinite(productId)) {
      setNotice({ tone: "error", text: "Selecciona un producto." });
      return;
    }

    const quantity = parseDecimal(quantityInput);
    const targetStock = parseDecimal(targetStockInput);

    if (movementType === "adjustment") {
      if (targetStock < 0) {
        setNotice({ tone: "error", text: "El stock objetivo no puede ser negativo." });
        return;
      }
    } else {
      if (quantity <= 0) {
        setNotice({ tone: "error", text: "La cantidad debe ser mayor a cero." });
        return;
      }
    }

    setSaving(true);
    try {
      const result = await registerInventoryMovement({
        productId,
        movementType,
        quantity: movementType === "adjustment" ? undefined : quantity,
        stockTarget: movementType === "adjustment" ? targetStock : undefined,
        note: noteInput.trim() || undefined,
      });
      setNotice({ tone: "ok", text: result.message });
      setNoteInput("");
      setQuantityInput("1");
      setTargetStockInput(formatInteger(result.product.stock));
      await Promise.all([reloadProducts(String(result.product.id)), reloadMovements()]);
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setSaving(false);
    }
  }

  async function handleRevertMovement(movement: InventoryMovementRow) {
    if (!canRevertMovement(movement)) {
      setNotice({ tone: "info", text: "Ese movimiento no se puede revertir desde inventario." });
      return;
    }

    const fromSale =
      (movement.referenceType === "sale" || movement.referenceType === "internal_consumption") &&
      (movement.referenceId ?? 0) > 0;
    const confirmed = window.confirm(fromSale
      ? `Revertir venta #${movement.referenceId}? Se restaura stock y se eliminan pagos/deuda de esa venta.`
      : `Revertir movimiento #${movement.id} de ${movement.productName}? Se registrara un movimiento inverso.`,
    );
    if (!confirmed) {
      return;
    }

    setRevertingMovementId(movement.id);
    try {
      if (fromSale && movement.referenceId) {
        const result = await reverseSale({
          saleId: movement.referenceId,
          reason: "Reversion desde movimientos de inventario",
        });
        setNotice({
          tone: "ok",
          text: `Venta #${result.saleId} revertida. Unidades restauradas: ${formatInteger(result.restoredUnits)}.`,
        });
        await Promise.all([reloadProducts(), reloadMovements()]);
      } else {
        const result = await reverseStockMovement({
          movementId: movement.id,
          reason: "Reversion manual desde inventario",
        });
        setNotice({
          tone: "ok",
          text: `Movimiento #${result.movementId} revertido. Stock actual de ${result.product.name}: ${formatInteger(result.product.stock)}.`,
        });
        await Promise.all([reloadProducts(String(result.product.id)), reloadMovements()]);
      }
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setRevertingMovementId(null);
    }
  }

  return (
    <section className="inventory-grid">
      <aside className="panel inventory-actions-panel">
        <header className="section-head">
          <h2>Inventario</h2>
          <p>Entradas, salidas y ajustes con trazabilidad completa.</p>
        </header>

        {notice && (
          <div className={`notice-strip notice-${notice.tone}`}>
            <span>{notice.text}</span>
          </div>
        )}

        <div className="inventory-form">
          <label className="field">
            <span>Producto</span>
            <div className="select-wrap">
              <select
                value={selectedProductId}
                onChange={(event) => {
                  setSelectedProductId(event.target.value);
                  const product =
                    products.find((row) => String(row.id) === event.target.value) ?? null;
                  if (product) {
                    setTargetStockInput(formatInteger(product.stock));
                  }
                }}
              >
                <option value="">Seleccionar</option>
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name} | Stock {formatInteger(product.stock)}
                  </option>
                ))}
              </select>
            </div>
          </label>

          <label className="field">
            <span>Tipo de movimiento</span>
            <div className="select-wrap">
              <select
                value={movementType}
                onChange={(event) => setMovementType(event.target.value as MovementTypeForm)}
              >
                <option value="manual_in">Entrada</option>
                <option value="manual_out">Salida</option>
                <option value="adjustment">Ajuste</option>
              </select>
            </div>
          </label>

          {movementType === "adjustment" ? (
            <label className="field">
              <span>Stock objetivo</span>
              <input
                type="number"
                min={0}
                step="1"
                value={targetStockInput}
                onChange={(event) => setTargetStockInput(event.target.value)}
                placeholder="Ej: 24"
              />
            </label>
          ) : (
            <label className="field">
              <span>Cantidad</span>
              <input
                type="number"
                min={0}
                step="1"
                value={quantityInput}
                onChange={(event) => setQuantityInput(event.target.value)}
                placeholder="Ej: 6"
              />
            </label>
          )}

          <label className="field">
            <span>Nota</span>
            <input
              value={noteInput}
              onChange={(event) => setNoteInput(event.target.value)}
              placeholder="Compra, ajuste por conteo, rotura..."
            />
          </label>

          <button type="button" onClick={handleApplyMovement} disabled={saving || loadingBoot}>
            {saving ? "Aplicando..." : "Registrar movimiento"}
          </button>
        </div>

        {selectedProduct && (
          <div className="inventory-product-card">
            <span>Producto seleccionado</span>
            <strong>{selectedProduct.name}</strong>
            <small>
              Stock: {formatInteger(selectedProduct.stock)} | Minimo:{" "}
              {formatInteger(selectedProduct.minStock)}
            </small>
          </div>
        )}
      </aside>

      <section className="panel inventory-table-panel">
        <div className="inventory-table-toolbar">
          <label className="field">
            <span>Buscar movimiento</span>
            <input
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder="Producto o codigo"
            />
          </label>
          <label className="field">
            <span>Filtrar tipo</span>
            <div className="select-wrap">
              <select
                value={movementFilter}
                onChange={(event) => setMovementFilter(event.target.value as MovementTypeFilter)}
              >
                <option value="todos">Todos</option>
                <option value="manual_in">Entrada</option>
                <option value="manual_out">Salida</option>
                <option value="adjustment">Ajuste</option>
                <option value="sale">Venta</option>
              </select>
            </div>
          </label>
          <button type="button" onClick={() => void reloadMovements()} disabled={loadingMovements}>
            {loadingMovements ? "Actualizando..." : "Filtrar"}
          </button>
        </div>

        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Producto</th>
                <th>Tipo</th>
                <th>Cant.</th>
                <th>Antes</th>
                <th>Despues</th>
                <th>Nota</th>
                <th>Accion</th>
              </tr>
            </thead>
            <tbody>
              {movements.length <= 0 ? (
                <tr>
                  <td colSpan={8} className="table-empty">
                    Sin movimientos para este filtro.
                  </td>
                </tr>
              ) : (
                movements.map((movement) => (
                  <tr key={movement.id}>
                    <td>{formatDateTime(movement.createdAt)}</td>
                    <td>{movement.productName}</td>
                    <td>{movementTypeLabel[movement.movementType] ?? movement.movementType}</td>
                    <td>{formatInteger(movement.quantity)}</td>
                    <td>{formatInteger(movement.stockBefore)}</td>
                    <td>{formatInteger(movement.stockAfter)}</td>
                    <td>{movement.note || "-"}</td>
                    <td>
                      <button
                        type="button"
                        className="button-soft button-xs"
                        onClick={() => void handleRevertMovement(movement)}
                        disabled={
                          !canRevertMovement(movement) ||
                          revertingMovementId === movement.id
                        }
                      >
                        {revertingMovementId === movement.id ? "Revirtiendo..." : "Revertir"}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <section className="inventory-alerts">
          <h3>Stock bajo</h3>
          {lowStockProducts.length <= 0 ? (
            <p className="empty-copy">Sin alertas de stock bajo.</p>
          ) : (
            <div className="inventory-alert-list">
              {lowStockProducts.map((product) => (
                <article key={product.id}>
                  <strong>{product.name}</strong>
                  <small>
                    Stock {formatInteger(product.stock)} / Minimo {formatInteger(product.minStock)}
                  </small>
                </article>
              ))}
            </div>
          )}
        </section>
      </section>
    </section>
  );
}
