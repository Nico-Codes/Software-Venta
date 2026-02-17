import { useEffect, useMemo, useState } from "react";

import { qualityAudit } from "../tauri";
import { QualityAuditResponse } from "../types";

type Notice = {
  tone: "ok" | "error" | "info";
  text: string;
};

function toErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  return "No se pudo ejecutar la auditoria";
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

export function QualityPage() {
  const [audit, setAudit] = useState<QualityAuditResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [notice, setNotice] = useState<Notice | null>(null);

  const issueCounters = useMemo(() => {
    const rows = audit?.issues ?? [];
    return {
      high: rows.filter((issue) => issue.severity === "high").length,
      medium: rows.filter((issue) => issue.severity === "medium").length,
      low: rows.filter((issue) => issue.severity === "low").length,
      total: rows.length,
    };
  }, [audit?.issues]);

  async function runAudit() {
    setLoading(true);
    try {
      const result = await qualityAudit();
      setAudit(result);
      if (result.issues.length <= 0) {
        setNotice({ tone: "ok", text: "Auditoria sin errores detectados." });
      } else {
        setNotice({ tone: "info", text: `Auditoria completa: ${result.issues.length} alertas detectadas.` });
      }
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void runAudit();
  }, []);

  return (
    <section className="quality-grid">
      <header className="panel quality-header">
        <div>
          <h2>Auditoria de calidad</h2>
          <p>Chequeo rapido de consistencia de datos, deuda, stock y trazabilidad.</p>
        </div>
        <button type="button" onClick={() => void runAudit()} disabled={loading}>
          {loading ? "Auditando..." : "Ejecutar auditoria"}
        </button>
      </header>

      {notice && (
        <div className={`notice-strip notice-${notice.tone}`}>
          <span>{notice.text}</span>
        </div>
      )}

      <div className="quality-kpis">
        <article className="panel kpi-card">
          <span>Productos</span>
          <strong>{audit?.productsCount ?? 0}</strong>
        </article>
        <article className="panel kpi-card">
          <span>Ventas</span>
          <strong>{audit?.salesCount ?? 0}</strong>
        </article>
        <article className="panel kpi-card">
          <span>Clientes</span>
          <strong>{audit?.customersCount ?? 0}</strong>
        </article>
        <article className="panel kpi-card">
          <span>Issues High</span>
          <strong>{issueCounters.high}</strong>
        </article>
        <article className="panel kpi-card">
          <span>Issues Medium</span>
          <strong>{issueCounters.medium}</strong>
        </article>
        <article className="panel kpi-card">
          <span>Issues Low</span>
          <strong>{issueCounters.low}</strong>
        </article>
      </div>

      <section className="panel quality-issues-panel">
        <header className="section-head">
          <h2>Detalle de issues</h2>
          <p>
            Ultima revision: {audit?.checkedAt ? formatDateTime(audit.checkedAt) : "-"} | Total: {issueCounters.total}
          </p>
        </header>

        <div className="quality-issues-list">
          {!audit || audit.issues.length <= 0 ? (
            <p className="empty-copy">No hay issues pendientes.</p>
          ) : (
            audit.issues.map((issue, index) => (
              <article key={`${issue.code}-${index}`} className={`quality-issue severity-${issue.severity}`}>
                <div className="quality-issue-head">
                  <strong>{issue.code}</strong>
                  <span>{issue.severity.toUpperCase()}</span>
                </div>
                <p>{issue.detail}</p>
              </article>
            ))
          )}
        </div>
      </section>
    </section>
  );
}
