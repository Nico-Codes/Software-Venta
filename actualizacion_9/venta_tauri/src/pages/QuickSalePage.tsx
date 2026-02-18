import { KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Icon } from "../components/Icon";
import {
  createSale,
  generateSaleTicket,
  getProductByBarcode,
  listCustomers,
  listFavoriteProducts,
  listPaymentMethods,
  searchProducts,
  setProductFavorite,
} from "../tauri";
import {
  CustomerSummary,
  FavoriteProductRow,
  PaymentMethod,
  ProductSummary,
  SaleTicketResponse,
} from "../types";

type CartItem = ProductSummary & {
  qty: number;
};

type QuickPickItem = ProductSummary & {
  favorite: boolean;
  source: "favorites" | "search";
};

type Notice = {
  tone: "ok" | "error" | "info";
  text: string;
};

const FALLBACK_METHODS: PaymentMethod[] = [
  "Efectivo",
  "Credito",
  "Debito",
  "Transferencia",
  "Deuda",
];

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

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function normalizeNumberInput(raw: string): number {
  const parsed = Number.parseFloat(raw.replace(",", "."));
  if (!Number.isFinite(parsed)) {
    return 0;
  }
  return parsed;
}

function defaultDueDateInput(): string {
  const now = new Date();
  now.setDate(now.getDate() + 30);
  return now.toISOString().slice(0, 10);
}

function resolvePaidAmount(
  partialEnabled: boolean,
  partialRaw: string,
  paymentMethod: PaymentMethod,
  total: number,
): number {
  if (!partialEnabled) {
    return paymentMethod === "Deuda" ? 0 : total;
  }
  return clamp(normalizeNumberInput(partialRaw), 0, total);
}

function printTicket(ticket: SaleTicketResponse) {
  const popup = window.open("", "_blank", "width=500,height=760");
  if (!popup) {
    return;
  }
  const safeText = ticket.bodyText.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
  popup.document.write(`
    <html>
      <head>
        <title>${ticket.title}</title>
        <style>
          body { font-family: Consolas, monospace; margin: 18px; }
          pre { white-space: pre-wrap; line-height: 1.45; font-size: 13px; }
        </style>
      </head>
      <body>
        <pre>${safeText}</pre>
      </body>
    </html>
  `);
  popup.document.close();
  popup.focus();
  popup.print();
}

function toProductFromFavorite(row: FavoriteProductRow): ProductSummary {
  return {
    id: row.productId,
    name: row.name,
    barcode: row.barcode,
    salePrice: row.salePrice,
    stock: row.stock,
  };
}

function formatQty(value: number): string {
  if (Number.isInteger(value)) {
    return String(value);
  }
  return value.toFixed(2);
}

export function QuickSalePage() {
  const barcodeInputRef = useRef<HTMLInputElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  const [barcodeInput, setBarcodeInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState<ProductSummary[]>([]);
  const [favorites, setFavorites] = useState<FavoriteProductRow[]>([]);
  const [customers, setCustomers] = useState<CustomerSummary[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [selectedCartProductId, setSelectedCartProductId] = useState<number | null>(null);
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>(FALLBACK_METHODS);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("Efectivo");
  const [selectedCustomerId, setSelectedCustomerId] = useState("");
  const [partialEnabled, setPartialEnabled] = useState(false);
  const [partialPaidInput, setPartialPaidInput] = useState("0");
  const [dueDateInput, setDueDateInput] = useState(defaultDueDateInput);
  const [loadingBoot, setLoadingBoot] = useState(true);
  const [searching, setSearching] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [printingTicket, setPrintingTicket] = useState(false);
  const [lastSaleId, setLastSaleId] = useState<number | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);

  const total = useMemo(
    () => cart.reduce((acc, item) => acc + item.qty * item.salePrice, 0),
    [cart],
  );

  const paidAmount = useMemo(
    () => resolvePaidAmount(partialEnabled, partialPaidInput, paymentMethod, total),
    [partialEnabled, partialPaidInput, paymentMethod, total],
  );

  const debtAmount = useMemo(() => Math.max(total - paidAmount, 0), [paidAmount, total]);

  const selectedCustomer = useMemo(
    () => customers.find((customer) => String(customer.id) === selectedCustomerId) ?? null,
    [customers, selectedCustomerId],
  );

  const favoriteIdSet = useMemo(
    () => new Set(favorites.map((item) => item.productId)),
    [favorites],
  );

  const quickPickRows = useMemo<QuickPickItem[]>(() => {
    const term = searchTerm.trim();
    if (term.length > 0) {
      return searchResults.slice(0, 10).map((product) => ({
        ...product,
        favorite: favoriteIdSet.has(product.id),
        source: "search",
      }));
    }
    return favorites.slice(0, 10).map((row) => ({
      ...toProductFromFavorite(row),
      favorite: true,
      source: "favorites",
    }));
  }, [favoriteIdSet, favorites, searchResults, searchTerm]);

  async function refreshCustomersState() {
    const rows = await listCustomers(undefined, 200);
    setCustomers(rows);
  }

  async function refreshFavoritesState() {
    const rows = await listFavoriteProducts(24);
    setFavorites(rows);
  }

  async function runProductSearch(term?: string) {
    setSearching(true);
    try {
      const rows = await searchProducts(term, 30);
      setSearchResults(rows);
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setSearching(false);
    }
  }

  useEffect(() => {
    barcodeInputRef.current?.focus();
  }, []);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [methods, customerRows, favoriteRows] = await Promise.all([
          listPaymentMethods().catch(() => FALLBACK_METHODS),
          listCustomers(undefined, 200),
          listFavoriteProducts(24).catch(() => []),
        ]);
        if (!active) {
          return;
        }
        if (methods.length > 0) {
          setPaymentMethods(methods);
          setPaymentMethod(methods[0]);
        }
        setCustomers(customerRows);
        setFavorites(favoriteRows);
      } catch (error) {
        if (!active) {
          return;
        }
        setNotice({
          tone: "error",
          text: toErrorMessage(error),
        });
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

  useEffect(() => {
    if (!partialEnabled) {
      setPartialPaidInput((paymentMethod === "Deuda" ? 0 : total).toFixed(2));
      return;
    }
    const current = normalizeNumberInput(partialPaidInput);
    if (current > total) {
      setPartialPaidInput(total.toFixed(2));
    }
  }, [partialEnabled, paymentMethod, partialPaidInput, total]);

  function focusScanner() {
    barcodeInputRef.current?.focus();
  }

  function clearCart() {
    setCart([]);
    setSelectedCartProductId(null);
    setNotice({ tone: "info", text: "Carrito limpiado." });
    focusScanner();
  }

  function addProductToCart(product: ProductSummary) {
    let blockedReason = "";
    setCart((current) => {
      const safeStock = Math.max(product.stock, 0);
      if (safeStock <= 0) {
        blockedReason = `${product.name} no tiene stock disponible.`;
        return current;
      }

      const index = current.findIndex((item) => item.id === product.id);
      if (index < 0) {
        return [...current, { ...product, qty: 1 }];
      }

      const next = [...current];
      const target = next[index];
      if (target.qty >= safeStock) {
        blockedReason = `Stock maximo alcanzado para ${target.name}.`;
        return current;
      }

      next[index] = {
        ...target,
        stock: product.stock,
        salePrice: product.salePrice,
        qty: target.qty + 1,
      };
      return next;
    });

    if (blockedReason) {
      setNotice({ tone: "error", text: blockedReason });
      return;
    }
    setSelectedCartProductId(product.id);
    setNotice({ tone: "ok", text: `${product.name} agregado.` });
    focusScanner();
  }

  function updateQuantity(productId: number, delta: number) {
    let blockedReason = "";
    setCart((current) => {
      const index = current.findIndex((item) => item.id === productId);
      if (index < 0) {
        return current;
      }
      const next = [...current];
      const target = next[index];
      const updatedQty = target.qty + delta;
      if (updatedQty <= 0) {
        next.splice(index, 1);
        if (selectedCartProductId === productId) {
          setSelectedCartProductId(next[0]?.id ?? null);
        }
        return next;
      }
      if (updatedQty > target.stock) {
        blockedReason = `No hay stock suficiente para ${target.name}.`;
        return current;
      }
      next[index] = { ...target, qty: updatedQty };
      return next;
    });
    if (blockedReason) {
      setNotice({ tone: "error", text: blockedReason });
    }
  }

  async function scanBarcode() {
    const clean = barcodeInput.trim();
    if (!clean) {
      focusScanner();
      return;
    }
    try {
      const product = await getProductByBarcode(clean);
      if (!product) {
        setNotice({ tone: "error", text: "Producto no encontrado para ese codigo." });
        return;
      }
      addProductToCart(product);
      setBarcodeInput("");
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      focusScanner();
    }
  }

  async function handleSearchClick() {
    await runProductSearch(searchTerm.trim() || undefined);
  }

  async function handleToggleFavorite(product: ProductSummary, currentFavorite: boolean) {
    try {
      await setProductFavorite(product.id, !currentFavorite);
      await refreshFavoritesState();
      setNotice({
        tone: "ok",
        text: !currentFavorite ? `${product.name} agregado a favoritos.` : `${product.name} quitado de favoritos.`,
      });
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    }
  }

  async function emitTicketForSale(saleId: number, copyType = "original") {
    setPrintingTicket(true);
    try {
      const ticket = await generateSaleTicket(saleId, copyType);
      printTicket(ticket);
      return ticket;
    } finally {
      setPrintingTicket(false);
    }
  }

  const handleCheckout = useCallback(async () => {
    if (cart.length <= 0) {
      setNotice({ tone: "error", text: "Agrega al menos un producto al carrito." });
      return;
    }
    if (debtAmount > 0 && !selectedCustomerId) {
      setNotice({
        tone: "error",
        text: "Selecciona cliente para registrar deuda o pago parcial.",
      });
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        items: cart.map((item) => ({
          productId: item.id,
          quantity: item.qty,
        })),
        paymentMethod,
        customerId: selectedCustomerId ? Number.parseInt(selectedCustomerId, 10) : undefined,
        paidAmount,
        initialPaymentMethod: paymentMethod,
        dueDate: debtAmount > 0 ? dueDateInput : undefined,
      };
      const result = await createSale(payload);
      setLastSaleId(result.saleId);
      const debtInfo =
        result.balanceDue > 0
          ? ` Se registro deuda de ${moneyFormatter.format(result.balanceDue)}.`
          : "";
      setNotice({
        tone: "ok",
        text: `Venta #${result.saleId} guardada.${debtInfo}`,
      });
      setCart([]);
      setSelectedCartProductId(null);
      setPartialEnabled(false);
      setPartialPaidInput("0");
      setDueDateInput(defaultDueDateInput());
      await refreshCustomersState();
      if (searchTerm.trim().length > 0) {
        await runProductSearch(searchTerm.trim());
      }
      try {
        await emitTicketForSale(result.saleId, "original");
      } catch (ticketError) {
        setNotice({
          tone: "info",
          text: `Venta guardada (#${result.saleId}). Ticket no impreso: ${toErrorMessage(ticketError)}`,
        });
      }
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setSubmitting(false);
      focusScanner();
    }
  }, [cart, debtAmount, dueDateInput, paidAmount, paymentMethod, searchTerm, selectedCustomerId]);

  async function handleReprintLastTicket() {
    if (!lastSaleId) {
      setNotice({ tone: "error", text: "No hay venta reciente para reimprimir." });
      return;
    }
    try {
      await emitTicketForSale(lastSaleId, "reimpresion");
      setNotice({ tone: "ok", text: `Ticket de venta #${lastSaleId} reimpreso.` });
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    }
  }

  function handleBarcodeKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    void scanBarcode();
  }

  function handleSearchKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    void handleSearchClick();
  }

  useEffect(() => {
    function onGlobalKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "F2") {
        event.preventDefault();
        focusScanner();
        return;
      }
      if (event.key === "F3") {
        event.preventDefault();
        searchInputRef.current?.focus();
        return;
      }
      if (event.key === "F4") {
        event.preventDefault();
        void handleCheckout();
        return;
      }
      if (event.ctrlKey && (event.key === "l" || event.key === "L")) {
        event.preventDefault();
        clearCart();
        return;
      }
      if (selectedCartProductId && (event.key === "+" || event.key === "=")) {
        event.preventDefault();
        updateQuantity(selectedCartProductId, 1);
        return;
      }
      if (selectedCartProductId && event.key === "-") {
        event.preventDefault();
        updateQuantity(selectedCartProductId, -1);
      }
    }
    window.addEventListener("keydown", onGlobalKeyDown);
    return () => {
      window.removeEventListener("keydown", onGlobalKeyDown);
    };
  }, [handleCheckout, selectedCartProductId]);

  return (
    <div className="view-grid sale-view-grid sale-view-simple">
      <section className="panel feature-panel sale-main-panel">
        <header className="panel-header-row">
          <div>
            <h2>Venta rapida</h2>
            <p>Flujo express: escanear, revisar carrito y cobrar.</p>
          </div>
          <span className="chip chip-primary">
            <Icon name="scan" size={16} />
            POS
          </span>
        </header>

        {notice && (
          <div className={`notice-strip notice-${notice.tone}`}>
            <span>{notice.text}</span>
          </div>
        )}

        <div className="sale-fastbar">
          <label className="field barcode-field">
            <span>Escanear codigo</span>
            <input
              ref={barcodeInputRef}
              value={barcodeInput}
              onChange={(event) => setBarcodeInput(event.target.value)}
              onKeyDown={handleBarcodeKeyDown}
              placeholder="Escanear y Enter"
              autoComplete="off"
            />
          </label>

          <button type="button" onClick={() => void scanBarcode()} disabled={loadingBoot || submitting}>
            Agregar
          </button>

          <label className="field">
            <span>Buscar producto</span>
            <input
              ref={searchInputRef}
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              onKeyDown={handleSearchKeyDown}
              placeholder="Nombre o codigo"
              autoComplete="off"
            />
          </label>

          <button type="button" onClick={handleSearchClick} disabled={searching || loadingBoot}>
            {searching ? "Buscando..." : "Buscar"}
          </button>

          <button type="button" className="button-soft" onClick={clearCart} disabled={submitting}>
            Limpiar
          </button>
        </div>

        <section className="sale-quick-picks">
          <div className="sale-picks-header">
            <h4>{searchTerm.trim().length > 0 ? "Resultados rapidos" : "Favoritos"}</h4>
            <small>{searchTerm.trim().length > 0 ? "Enter para buscar" : "Productos de acceso directo"}</small>
          </div>
          <div className="catalog-list sale-pick-list">
            {quickPickRows.length <= 0 ? (
              <p className="empty-copy">Sin productos para mostrar.</p>
            ) : (
              quickPickRows.map((product) => (
                <article key={`${product.source}-${product.id}`} className="catalog-card">
                  <button type="button" className="catalog-item" onClick={() => addProductToCart(product)}>
                    <strong>{product.name}</strong>
                    <small>
                      {moneyFormatter.format(product.salePrice)} | Stock {formatQty(product.stock)}
                    </small>
                  </button>
                  <button
                    type="button"
                    className={`button-soft button-xs favorite-toggle ${product.favorite ? "active" : ""}`}
                    onClick={() => void handleToggleFavorite(product, product.favorite)}
                    title={product.favorite ? "Quitar favorito" : "Agregar favorito"}
                  >
                    <Icon name="star" size={14} />
                  </button>
                </article>
              ))
            )}
          </div>
        </section>

        <div className="table-shell sale-cart-table">
          <table>
            <thead>
              <tr>
                <th>Producto</th>
                <th>Cant.</th>
                <th>Unitario</th>
                <th>Subtotal</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {cart.length <= 0 ? (
                <tr>
                  <td colSpan={5} className="table-empty">
                    Carrito vacio. Escanea un producto para empezar.
                  </td>
                </tr>
              ) : (
                cart.map((item) => (
                  <tr
                    key={item.id}
                    className={selectedCartProductId === item.id ? "row-selected" : ""}
                    onClick={() => setSelectedCartProductId(item.id)}
                  >
                    <td>{item.name}</td>
                    <td>
                      <div className="qty-stepper">
                        <button type="button" onClick={() => updateQuantity(item.id, -1)}>
                          -
                        </button>
                        <span>{formatQty(item.qty)}</span>
                        <button type="button" onClick={() => updateQuantity(item.id, 1)}>
                          +
                        </button>
                      </div>
                    </td>
                    <td>{moneyFormatter.format(item.salePrice)}</td>
                    <td>{moneyFormatter.format(item.qty * item.salePrice)}</td>
                    <td>
                      <button
                        type="button"
                        className="button-soft button-xs"
                        onClick={() => updateQuantity(item.id, -item.qty)}
                      >
                        Quitar
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <aside className="panel checkout-panel sale-checkout-panel">
        <h3>Total y cobro</h3>
        <p>Configura cliente, metodo de pago y cobra en un paso.</p>

        <div className="total-card">
          <span>Total</span>
          <strong>{moneyFormatter.format(total)}</strong>
        </div>

        <div className="checkout-inline-grid">
          <label className="field">
            <span>Cliente</span>
            <div className="select-wrap">
              <select
                value={selectedCustomerId}
                onChange={(event) => setSelectedCustomerId(event.target.value)}
              >
                <option value="">Consumidor final</option>
                {customers.map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name}
                  </option>
                ))}
              </select>
            </div>
          </label>

          <label className="field">
            <span>Metodo</span>
            <div className="select-wrap">
              <select
                value={paymentMethod}
                onChange={(event) => setPaymentMethod(event.target.value as PaymentMethod)}
              >
                {paymentMethods.map((method) => (
                  <option key={method} value={method}>
                    {method}
                  </option>
                ))}
              </select>
            </div>
          </label>
        </div>

        {selectedCustomer && (
          <div className={`customer-debt ${selectedCustomer.overLimit ? "over-limit" : ""}`}>
            <span>Deuda actual: {moneyFormatter.format(selectedCustomer.debtTotal)}</span>
            <small>Limite: {moneyFormatter.format(selectedCustomer.alertLimit)}</small>
            {selectedCustomer.overdueSalesCount > 0 && (
              <small>{`Vencida: ${moneyFormatter.format(selectedCustomer.overdueTotal)} (${selectedCustomer.overdueSalesCount} ventas)`}</small>
            )}
          </div>
        )}

        <button
          type="button"
          className={`button-soft partial-toggle ${partialEnabled ? "active" : ""}`}
          onClick={() => {
            setPartialEnabled((current) => !current);
            if (!partialEnabled) {
              setPartialPaidInput(total.toFixed(2));
            }
          }}
        >
          {partialEnabled ? "Quitar pago parcial" : "Pago parcial"}
        </button>

        <div className={`partial-panel ${partialEnabled ? "open" : ""}`}>
          <label className="field">
            <span>Abona ahora</span>
            <input
              type="number"
              min={0}
              max={total}
              step="0.01"
              value={partialPaidInput}
              onChange={(event) => setPartialPaidInput(event.target.value)}
            />
          </label>
        </div>

        {debtAmount > 0 && (
          <label className="field">
            <span>Vence deuda</span>
            <input
              type="date"
              value={dueDateInput}
              onChange={(event) => setDueDateInput(event.target.value)}
            />
          </label>
        )}

        <div className={`debt-preview ${debtAmount > 0 ? "open" : ""}`}>
          <span>A deuda</span>
          <strong>{moneyFormatter.format(debtAmount)}</strong>
        </div>

        <button
          type="button"
          className="button-cta"
          onClick={() => void handleCheckout()}
          disabled={submitting || cart.length <= 0}
        >
          <Icon name="wallet" size={16} />
          {submitting ? "Cobrando..." : "Cobrar venta (F4)"}
        </button>

        <div className="sale-side-actions">
          <button type="button" className="button-soft" onClick={focusScanner}>
            Foco scanner (F2)
          </button>
          <button
            type="button"
            className="button-soft"
            onClick={() => void handleReprintLastTicket()}
            disabled={printingTicket || !lastSaleId}
          >
            <Icon name="print" size={16} />
            {printingTicket ? "Imprimiendo..." : "Reimprimir ultimo"}
          </button>
        </div>

        <small className="shortcut-hint">Atajos: F2 scanner, F3 buscar, F4 cobrar, Ctrl+L limpiar, +/- cantidad.</small>
      </aside>
    </div>
  );
}
