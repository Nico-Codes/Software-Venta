import { useEffect, useMemo, useState } from "react";

import {
  generateSaleTicket,
  listTicketPrints,
  ticketSettings,
  updateTicketSettings,
} from "../tauri";
import {
  SaleTicketResponse,
  TicketPrintRow,
  TicketSettingsResponse,
  UpdateTicketSettingsRequest,
} from "../types";
import { formatMoney } from "../utils/number";

type Notice = {
  tone: "ok" | "error" | "info";
  text: string;
};

type SettingsDraft = {
  storeName: string;
  taxId: string;
  address: string;
  phone: string;
  headerText: string;
  footerText: string;
  paperWidthMm: string;
  logoPath: string;
  showLogo: boolean;
};

const EMPTY_DRAFT: SettingsDraft = {
  storeName: "",
  taxId: "",
  address: "",
  phone: "",
  headerText: "",
  footerText: "",
  paperWidthMm: "80",
  logoPath: "",
  showLogo: false,
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

function syncDraft(settings: TicketSettingsResponse): SettingsDraft {
  return {
    storeName: settings.storeName,
    taxId: settings.taxId,
    address: settings.address,
    phone: settings.phone,
    headerText: settings.headerText,
    footerText: settings.footerText,
    paperWidthMm: String(settings.paperWidthMm),
    logoPath: settings.logoPath,
    showLogo: settings.showLogo,
  };
}

function printTicket(ticket: SaleTicketResponse) {
  const popup = window.open("", "_blank", "width=500,height=760");
  if (!popup) {
    return;
  }
  const safeText = ticket.bodyText
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
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

export function TicketsPage() {
  const [settings, setSettings] = useState<TicketSettingsResponse | null>(null);
  const [draft, setDraft] = useState<SettingsDraft>(EMPTY_DRAFT);
  const [prints, setPrints] = useState<TicketPrintRow[]>([]);
  const [saleIdInput, setSaleIdInput] = useState("");
  const [copyType, setCopyType] = useState("reimpresion");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [printing, setPrinting] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);

  const previewText = useMemo(() => {
    const lines = [
      draft.storeName || "Mi Local",
      draft.headerText || "",
      "---",
      "1 x Producto ejemplo   1200",
      "TOTAL                1200",
      "Pago: Efectivo",
      "---",
      draft.footerText || "Gracias por su compra",
    ];
    return lines.filter((line) => line.length > 0).join("\n");
  }, [draft.footerText, draft.headerText, draft.storeName]);

  async function refreshData() {
    setLoading(true);
    try {
      const [settingsResult, printsResult] = await Promise.all([
        ticketSettings(),
        listTicketPrints(160),
      ]);
      setSettings(settingsResult);
      setDraft(syncDraft(settingsResult));
      setPrints(printsResult);
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshData();
  }, []);

  async function handleSaveSettings() {
    const paperWidthMm = Number.parseInt(draft.paperWidthMm.trim(), 10);
    if (!Number.isFinite(paperWidthMm) || (paperWidthMm !== 58 && paperWidthMm !== 80)) {
      setNotice({ tone: "error", text: "El ancho de papel debe ser 58 mm o 80 mm." });
      return;
    }

    const payload: UpdateTicketSettingsRequest = {
      storeName: draft.storeName.trim() || undefined,
      taxId: draft.taxId.trim() || undefined,
      address: draft.address.trim() || undefined,
      phone: draft.phone.trim() || undefined,
      headerText: draft.headerText.trim() || undefined,
      footerText: draft.footerText.trim() || undefined,
      paperWidthMm,
      logoPath: draft.logoPath.trim() || undefined,
      showLogo: draft.showLogo,
    };

    setSaving(true);
    try {
      const updated = await updateTicketSettings(payload);
      setSettings(updated);
      setDraft(syncDraft(updated));
      setNotice({ tone: "ok", text: "Configuracion de ticket guardada." });
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setSaving(false);
    }
  }

  async function handlePrintBySaleId() {
    const saleId = Number.parseInt(saleIdInput.trim(), 10);
    if (!Number.isFinite(saleId) || saleId <= 0) {
      setNotice({ tone: "error", text: "Ingresa un numero de venta valido." });
      return;
    }

    setPrinting(true);
    try {
      const ticket = await generateSaleTicket(saleId, copyType);
      printTicket(ticket);
      setNotice({ tone: "ok", text: `Ticket generado para venta #${saleId}.` });
      const rows = await listTicketPrints(160);
      setPrints(rows);
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setPrinting(false);
    }
  }

  async function handleReprint(row: TicketPrintRow) {
    setPrinting(true);
    try {
      const ticket = await generateSaleTicket(row.saleId, "reimpresion");
      printTicket(ticket);
      setNotice({ tone: "ok", text: `Ticket reimpreso para venta #${row.saleId}.` });
      const rows = await listTicketPrints(160);
      setPrints(rows);
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setPrinting(false);
    }
  }

  return (
    <section className="tickets-grid">
      <section className="panel tickets-settings-panel">
        <header className="section-head">
          <h2>Tickets e impresion</h2>
          <p>Configura plantilla del ticket, datos fiscales y ancho de papel.</p>
        </header>

        {notice && (
          <div className={`notice-strip notice-${notice.tone}`}>
            <span>{notice.text}</span>
          </div>
        )}

        <div className="tickets-form">
          <div className="split-grid">
            <label className="field">
              <span>Nombre del local</span>
              <input
                value={draft.storeName}
                onChange={(event) => setDraft((prev) => ({ ...prev, storeName: event.target.value }))}
                placeholder="Vinoteca Central"
              />
            </label>
            <label className="field">
              <span>CUIT / ID fiscal</span>
              <input
                value={draft.taxId}
                onChange={(event) => setDraft((prev) => ({ ...prev, taxId: event.target.value }))}
                placeholder="30-XXXXXXXX-X"
              />
            </label>
          </div>

          <label className="field">
            <span>Direccion</span>
            <input
              value={draft.address}
              onChange={(event) => setDraft((prev) => ({ ...prev, address: event.target.value }))}
            />
          </label>

          <div className="split-grid">
            <label className="field">
              <span>Telefono</span>
              <input
                value={draft.phone}
                onChange={(event) => setDraft((prev) => ({ ...prev, phone: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Ancho papel (mm)</span>
              <input
                type="number"
                min={58}
                max={80}
                step={22}
                value={draft.paperWidthMm}
                onChange={(event) => setDraft((prev) => ({ ...prev, paperWidthMm: event.target.value }))}
              />
            </label>
          </div>

          <label className="field">
            <span>Texto cabecera</span>
            <input
              value={draft.headerText}
              onChange={(event) => setDraft((prev) => ({ ...prev, headerText: event.target.value }))}
            />
          </label>

          <label className="field">
            <span>Texto pie</span>
            <input
              value={draft.footerText}
              onChange={(event) => setDraft((prev) => ({ ...prev, footerText: event.target.value }))}
            />
          </label>

          <label className="field">
            <span>Ruta logo (opcional)</span>
            <input
              value={draft.logoPath}
              onChange={(event) => setDraft((prev) => ({ ...prev, logoPath: event.target.value }))}
              placeholder="C:\\Logo\\tienda.png"
            />
          </label>

          <label className="switch-row">
            <input
              type="checkbox"
              checked={draft.showLogo}
              onChange={(event) => setDraft((prev) => ({ ...prev, showLogo: event.target.checked }))}
            />
            <span>Mostrar logo en ticket</span>
          </label>

          <div className="tickets-actions">
            <button type="button" onClick={handleSaveSettings} disabled={saving || loading}>
              {saving ? "Guardando..." : "Guardar plantilla"}
            </button>
            <button type="button" className="button-soft" onClick={() => void refreshData()} disabled={loading || saving}>
              {loading ? "Cargando..." : "Recargar"}
            </button>
          </div>
        </div>

        <div className="tickets-preview">
          <h3>Vista previa</h3>
          <pre>{previewText}</pre>
          <small>Ancho actual: {settings?.paperWidthMm ?? draft.paperWidthMm} mm</small>
        </div>
      </section>

      <section className="panel tickets-history-panel">
        <header className="section-head">
          <h2>Reimpresion</h2>
          <p>Genera tickets por numero de venta o desde historial.</p>
        </header>

        <div className="ticket-history-toolbar">
          <label className="field">
            <span>Nro de venta</span>
            <input
              value={saleIdInput}
              onChange={(event) => setSaleIdInput(event.target.value)}
              placeholder="123"
            />
          </label>
          <label className="field">
            <span>Tipo de copia</span>
            <div className="select-wrap">
              <select value={copyType} onChange={(event) => setCopyType(event.target.value)}>
                <option value="reimpresion">Reimpresion</option>
                <option value="copia">Copia</option>
                <option value="original">Original</option>
              </select>
            </div>
          </label>
          <button type="button" onClick={handlePrintBySaleId} disabled={printing || loading}>
            {printing ? "Imprimiendo..." : "Imprimir ticket"}
          </button>
        </div>

        <div className="ticket-list">
          {prints.length <= 0 ? (
            <p className="empty-copy">No hay impresiones registradas todavia.</p>
          ) : (
            prints.map((row) => (
              <article key={row.id}>
                <div>
                  <strong>{`Venta #${row.saleId} (${row.copyType})`}</strong>
                  <small>{formatDateTime(row.printedAt)}</small>
                  <small>{`Total ${formatMoney(row.total)} | Cobrado ${formatMoney(row.paidAmount)} | Deuda ${formatMoney(row.balanceDue)}`}</small>
                </div>
                <button
                  type="button"
                  className="button-soft button-xs"
                  onClick={() => void handleReprint(row)}
                  disabled={printing || loading}
                >
                  Reimprimir
                </button>
              </article>
            ))
          )}
        </div>
      </section>
    </section>
  );
}
