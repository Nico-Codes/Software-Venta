import { useEffect, useMemo, useState } from "react";

import { listPaymentMethods, salesReport } from "../tauri";
import { PaymentMethod, SalesReportResponse } from "../types";

const FALLBACK_PAYMENT_METHODS: PaymentMethod[] = [
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

const integerFormatter = new Intl.NumberFormat("es-AR", {
  maximumFractionDigits: 0,
});

function localDateInputValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function monthStartInputValue(): string {
  const now = new Date();
  return localDateInputValue(new Date(now.getFullYear(), now.getMonth(), 1));
}

function toErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  return "No se pudo cargar el reporte";
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

function escapeCsv(value: string): string {
  if (value.includes('"') || value.includes(",") || value.includes("\n")) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

function downloadCsv(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function buildReportCsv(report: SalesReportResponse): string {
  const lines: string[] = [];
  lines.push("Resumen");
  lines.push(`Desde,${escapeCsv(report.fromDate)}`);
  lines.push(`Hasta,${escapeCsv(report.toDate)}`);
  lines.push(`Metodo filtro,${escapeCsv(report.paymentMethod ?? "Todos")}`);
  lines.push(`Cantidad ventas,${report.summary.salesCount}`);
  lines.push(`Total vendido,${report.summary.grossTotal.toFixed(2)}`);
  lines.push(`Cobrado,${report.summary.paidTotal.toFixed(2)}`);
  lines.push(`Deuda pendiente,${report.summary.dueTotal.toFixed(2)}`);
  lines.push(`Ganancia estimada,${report.summary.estimatedProfit.toFixed(2)}`);
  lines.push(`Ticket promedio,${report.summary.avgTicket.toFixed(2)}`);
  lines.push("");

  lines.push("Desglose por metodo");
  lines.push("Metodo,Total");
  for (const payment of report.paymentBreakdown) {
    lines.push(`${escapeCsv(payment.paymentMethod)},${payment.total.toFixed(2)}`);
  }
  lines.push("");

  lines.push("Ventas");
  lines.push("ID,Fecha,Cliente,Metodo,Total,Pagado,Debe,Estado");
  for (const sale of report.sales) {
    lines.push(
      [
        sale.saleId,
        escapeCsv(sale.soldAt),
        escapeCsv(sale.customerName ?? ""),
        escapeCsv(sale.paymentMethod),
        sale.total.toFixed(2),
        sale.paidAmount.toFixed(2),
        sale.balanceDue.toFixed(2),
        escapeCsv(sale.status),
      ].join(","),
    );
  }
  lines.push("");

  lines.push("Productos");
  lines.push("Producto,Cantidad,Facturacion,Costo,Ganancia");
  for (const product of report.products) {
    lines.push(
      [
        escapeCsv(product.productName),
        product.quantity.toFixed(2),
        product.revenue.toFixed(2),
        product.costTotal.toFixed(2),
        product.profit.toFixed(2),
      ].join(","),
    );
  }

  return lines.join("\n");
}

export function ReportsPage() {
  const [fromDate, setFromDate] = useState(monthStartInputValue);
  const [toDate, setToDate] = useState(() => localDateInputValue(new Date()));
  const [paymentMethodFilter, setPaymentMethodFilter] = useState("Todos");
  const [paymentMethods, setPaymentMethods] = useState<string[]>(["Todos", ...FALLBACK_PAYMENT_METHODS]);
  const [report, setReport] = useState<SalesReportResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState("");

  async function loadReport() {
    setLoading(true);
    setErrorText("");
    try {
      const method = paymentMethodFilter === "Todos" ? undefined : paymentMethodFilter;
      const snapshot = await salesReport(fromDate, toDate, method, 260, 140);
      setReport(snapshot);
    } catch (error) {
      setErrorText(toErrorMessage(error));
      setReport(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let mounted = true;
    listPaymentMethods()
      .then((rows) => {
        if (!mounted) {
          return;
        }
        setPaymentMethods(["Todos", ...rows]);
      })
      .catch(() => {
        if (!mounted) {
          return;
        }
        setPaymentMethods(["Todos", ...FALLBACK_PAYMENT_METHODS]);
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    void loadReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const maxPaymentTotal = useMemo(() => {
    if (!report || report.paymentBreakdown.length <= 0) {
      return 1;
    }
    return Math.max(...report.paymentBreakdown.map((item) => item.total), 1);
  }, [report]);

  return (
    <section className="reports-grid">
      <header className="panel reports-header">
        <div>
          <h2>Reportes</h2>
          <p>Filtra por fecha y metodo de pago. Exporta a CSV para analisis externo.</p>
        </div>
        <div className="reports-toolbar">
          <label className="field">
            <span>Desde</span>
            <input type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} />
          </label>
          <label className="field">
            <span>Hasta</span>
            <input type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} />
          </label>
          <label className="field">
            <span>Metodo</span>
            <div className="select-wrap">
              <select
                value={paymentMethodFilter}
                onChange={(event) => setPaymentMethodFilter(event.target.value)}
              >
                {paymentMethods.map((method) => (
                  <option key={method} value={method}>
                    {method}
                  </option>
                ))}
              </select>
            </div>
          </label>
          <button type="button" onClick={() => void loadReport()} disabled={loading}>
            {loading ? "Actualizando..." : "Actualizar"}
          </button>
          <button
            type="button"
            className="button-soft"
            onClick={() => {
              if (!report) {
                return;
              }
              const csv = buildReportCsv(report);
              const filename = `reporte_${report.fromDate}_${report.toDate}.csv`;
              downloadCsv(filename, csv);
            }}
            disabled={!report}
          >
            Exportar CSV
          </button>
        </div>
      </header>

      {errorText && (
        <div className="notice-strip notice-error">
          <span>{errorText}</span>
        </div>
      )}

      <div className="reports-kpis">
        <article className="panel kpi-card">
          <span>Ventas</span>
          <strong>{integerFormatter.format(report?.summary.salesCount ?? 0)}</strong>
        </article>
        <article className="panel kpi-card">
          <span>Total vendido</span>
          <strong>{moneyFormatter.format(report?.summary.grossTotal ?? 0)}</strong>
        </article>
        <article className="panel kpi-card">
          <span>Cobrado</span>
          <strong>{moneyFormatter.format(report?.summary.paidTotal ?? 0)}</strong>
        </article>
        <article className="panel kpi-card">
          <span>Deuda pendiente</span>
          <strong>{moneyFormatter.format(report?.summary.dueTotal ?? 0)}</strong>
        </article>
        <article className="panel kpi-card">
          <span>Ticket promedio</span>
          <strong>{moneyFormatter.format(report?.summary.avgTicket ?? 0)}</strong>
        </article>
      </div>

      <div className="reports-panels">
        <article className="panel report-panel">
          <h3>Desglose por metodo</h3>
          <div className="bar-list">
            {!report || report.paymentBreakdown.length <= 0 ? (
              <p className="empty-copy">Sin pagos para este filtro.</p>
            ) : (
              report.paymentBreakdown.map((item) => (
                <div key={item.paymentMethod} className="bar-row">
                  <span>{item.paymentMethod}</span>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{ width: `${Math.max((item.total / maxPaymentTotal) * 100, 3)}%` }}
                    />
                  </div>
                  <strong>{moneyFormatter.format(item.total)}</strong>
                </div>
              ))
            )}
          </div>
        </article>

        <article className="panel report-panel">
          <h3>Productos del periodo</h3>
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Cantidad</th>
                  <th>Facturacion</th>
                  <th>Costo</th>
                  <th>Ganancia</th>
                </tr>
              </thead>
              <tbody>
                {!report || report.products.length <= 0 ? (
                  <tr>
                    <td colSpan={5} className="table-empty">
                      Sin datos de productos.
                    </td>
                  </tr>
                ) : (
                  report.products.map((item) => (
                    <tr key={`report-prod-${item.productName}`}>
                      <td>{item.productName}</td>
                      <td>{item.quantity.toFixed(2)}</td>
                      <td>{moneyFormatter.format(item.revenue)}</td>
                      <td>{moneyFormatter.format(item.costTotal)}</td>
                      <td>{moneyFormatter.format(item.profit)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel report-panel report-panel-full">
          <h3>Detalle de ventas</h3>
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Fecha</th>
                  <th>Cliente</th>
                  <th>Metodo</th>
                  <th>Total</th>
                  <th>Pagado</th>
                  <th>Debe</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {!report || report.sales.length <= 0 ? (
                  <tr>
                    <td colSpan={8} className="table-empty">
                      Sin ventas para este filtro.
                    </td>
                  </tr>
                ) : (
                  report.sales.map((sale) => (
                    <tr key={`report-sale-${sale.saleId}`}>
                      <td>{sale.saleId}</td>
                      <td>{formatDateTime(sale.soldAt)}</td>
                      <td>{sale.customerName || "Consumidor final"}</td>
                      <td>{sale.paymentMethod}</td>
                      <td>{moneyFormatter.format(sale.total)}</td>
                      <td>{moneyFormatter.format(sale.paidAmount)}</td>
                      <td>{moneyFormatter.format(sale.balanceDue)}</td>
                      <td>{sale.status}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </article>
      </div>
    </section>
  );
}
