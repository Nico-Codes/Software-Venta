import { KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ComboDecisionPopup } from "../components/ComboDecisionPopup";
import { CriticalAlertPopup } from "../components/CriticalAlertPopup";
import { Icon } from "../components/Icon";
import {
  createSale,
  generateSaleTicket,
  getProductByBarcode,
  listCustomers,
  listFavoriteProducts,
  listPaymentMethods,
  previewSaleCombos,
  reverseSale,
  searchProducts,
  setProductFavorite,
} from "../tauri";
import {
  ComboChoiceGroup,
  CustomerSummary,
  ComboPreviewResponse,
  FavoriteProductRow,
  PaymentMethod,
  ProductSummary,
  SaleTicketResponse,
} from "../types";
import {
  formatInteger,
  formatMoney,
  parseIntegerInput,
  roundInteger,
} from "../utils/number";

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

type ComboDecisionGroupState = {
  signature: string;
  suggestedComboId: number;
  selectedComboId: number;
  options: ComboChoiceGroup["options"];
};

type ComboDecisionState = {
  signature: string;
  comboNames: string;
  discountAmount: number;
  groups: ComboDecisionGroupState[];
};

const FALLBACK_METHODS: PaymentMethod[] = [
  "Efectivo",
  "Credito",
  "Debito",
  "Transferencia",
  "Deuda",
  "Consumo interno",
];

const EMPTY_COMBO_PREVIEW: ComboPreviewResponse = {
  subtotalBeforeDiscount: 0,
  comboDiscountTotal: 0,
  totalAfterDiscount: 0,
  matches: [],
  ambiguousGroups: [],
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

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function normalizeNumberInput(raw: string): number {
  return parseIntegerInput(raw);
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
    return paymentMethod === "Deuda" || paymentMethod === "Consumo interno" ? 0 : total;
  }
  return roundInteger(clamp(normalizeNumberInput(partialRaw), 0, total));
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
  return formatInteger(value);
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tag = target.tagName.toLowerCase();
  if (tag === "input" || tag === "select" || tag === "textarea") {
    return true;
  }
  return Boolean(target.closest("input, select, textarea, [contenteditable='true']"));
}

export function QuickSalePage() {
  const barcodeInputRef = useRef<HTMLInputElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const customerSelectRef = useRef<HTMLSelectElement | null>(null);
  const paymentSelectRef = useRef<HTMLSelectElement | null>(null);
  const partialPaidInputRef = useRef<HTMLInputElement | null>(null);
  const dueDateInputRef = useRef<HTMLInputElement | null>(null);
  const cartStateRef = useRef<CartItem[]>([]);

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
  const [revertSaleInput, setRevertSaleInput] = useState("");
  const [revertingSale, setRevertingSale] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [criticalNotice, setCriticalNotice] = useState<Notice | null>(null);
  const [comboPreview, setComboPreview] = useState<ComboPreviewResponse>(EMPTY_COMBO_PREVIEW);
  const [comboDiscountEnabled, setComboDiscountEnabled] = useState(false);
  const [selectedComboIds, setSelectedComboIds] = useState<number[]>([]);
  const [comboDecision, setComboDecision] = useState<ComboDecisionState | null>(null);
  const comboDecisionSignatureRef = useRef("");

  const subtotal = useMemo(
    () => roundInteger(cart.reduce((acc, item) => acc + item.qty * item.salePrice, 0)),
    [cart],
  );

  const total = useMemo(() => {
    if (paymentMethod === "Consumo interno") {
      return subtotal;
    }
    if (subtotal <= 0) {
      return 0;
    }
    if (!comboDiscountEnabled) {
      return subtotal;
    }
    if (roundInteger(comboPreview.subtotalBeforeDiscount) !== roundInteger(subtotal)) {
      return subtotal;
    }
    return roundInteger(comboPreview.totalAfterDiscount);
  }, [comboDiscountEnabled, comboPreview.subtotalBeforeDiscount, comboPreview.totalAfterDiscount, paymentMethod, subtotal]);

  const paidAmount = useMemo(
    () => resolvePaidAmount(partialEnabled, partialPaidInput, paymentMethod, total),
    [partialEnabled, partialPaidInput, paymentMethod, total],
  );

  const debtAmount = useMemo(() => {
    if (paymentMethod === "Consumo interno") {
      return 0;
    }
    return Math.max(total - paidAmount, 0);
  }, [paidAmount, paymentMethod, total]);

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

  function buildComboContextSignature(preview: ComboPreviewResponse): string {
    if (preview.ambiguousGroups.length > 0) {
      return preview.ambiguousGroups
        .map((group) => {
          const options = [...group.options]
            .sort((left, right) => left.comboId - right.comboId)
            .map((option) => `${option.comboId}`)
            .join(",");
          return `${group.signature}[${options}]`;
        })
        .join("|");
    }
    if (preview.matches.length <= 0) {
      return "";
    }
    return preview.matches
      .map((match) => `${match.comboId}`)
      .sort()
      .join("|");
  }

  function buildComboDecisionFromPreview(preview: ComboPreviewResponse): ComboDecisionState | null {
    const signature = buildComboContextSignature(preview);
    if (!signature) {
      return null;
    }
    const namesFromMatches = preview.matches
      .map((match) => `${match.comboName} x${formatInteger(match.applications)}`)
      .join(", ");
    const groups: ComboDecisionGroupState[] = preview.ambiguousGroups.map((group) => {
      const selectedComboId = group.selectedComboId ?? group.suggestedComboId;
      return {
        signature: group.signature,
        suggestedComboId: group.suggestedComboId,
        selectedComboId,
        options: group.options,
      };
    });
    const comboNames =
      namesFromMatches ||
      groups
        .map((group) => group.options.find((option) => option.comboId === group.selectedComboId)?.comboName ?? "")
        .filter(Boolean)
        .join(", ");

    return {
      signature,
      comboNames: comboNames || "Combo disponible",
      discountAmount: preview.comboDiscountTotal,
      groups,
    };
  }

  function selectedComboIdsFromDecision(decision: ComboDecisionState): number[] {
    if (decision.groups.length <= 0) {
      return [];
    }
    return Array.from(
      new Set(
        decision.groups
          .map((group) => group.selectedComboId)
          .filter((comboId) => Number.isFinite(comboId) && comboId > 0),
      ),
    );
  }

  useEffect(() => {
    cartStateRef.current = cart;
  }, [cart]);

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
      setPartialPaidInput(
        formatInteger(paymentMethod === "Deuda" || paymentMethod === "Consumo interno" ? 0 : total),
      );
      return;
    }
    const current = normalizeNumberInput(partialPaidInput);
    if (current > total) {
      setPartialPaidInput(formatInteger(total));
    }
  }, [partialEnabled, paymentMethod, partialPaidInput, total]);

  useEffect(() => {
    if (paymentMethod !== "Consumo interno") {
      return;
    }
    if (partialEnabled) {
      setPartialEnabled(false);
    }
    setPartialPaidInput("0");
    setSelectedCustomerId("");
  }, [partialEnabled, paymentMethod]);

  useEffect(() => {
    if (lastSaleId !== null) {
      setRevertSaleInput(String(lastSaleId));
    }
  }, [lastSaleId]);

  useEffect(() => {
    let active = true;

    if (cart.length <= 0) {
      setComboPreview(EMPTY_COMBO_PREVIEW);
      setComboDiscountEnabled(false);
      setSelectedComboIds([]);
      setComboDecision(null);
      comboDecisionSignatureRef.current = "";
      return () => {
        active = false;
      };
    }

    if (paymentMethod === "Consumo interno") {
      setComboPreview({
        subtotalBeforeDiscount: subtotal,
        comboDiscountTotal: 0,
        totalAfterDiscount: subtotal,
        matches: [],
        ambiguousGroups: [],
      });
      setComboDiscountEnabled(false);
      setSelectedComboIds([]);
      setComboDecision(null);
      comboDecisionSignatureRef.current = "";
      return () => {
        active = false;
      };
    }

    const items = cart.map((item) => ({
      productId: item.id,
      quantity: item.qty,
    }));

    (async () => {
      try {
        const preview = await previewSaleCombos(
          items,
          comboDiscountEnabled && selectedComboIds.length > 0 ? selectedComboIds : undefined,
        );
        if (!active) {
          return;
        }
        setComboPreview(preview);
        const contextSignature = buildComboContextSignature(preview);

        if (!contextSignature) {
          comboDecisionSignatureRef.current = "";
          setComboDecision(null);
          if (comboDiscountEnabled) {
            setComboDiscountEnabled(false);
          }
          if (selectedComboIds.length > 0) {
            setSelectedComboIds([]);
          }
          return;
        }

        if (contextSignature !== comboDecisionSignatureRef.current) {
          const nextDecision = buildComboDecisionFromPreview(preview);
          if (nextDecision) {
            setComboDecision(nextDecision);
            if (comboDiscountEnabled) {
              setComboDiscountEnabled(false);
            }
            if (selectedComboIds.length > 0) {
              setSelectedComboIds([]);
            }
          }
        }
      } catch (error) {
        if (!active) {
          return;
        }
        setComboPreview({
          subtotalBeforeDiscount: subtotal,
          comboDiscountTotal: 0,
          totalAfterDiscount: subtotal,
          matches: [],
          ambiguousGroups: [],
        });
        setComboDecision(null);
        setComboDiscountEnabled(false);
        setSelectedComboIds([]);
        comboDecisionSignatureRef.current = "";
        setNotice({ tone: "error", text: toErrorMessage(error) });
      }
    })();

    return () => {
      active = false;
    };
  }, [cart, comboDiscountEnabled, paymentMethod, selectedComboIds, subtotal]);

  useEffect(() => {
    if (!notice || notice.tone !== "error") {
      return;
    }
    setCriticalNotice(notice);
  }, [notice]);

  function focusScanner() {
    barcodeInputRef.current?.focus();
  }

  function focusSearch() {
    searchInputRef.current?.focus();
  }

  function focusPartialAmount() {
    partialPaidInputRef.current?.focus();
    partialPaidInputRef.current?.select();
  }

  function focusDueDate() {
    dueDateInputRef.current?.focus();
  }

  function closeCriticalNotice() {
    setCriticalNotice(null);
    focusScanner();
  }

  function handleComboOptionSelect(signature: string, comboId: number) {
    setComboDecision((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        groups: current.groups.map((group) =>
          group.signature === signature ? { ...group, selectedComboId: comboId } : group,
        ),
      };
    });
  }

  function handleApplyComboDiscount() {
    if (!comboDecision) {
      return;
    }
    const nextSelectedIds = selectedComboIdsFromDecision(comboDecision);
    comboDecisionSignatureRef.current = comboDecision.signature;
    setSelectedComboIds(nextSelectedIds);
    setComboDiscountEnabled(true);
    setComboDecision(null);
    setNotice({
      tone: "ok",
      text: `Descuento de combo aplicado (${comboDecision.comboNames}).`,
    });
    focusScanner();
  }

  function handleSkipComboDiscount() {
    if (!comboDecision) {
      return;
    }
    comboDecisionSignatureRef.current = comboDecision.signature;
    setComboDiscountEnabled(false);
    setSelectedComboIds([]);
    setComboDecision(null);
    setNotice({
      tone: "info",
      text: "Combo detectado, pero el descuento no se aplico.",
    });
    focusScanner();
  }

  function cyclePaymentMethod(step: 1 | -1) {
    if (paymentMethods.length <= 0) {
      return;
    }
    const currentIndex = paymentMethods.indexOf(paymentMethod);
    const baseIndex = currentIndex >= 0 ? currentIndex : 0;
    const nextIndex = (baseIndex + step + paymentMethods.length) % paymentMethods.length;
    setPaymentMethod(paymentMethods[nextIndex]);
  }

  function setPaymentMethodByIndex(index: number) {
    const method = FALLBACK_METHODS[index];
    if (!method) {
      return;
    }
    if (!paymentMethods.includes(method)) {
      return;
    }
    setPaymentMethod(method);
  }

  function cycleCustomer(step: 1 | -1) {
    const options = ["", ...customers.map((customer) => String(customer.id))];
    if (options.length <= 0) {
      return;
    }
    const currentIndex = options.indexOf(selectedCustomerId);
    const baseIndex = currentIndex >= 0 ? currentIndex : 0;
    const nextIndex = (baseIndex + step + options.length) % options.length;
    setSelectedCustomerId(options[nextIndex]);
  }

  function selectCartByOffset(step: 1 | -1) {
    if (cart.length <= 0) {
      return;
    }
    const ids = cart.map((item) => item.id);
    const currentIndex = selectedCartProductId !== null ? ids.indexOf(selectedCartProductId) : -1;
    const baseIndex = currentIndex >= 0 ? currentIndex : step > 0 ? -1 : 0;
    const nextIndex = (baseIndex + step + ids.length) % ids.length;
    setSelectedCartProductId(ids[nextIndex]);
  }

  function removeSelectedCartItem() {
    if (selectedCartProductId === null) {
      return;
    }
    const item = cart.find((row) => row.id === selectedCartProductId);
    if (!item) {
      return;
    }
    updateQuantity(item.id, -item.qty);
  }

  function enablePartialAndFocus() {
    if (paymentMethod === "Consumo interno") {
      return;
    }
    if (!partialEnabled) {
      setPartialEnabled(true);
      setPartialPaidInput(formatInteger(total));
    }
    requestAnimationFrame(() => {
      focusPartialAmount();
    });
  }

  function togglePartialMode() {
    if (paymentMethod === "Consumo interno") {
      return;
    }
    if (partialEnabled) {
      setPartialEnabled(false);
      focusScanner();
      return;
    }
    enablePartialAndFocus();
  }

  function clearCart() {
    cartStateRef.current = [];
    setCart([]);
    setSelectedCartProductId(null);
    setComboPreview(EMPTY_COMBO_PREVIEW);
    setComboDiscountEnabled(false);
    setSelectedComboIds([]);
    setComboDecision(null);
    comboDecisionSignatureRef.current = "";
    setNotice({ tone: "info", text: "Carrito limpiado." });
    focusScanner();
  }

  function addProductToCart(product: ProductSummary): boolean {
    const safeStock = Math.max(roundInteger(product.stock), 0);
    const roundedPrice = roundInteger(product.salePrice);
    if (safeStock <= 0) {
      setNotice({ tone: "error", text: `${product.name} no tiene stock disponible.` });
      return false;
    }

    const current = cartStateRef.current;
    const index = current.findIndex((item) => item.id === product.id);
    let next: CartItem[];
    if (index < 0) {
      next = [...current, { ...product, qty: 1, stock: safeStock, salePrice: roundedPrice }];
    } else {
      const target = current[index];
      if (target.qty >= safeStock) {
        setNotice({ tone: "error", text: `Stock maximo alcanzado para ${target.name}.` });
        return false;
      }
      next = [...current];
      next[index] = {
        ...target,
        stock: safeStock,
        salePrice: roundedPrice,
        qty: target.qty + 1,
      };
    }

    cartStateRef.current = next;
    setCart(next);
    setSelectedCartProductId(product.id);
    setNotice({ tone: "ok", text: `${product.name} agregado.` });
    focusScanner();
    return true;
  }

  function updateQuantity(productId: number, delta: number) {
    const current = cartStateRef.current;
    const index = current.findIndex((item) => item.id === productId);
    if (index < 0) {
      return;
    }
    const next = [...current];
    const target = next[index];
    const updatedQty = target.qty + delta;
    if (updatedQty <= 0) {
      next.splice(index, 1);
      cartStateRef.current = next;
      setCart(next);
      if (selectedCartProductId === productId) {
        setSelectedCartProductId(next[0]?.id ?? null);
      }
      return;
    }
    if (updatedQty > target.stock) {
      setNotice({ tone: "error", text: `No hay stock suficiente para ${target.name}.` });
      return;
    }
    next[index] = { ...target, qty: updatedQty };
    cartStateRef.current = next;
    setCart(next);
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
      const safeStock = Math.max(roundInteger(product.stock), 0);
      if (safeStock <= 0) {
        setNotice({ tone: "error", text: `${product.name} sin stock. No se puede vender.` });
        return;
      }
      const added = addProductToCart(product);
      if (added) {
        setBarcodeInput("");
      }
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      focusScanner();
    }
  }

  async function handleSearchClick() {
    await runProductSearch(searchTerm.trim() || undefined);
  }

  function addFirstQuickPick() {
    const first = quickPickRows[0];
    if (!first) {
      setNotice({ tone: "info", text: "No hay productos rapidos para agregar." });
      return;
    }
    addProductToCart(first);
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
    const isInternalConsumption = paymentMethod === "Consumo interno";
    if (!isInternalConsumption && debtAmount > 0 && !selectedCustomerId) {
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
        customerId: !isInternalConsumption && selectedCustomerId ? Number.parseInt(selectedCustomerId, 10) : undefined,
        paidAmount,
        initialPaymentMethod: !isInternalConsumption ? paymentMethod : undefined,
        dueDate: !isInternalConsumption && debtAmount > 0 ? dueDateInput : undefined,
        selectedComboIds:
          !isInternalConsumption && comboDiscountEnabled && selectedComboIds.length > 0
            ? selectedComboIds
            : undefined,
        applyComboDiscount: !isInternalConsumption ? comboDiscountEnabled : false,
      };
      const result = await createSale(payload);
      setLastSaleId(result.saleId);
      const debtInfo =
        result.balanceDue > 0
          ? ` Se registro deuda de ${formatMoney(result.balanceDue)}.`
          : "";
      const internalInfo =
        result.saleType === "internal" ? " Consumo interno registrado correctamente." : "";
      const comboInfo =
        result.comboDiscountTotal > 0
          ? ` Descuento combos: ${formatMoney(result.comboDiscountTotal)}.`
          : "";
      setNotice({
        tone: "ok",
        text: `Venta #${result.saleId} guardada.${debtInfo}${comboInfo}${internalInfo}`,
      });
      cartStateRef.current = [];
      setCart([]);
      setSelectedCartProductId(null);
      setComboPreview(EMPTY_COMBO_PREVIEW);
      setComboDiscountEnabled(false);
      setSelectedComboIds([]);
      setComboDecision(null);
      comboDecisionSignatureRef.current = "";
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
  }, [
    cart,
    comboDiscountEnabled,
    debtAmount,
    dueDateInput,
    paidAmount,
    paymentMethod,
    searchTerm,
    selectedComboIds,
    selectedCustomerId,
  ]);

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

  async function handleReverseSale() {
    const saleId = Number.parseInt(revertSaleInput.trim(), 10);
    if (!Number.isFinite(saleId) || saleId <= 0) {
      setNotice({ tone: "error", text: "Ingresa un numero de venta valido para revertir." });
      return;
    }

    const confirmed = window.confirm(
      `Revertir venta #${saleId}? Se restaura stock y se eliminan deuda/pagos asociados.`,
    );
    if (!confirmed) {
      return;
    }

    setRevertingSale(true);
    try {
      const result = await reverseSale({
        saleId,
        reason: "Reversion manual desde venta rapida",
      });
      setNotice({
        tone: "ok",
        text: `Venta #${result.saleId} revertida. Items restaurados: ${formatInteger(result.restoredItems)} | Unidades: ${formatInteger(result.restoredUnits)}.`,
      });
      if (lastSaleId === saleId) {
        setLastSaleId(null);
      }
      await refreshCustomersState();
      await refreshFavoritesState();
      if (searchTerm.trim().length > 0) {
        await runProductSearch(searchTerm.trim());
      }
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setRevertingSale(false);
      focusScanner();
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

  function handleCheckoutFieldKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") {
      return;
    }
    event.preventDefault();
    void handleCheckout();
  }

  useEffect(() => {
    function onGlobalKeyDown(event: globalThis.KeyboardEvent) {
      const key = event.key;
      const editableContext = isEditableTarget(event.target);
      if (comboDecision) {
        if (key === "Escape") {
          event.preventDefault();
          handleSkipComboDiscount();
        } else if (key === "Enter") {
          event.preventDefault();
          handleApplyComboDiscount();
        }
        return;
      }
      const forceShortcut =
        key === "Escape" ||
        key === "F2" ||
        key === "F3" ||
        key === "F4" ||
        key === "F5" ||
        key === "F6" ||
        key === "F7" ||
        key === "F8" ||
        key === "F9" ||
        key === "F10";
      const altPaymentShortcut =
        event.altKey && !event.ctrlKey && !event.shiftKey && !event.metaKey && /^[1-6]$/.test(key);

      if (editableContext && !forceShortcut && !altPaymentShortcut) {
        return;
      }

      if (key === "Escape") {
        event.preventDefault();
        focusScanner();
        return;
      }

      if (event.key === "F2") {
        event.preventDefault();
        focusScanner();
        return;
      }
      if (event.key === "F3") {
        event.preventDefault();
        focusSearch();
        return;
      }
      if (event.key === "F4") {
        event.preventDefault();
        void handleCheckout();
        return;
      }
      if (event.key === "F5") {
        event.preventDefault();
        togglePartialMode();
        return;
      }
      if (event.key === "F6") {
        event.preventDefault();
        cyclePaymentMethod(event.shiftKey ? -1 : 1);
        return;
      }
      if (event.key === "F7") {
        event.preventDefault();
        cycleCustomer(event.shiftKey ? -1 : 1);
        return;
      }
      if (event.key === "F8") {
        event.preventDefault();
        enablePartialAndFocus();
        return;
      }
      if (event.key === "F9") {
        if (debtAmount > 0) {
          event.preventDefault();
          focusDueDate();
        }
        return;
      }
      if (event.key === "F10") {
        event.preventDefault();
        addFirstQuickPick();
        return;
      }
      if (altPaymentShortcut) {
        event.preventDefault();
        const raw = Number.parseInt(key, 10);
        if (!Number.isNaN(raw)) {
          setPaymentMethodByIndex(raw - 1);
        }
        return;
      }
      if (event.ctrlKey && (event.key === "l" || event.key === "L")) {
        event.preventDefault();
        clearCart();
        return;
      }

      if (editableContext) {
        return;
      }

      if (event.key === "ArrowDown") {
        event.preventDefault();
        selectCartByOffset(1);
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        selectCartByOffset(-1);
        return;
      }
      if (selectedCartProductId && (event.key === "+" || event.key === "=" || event.key === "Add")) {
        event.preventDefault();
        updateQuantity(selectedCartProductId, 1);
        return;
      }
      if (selectedCartProductId && (event.key === "-" || event.key === "Subtract")) {
        event.preventDefault();
        updateQuantity(selectedCartProductId, -1);
        return;
      }
      if (selectedCartProductId && (event.key === "Delete" || event.key === "Backspace")) {
        event.preventDefault();
        removeSelectedCartItem();
      }
    }
    window.addEventListener("keydown", onGlobalKeyDown);
    return () => {
      window.removeEventListener("keydown", onGlobalKeyDown);
    };
  }, [
    addFirstQuickPick,
    cart,
    comboDecision,
    customers,
    debtAmount,
    handleApplyComboDiscount,
    handleCheckout,
    handleSkipComboDiscount,
    partialEnabled,
    paymentMethod,
    paymentMethods,
    selectedCartProductId,
    selectedCustomerId,
    total,
  ]);

  return (
    <>
      <CriticalAlertPopup
        open={Boolean(criticalNotice)}
        title="Error operativo"
        message={criticalNotice?.text ?? ""}
        onClose={closeCriticalNotice}
      />
      <ComboDecisionPopup
        open={Boolean(comboDecision)}
        comboNames={comboDecision?.comboNames ?? ""}
        discountAmount={comboDecision?.discountAmount ?? 0}
        groups={comboDecision?.groups ?? []}
        onSelectCombo={handleComboOptionSelect}
        onApply={handleApplyComboDiscount}
        onSkip={handleSkipComboDiscount}
      />
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
                      {formatMoney(product.salePrice)} | Stock {formatQty(product.stock)}
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
                    onFocus={() => setSelectedCartProductId(item.id)}
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelectedCartProductId(item.id);
                        return;
                      }
                      if (event.key === "+" || event.key === "=" || event.key === "Add") {
                        event.preventDefault();
                        updateQuantity(item.id, 1);
                        return;
                      }
                      if (event.key === "-" || event.key === "Subtract") {
                        event.preventDefault();
                        updateQuantity(item.id, -1);
                        return;
                      }
                      if (event.key === "Delete" || event.key === "Backspace") {
                        event.preventDefault();
                        updateQuantity(item.id, -item.qty);
                      }
                    }}
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
                    <td>{formatMoney(item.salePrice)}</td>
                    <td>{formatMoney(item.qty * item.salePrice)}</td>
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
          <strong>{formatMoney(total)}</strong>
        </div>

        {paymentMethod !== "Consumo interno" &&
          comboDiscountEnabled &&
          roundInteger(comboPreview.subtotalBeforeDiscount) === roundInteger(subtotal) &&
          comboPreview.comboDiscountTotal > 0 && (
          <div className="combo-summary-card">
            <small>Subtotal lista: {formatMoney(comboPreview.subtotalBeforeDiscount)}</small>
            <small>{`Descuento combos: -${formatMoney(comboPreview.comboDiscountTotal)}`}</small>
            <small>Total final: {formatMoney(total)}</small>
            <p>
              {comboPreview.matches
                .map((match) => `${match.comboName} x${formatInteger(match.applications)}`)
                .join(" | ")}
            </p>
          </div>
        )}

        <div className="checkout-inline-grid">
          <label className="field">
            <span>Cliente</span>
            <div className="select-wrap">
              <select
                ref={customerSelectRef}
                value={selectedCustomerId}
                onChange={(event) => setSelectedCustomerId(event.target.value)}
                disabled={paymentMethod === "Consumo interno"}
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
                ref={paymentSelectRef}
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

        {paymentMethod === "Consumo interno" && (
          <div className="notice-strip notice-info">
            <span>Modo consumo interno: descuenta stock sin generar deuda ni ganancia.</span>
          </div>
        )}

        {selectedCustomer && (
          <div className={`customer-debt ${selectedCustomer.overLimit ? "over-limit" : ""}`}>
            <span>Deuda actual: {formatMoney(selectedCustomer.debtTotal)}</span>
            <small>Limite: {formatMoney(selectedCustomer.alertLimit)}</small>
            {selectedCustomer.overdueSalesCount > 0 && (
              <small>{`Vencida: ${formatMoney(selectedCustomer.overdueTotal)} (${selectedCustomer.overdueSalesCount} ventas)`}</small>
            )}
          </div>
        )}

        <button
          type="button"
          className={`button-soft partial-toggle ${partialEnabled ? "active" : ""}`}
          onClick={togglePartialMode}
          disabled={paymentMethod === "Consumo interno"}
        >
          {partialEnabled ? "Quitar pago parcial" : "Pago parcial"}
        </button>

        {paymentMethod !== "Consumo interno" && (
          <div className={`partial-panel ${partialEnabled ? "open" : ""}`}>
            <label className="field">
              <span>Abona ahora</span>
              <input
                ref={partialPaidInputRef}
                type="number"
                min={0}
                max={total}
                step="1"
                value={partialPaidInput}
                onChange={(event) => setPartialPaidInput(event.target.value)}
                onKeyDown={handleCheckoutFieldKeyDown}
              />
            </label>
          </div>
        )}

        {paymentMethod !== "Consumo interno" && debtAmount > 0 && (
          <label className="field">
            <span>Vence deuda</span>
            <input
              ref={dueDateInputRef}
              type="date"
              value={dueDateInput}
              onChange={(event) => setDueDateInput(event.target.value)}
              onKeyDown={handleCheckoutFieldKeyDown}
            />
          </label>
        )}

        {paymentMethod === "Consumo interno" ? (
          <div className="debt-preview open">
            <span>Consumo interno</span>
            <strong>{formatMoney(total)}</strong>
          </div>
        ) : (
          <div className={`debt-preview ${debtAmount > 0 ? "open" : ""}`}>
            <span>A deuda</span>
            <strong>{formatMoney(debtAmount)}</strong>
          </div>
        )}

        <button
          type="button"
          className="button-cta"
          onClick={() => void handleCheckout()}
          disabled={submitting || cart.length <= 0}
        >
          <Icon name="wallet" size={16} />
          {submitting ? "Procesando..." : paymentMethod === "Consumo interno" ? "Registrar consumo (F4)" : "Cobrar venta (F4)"}
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

        <div className="sale-revert-card">
          <label className="field">
            <span>Revertir venta</span>
            <input
              type="number"
              min={1}
              step="1"
              value={revertSaleInput}
              onChange={(event) => setRevertSaleInput(event.target.value)}
              placeholder="Nro de venta"
            />
          </label>
          <button
            type="button"
            className="button-soft"
            onClick={() => void handleReverseSale()}
            disabled={revertingSale}
          >
            {revertingSale ? "Revirtiendo..." : "Revertir venta"}
          </button>
        </div>

        <small className="shortcut-hint">
          Atajos: F2 scanner, F3 buscar, F4 cobrar, F5 parcial, F6 metodo, F7 cliente, F8 abono, F9 vencimiento,
          F10 primer rapido, Flechas carrito, +/- cantidad, Del quitar, Alt+1..6 metodo, Ctrl+L limpiar, Esc scanner.
        </small>
      </aside>
      </div>
    </>
  );
}
