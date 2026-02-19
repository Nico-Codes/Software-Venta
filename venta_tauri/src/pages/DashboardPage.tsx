import { useEffect, useMemo, useState } from "react";

import { dashboardExecutive, dashboardSnapshot } from "../tauri";
import { DashboardExecutiveResponse, DashboardSnapshotResponse } from "../types";
import { formatInteger, formatMoney } from "../utils/number";

function toErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  return "No se pudo cargar el dashboard";
}

function currentMonthInputValue(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  return `${year}-${month}`;
}

function formatSoldDay(soldDay: string): string {
  const parsed = new Date(`${soldDay}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return soldDay;
  }
  return new Intl.DateTimeFormat("es-AR", {
    day: "2-digit",
    month: "2-digit",
  }).format(parsed);
}

export function DashboardPage() {
  const [monthInput, setMonthInput] = useState(currentMonthInputValue);
  const [snapshot, setSnapshot] = useState<DashboardSnapshotResponse | null>(null);
  const [executive, setExecutive] = useState<DashboardExecutiveResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState("");

  async function loadSnapshot() {
    setLoading(true);
    setErrorText("");
    try {
      const [summaryData, executiveData] = await Promise.all([
        dashboardSnapshot(monthInput),
        dashboardExecutive(monthInput),
      ]);
      setSnapshot(summaryData);
      setExecutive(executiveData);
    } catch (error) {
      setErrorText(toErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadSnapshot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const maxPaymentTotal = useMemo(() => {
    if (!snapshot || snapshot.paymentBreakdown.length <= 0) {
      return 1;
    }
    return Math.max(...snapshot.paymentBreakdown.map((item) => item.total), 1);
  }, [snapshot]);

  const maxDailyTotal = useMemo(() => {
    if (!snapshot || snapshot.dailySales.length <= 0) {
      return 1;
    }
    return Math.max(...snapshot.dailySales.map((item) => item.total), 1);
  }, [snapshot]);

  return (
    <section className="dashboard-grid">
      <header className="panel dashboard-header">
        <div>
          <h2>Dashboard financiero</h2>
          <p>Vista mensual de ventas, pagos, rentabilidad y alertas operativas.</p>
        </div>
        <div className="dashboard-controls">
          <label className="field">
            <span>Mes</span>
            <input
              type="month"
              value={monthInput}
              onChange={(event) => setMonthInput(event.target.value)}
            />
          </label>
          <button type="button" onClick={() => void loadSnapshot()} disabled={loading}>
            {loading ? "Actualizando..." : "Actualizar"}
          </button>
        </div>
      </header>

      {errorText && (
        <div className="notice-strip notice-error">
          <span>{errorText}</span>
        </div>
      )}

      <div className="dashboard-kpis">
        <article className="panel kpi-card">
          <span>Ventas</span>
          <strong>{formatInteger(snapshot?.summary.salesCount ?? 0)}</strong>
        </article>
        <article className="panel kpi-card">
          <span>Total vendido</span>
          <strong>{formatMoney(snapshot?.summary.grossTotal ?? 0)}</strong>
        </article>
        <article className="panel kpi-card">
          <span>Cobrado</span>
          <strong>{formatMoney(snapshot?.summary.paidTotal ?? 0)}</strong>
        </article>
        <article className="panel kpi-card">
          <span>Deuda pendiente</span>
          <strong>{formatMoney(snapshot?.summary.dueTotal ?? 0)}</strong>
        </article>
        <article className="panel kpi-card">
          <span>Ganancia estimada</span>
          <strong>{formatMoney(snapshot?.summary.estimatedProfit ?? 0)}</strong>
        </article>
        <article className="panel kpi-card">
          <span>Consumo interno</span>
          <strong>{formatMoney(snapshot?.summary.internalConsumptionTotal ?? 0)}</strong>
          <small>{`${formatInteger(snapshot?.summary.internalOperationsCount ?? 0)} mov.`}</small>
        </article>
        <article className="panel kpi-card">
          <span>Resultado neto</span>
          <strong>{formatMoney(snapshot?.summary.netProfitAfterInternal ?? 0)}</strong>
        </article>
        <article className="panel kpi-card">
          <span>Delta venta vs mes previo</span>
          <strong>{`${(executive?.grossDeltaPercent ?? 0).toFixed(1)}%`}</strong>
        </article>
        <article className="panel kpi-card">
          <span>Delta ticket promedio</span>
          <strong>{`${(executive?.avgTicketDeltaPercent ?? 0).toFixed(1)}%`}</strong>
        </article>
      </div>

      <div className="dashboard-panels">
        <article className="panel dashboard-block">
          <h3>Ventas diarias</h3>
          <div className="bar-list">
            {!snapshot || snapshot.dailySales.length <= 0 ? (
              <p className="empty-copy">Sin ventas cargadas para el mes seleccionado.</p>
            ) : (
              snapshot.dailySales.map((item) => (
                <div key={item.soldDay} className="bar-row">
                  <span>{formatSoldDay(item.soldDay)}</span>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{ width: `${Math.max((item.total / maxDailyTotal) * 100, 3)}%` }}
                    />
                  </div>
                  <strong>{formatMoney(item.total)}</strong>
                </div>
              ))
            )}
          </div>
        </article>

        <article className="panel dashboard-block">
          <h3>Metodos de pago</h3>
          <div className="bar-list">
            {!snapshot || snapshot.paymentBreakdown.length <= 0 ? (
              <p className="empty-copy">Sin pagos registrados para el mes seleccionado.</p>
            ) : (
              snapshot.paymentBreakdown.map((item) => (
                <div key={item.paymentMethod} className="bar-row">
                  <span>{item.paymentMethod}</span>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{ width: `${Math.max((item.total / maxPaymentTotal) * 100, 3)}%` }}
                    />
                  </div>
                  <strong>{formatMoney(item.total)}</strong>
                </div>
              ))
            )}
          </div>
        </article>

        <article className="panel dashboard-block">
          <h3>Top productos</h3>
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Unidades</th>
                  <th>Facturacion</th>
                </tr>
              </thead>
              <tbody>
                {!snapshot || snapshot.topProducts.length <= 0 ? (
                  <tr>
                    <td colSpan={3} className="table-empty">
                      Sin datos.
                    </td>
                  </tr>
                ) : (
                  snapshot.topProducts.map((item) => (
                    <tr key={`top-${item.productName}`}>
                      <td>{item.productName}</td>
                      <td>{formatInteger(item.quantity)}</td>
                      <td>{formatMoney(item.revenue)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel dashboard-block">
          <h3>Menor salida</h3>
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Unidades</th>
                  <th>Facturacion</th>
                </tr>
              </thead>
              <tbody>
                {!snapshot || snapshot.lowProducts.length <= 0 ? (
                  <tr>
                    <td colSpan={3} className="table-empty">
                      Sin datos.
                    </td>
                  </tr>
                ) : (
                  snapshot.lowProducts.map((item) => (
                    <tr key={`low-${item.productName}`}>
                      <td>{item.productName}</td>
                      <td>{formatInteger(item.quantity)}</td>
                      <td>{formatMoney(item.revenue)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel dashboard-block dashboard-block-full">
          <h3>Alertas de stock</h3>
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Stock</th>
                  <th>Minimo</th>
                  <th>Faltante</th>
                </tr>
              </thead>
              <tbody>
                {!snapshot || snapshot.lowStockAlerts.length <= 0 ? (
                  <tr>
                    <td colSpan={4} className="table-empty">
                      Sin alertas de stock en este momento.
                    </td>
                  </tr>
                ) : (
                  snapshot.lowStockAlerts.map((item) => (
                    <tr key={`alert-${item.id}`}>
                      <td>{item.name}</td>
                      <td>{formatInteger(item.stock)}</td>
                      <td>{formatInteger(item.minStock)}</td>
                      <td>{formatInteger(item.shortage)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel dashboard-block">
          <h3>Horas pico</h3>
          <div className="bar-list">
            {!executive || executive.peakHours.length <= 0 ? (
              <p className="empty-copy">Sin datos horarios para el periodo.</p>
            ) : (
              executive.peakHours.map((item) => (
                <div key={`hour-${item.hour}`} className="bar-row">
                  <span>{`${String(item.hour).padStart(2, "0")}:00`}</span>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{
                        width: `${Math.max(
                          (item.total / Math.max(...executive.peakHours.map((row) => row.total), 1)) * 100,
                          3,
                        )}%`,
                      }}
                    />
                  </div>
                  <strong>{formatMoney(item.total)}</strong>
                </div>
              ))
            )}
          </div>
        </article>

        <article className="panel dashboard-block">
          <h3>Margen por categoria</h3>
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>Categoria</th>
                  <th>Venta</th>
                  <th>Ganancia</th>
                </tr>
              </thead>
              <tbody>
                {!executive || executive.categoryProfit.length <= 0 ? (
                  <tr>
                    <td colSpan={3} className="table-empty">
                      Sin datos.
                    </td>
                  </tr>
                ) : (
                  executive.categoryProfit.map((item) => (
                    <tr key={`cat-${item.categoryName}`}>
                      <td>{item.categoryName}</td>
                      <td>{formatMoney(item.revenue)}</td>
                      <td>{formatMoney(item.profit)}</td>
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
