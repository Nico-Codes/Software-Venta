import { useEffect, useMemo, useState } from "react";

import {
  createCustomer,
  customerAccountSnapshot,
  listCustomers,
  registerCustomerPayment,
  updateCustomer,
} from "../tauri";
import { CustomerAccountSnapshotResponse, CustomerSummary, PaymentMethod } from "../types";

type Notice = {
  tone: "ok" | "error" | "info";
  text: string;
};

type CreateCustomerFormState = {
  name: string;
  phone: string;
  email: string;
  alertLimit: string;
  notes: string;
};

const PAYMENT_METHODS_FOR_PAYMENTS: PaymentMethod[] = [
  "Efectivo",
  "Credito",
  "Debito",
  "Transferencia",
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

function parseDecimal(raw: string): number {
  const parsed = Number.parseFloat(raw.replace(",", "."));
  if (!Number.isFinite(parsed)) {
    return 0;
  }
  return parsed;
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

const EMPTY_CREATE_FORM: CreateCustomerFormState = {
  name: "",
  phone: "",
  email: "",
  alertLimit: "50000",
  notes: "",
};

export function CustomersPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [customers, setCustomers] = useState<CustomerSummary[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState("");
  const [account, setAccount] = useState<CustomerAccountSnapshotResponse | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingAccount, setLoadingAccount] = useState(false);
  const [registeringPayment, setRegisteringPayment] = useState(false);
  const [creatingCustomer, setCreatingCustomer] = useState(false);
  const [createFormOpen, setCreateFormOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateCustomerFormState>(EMPTY_CREATE_FORM);
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("Efectivo");
  const [paymentNote, setPaymentNote] = useState("");
  const [alertLimitEdit, setAlertLimitEdit] = useState("");
  const [savingCustomerConfig, setSavingCustomerConfig] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);

  const selectedCustomer = useMemo(
    () => customers.find((row) => String(row.id) === selectedCustomerId) ?? null,
    [customers, selectedCustomerId],
  );

  async function reloadCustomers(preferCustomerId?: string) {
    setLoadingList(true);
    try {
      const rows = await listCustomers(searchTerm.trim() || undefined, 220);
      setCustomers(rows);

      const requested = preferCustomerId ?? selectedCustomerId;
      if (requested && rows.some((row) => String(row.id) === requested)) {
        setSelectedCustomerId(requested);
      } else if (rows[0]) {
        setSelectedCustomerId(String(rows[0].id));
      } else {
        setSelectedCustomerId("");
        setAccount(null);
      }
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setLoadingList(false);
    }
  }

  async function loadAccount(customerIdText: string) {
    if (!customerIdText) {
      setAccount(null);
      return;
    }
    const customerId = Number.parseInt(customerIdText, 10);
    if (!Number.isFinite(customerId)) {
      setAccount(null);
      return;
    }

    setLoadingAccount(true);
    try {
      const snapshot = await customerAccountSnapshot(customerId, 40, 80);
      setAccount(snapshot);
      setAlertLimitEdit(snapshot.customer.alertLimit.toFixed(2));
      if (snapshot.customer.debtTotal > 0) {
        setPaymentAmount(snapshot.customer.debtTotal.toFixed(2));
      } else {
        setPaymentAmount("");
      }
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
      setAccount(null);
    } finally {
      setLoadingAccount(false);
    }
  }

  useEffect(() => {
    void reloadCustomers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    void loadAccount(selectedCustomerId);
  }, [selectedCustomerId]);

  async function handleCreateCustomer() {
    const cleanName = createForm.name.trim();
    const alertLimit = parseDecimal(createForm.alertLimit);
    if (!cleanName) {
      setNotice({ tone: "error", text: "Ingresa el nombre del cliente." });
      return;
    }
    if (alertLimit < 0) {
      setNotice({ tone: "error", text: "El limite de alerta no puede ser negativo." });
      return;
    }

    setCreatingCustomer(true);
    try {
      const created = await createCustomer({
        name: cleanName,
        phone: createForm.phone.trim() || undefined,
        email: createForm.email.trim() || undefined,
        alertLimit,
        notes: createForm.notes.trim() || undefined,
      });
      setNotice({ tone: "ok", text: `Cliente ${created.name} creado correctamente.` });
      setCreateFormOpen(false);
      setCreateForm(EMPTY_CREATE_FORM);
      await reloadCustomers(String(created.id));
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setCreatingCustomer(false);
    }
  }

  async function handleRegisterPayment() {
    if (!selectedCustomerId) {
      setNotice({ tone: "error", text: "Selecciona un cliente primero." });
      return;
    }
    const customerId = Number.parseInt(selectedCustomerId, 10);
    const amount = parseDecimal(paymentAmount);
    if (!Number.isFinite(customerId)) {
      setNotice({ tone: "error", text: "Cliente invalido." });
      return;
    }
    if (amount <= 0) {
      setNotice({ tone: "error", text: "El monto del abono debe ser mayor a cero." });
      return;
    }

    setRegisteringPayment(true);
    try {
      const result = await registerCustomerPayment({
        customerId,
        amount,
        paymentMethod,
        note: paymentNote.trim() || undefined,
      });
      setNotice({
        tone: "ok",
        text: `Abono aplicado: ${moneyFormatter.format(result.appliedTotal)}. Deuda restante: ${moneyFormatter.format(result.debtTotalAfter)}.`,
      });
      setPaymentNote("");
      setPaymentAmount(result.debtTotalAfter > 0 ? result.debtTotalAfter.toFixed(2) : "");
      await reloadCustomers(selectedCustomerId);
      await loadAccount(selectedCustomerId);
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setRegisteringPayment(false);
    }
  }

  async function handleUpdateAlertLimit() {
    if (!selectedCustomerId) {
      setNotice({ tone: "error", text: "Selecciona un cliente primero." });
      return;
    }
    const customerId = Number.parseInt(selectedCustomerId, 10);
    const alertLimit = parseDecimal(alertLimitEdit);
    if (!Number.isFinite(customerId)) {
      setNotice({ tone: "error", text: "Cliente invalido." });
      return;
    }
    if (alertLimit < 0) {
      setNotice({ tone: "error", text: "El limite debe ser mayor o igual a cero." });
      return;
    }

    setSavingCustomerConfig(true);
    try {
      const updated = await updateCustomer({ customerId, alertLimit });
      setNotice({
        tone: "ok",
        text: `Limite actualizado para ${updated.name}: ${moneyFormatter.format(updated.alertLimit)}.`,
      });
      await reloadCustomers(selectedCustomerId);
      await loadAccount(selectedCustomerId);
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setSavingCustomerConfig(false);
    }
  }

  return (
    <section className="customers-grid">
      <aside className="panel customers-list-panel">
        <header className="section-head">
          <h2>Clientes</h2>
          <p>Cuenta corriente y alertas de deuda.</p>
        </header>

        {notice && (
          <div className={`notice-strip notice-${notice.tone}`}>
            <span>{notice.text}</span>
          </div>
        )}

        <div className="customers-toolbar">
          <label className="field">
            <span>Buscar</span>
            <input
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Nombre o telefono"
            />
          </label>
          <button type="button" onClick={() => void reloadCustomers()} disabled={loadingList}>
            {loadingList ? "Buscando..." : "Buscar"}
          </button>
          <button
            type="button"
            className="button-soft"
            onClick={() => setCreateFormOpen((value) => !value)}
          >
            {createFormOpen ? "Cerrar alta" : "Nuevo cliente"}
          </button>
        </div>

        {createFormOpen && (
          <div className="create-customer-form">
            <label className="field">
              <span>Nombre</span>
              <input
                value={createForm.name}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, name: event.target.value }))}
              />
            </label>
            <div className="split-grid">
              <label className="field">
                <span>Telefono</span>
                <input
                  value={createForm.phone}
                  onChange={(event) => setCreateForm((prev) => ({ ...prev, phone: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Email</span>
                <input
                  value={createForm.email}
                  onChange={(event) => setCreateForm((prev) => ({ ...prev, email: event.target.value }))}
                />
              </label>
            </div>
            <label className="field">
              <span>Limite alerta</span>
              <input
                type="number"
                min={0}
                step="0.01"
                value={createForm.alertLimit}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, alertLimit: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Notas</span>
              <input
                value={createForm.notes}
                onChange={(event) => setCreateForm((prev) => ({ ...prev, notes: event.target.value }))}
              />
            </label>
            <button type="button" onClick={handleCreateCustomer} disabled={creatingCustomer}>
              {creatingCustomer ? "Creando..." : "Guardar cliente"}
            </button>
          </div>
        )}

        <div className="customers-list">
          {customers.length <= 0 ? (
            <p className="empty-copy">No hay clientes para mostrar.</p>
          ) : (
            customers.map((customer) => (
              <button
                key={customer.id}
                type="button"
                className={`customer-row ${String(customer.id) === selectedCustomerId ? "active" : ""}`}
                onClick={() => setSelectedCustomerId(String(customer.id))}
              >
                <span className="row-main">
                  <strong>{customer.name}</strong>
                  <small>{moneyFormatter.format(customer.debtTotal)}</small>
                </span>
                <span className={`row-badge ${customer.overLimit ? "alert" : ""}`}>
                  Limite {moneyFormatter.format(customer.alertLimit)}
                </span>
                {customer.overdueSalesCount > 0 && (
                  <span className="row-badge alert">
                    {`${customer.overdueSalesCount} vencidas | ${moneyFormatter.format(customer.overdueTotal)}`}
                  </span>
                )}
              </button>
            ))
          )}
        </div>
      </aside>

      <section className="panel customers-account-panel">
        {!selectedCustomer ? (
          <div className="account-empty">
            <h3>Selecciona un cliente</h3>
            <p>Veras deudas pendientes, ventas y pagos recientes.</p>
          </div>
        ) : loadingAccount || !account ? (
          <div className="account-empty">
            <h3>Cargando cuenta</h3>
            <p>Consultando datos de {selectedCustomer.name}...</p>
          </div>
        ) : (
          <div className="account-content">
            <header className="account-header">
              <div>
                <h3>{account.customer.name}</h3>
                <p>
                  {account.customer.phone || "Sin telefono"} |{" "}
                  {account.customer.email || "Sin email"}
                </p>
              </div>
              <div className={`customer-debt ${account.customer.overLimit ? "over-limit" : ""}`}>
                <span>Deuda total</span>
                <strong>{moneyFormatter.format(account.customer.debtTotal)}</strong>
                <small>Limite: {moneyFormatter.format(account.customer.alertLimit)}</small>
              </div>
            </header>

            <div className="payment-box">
              <h4>Configuracion de deuda</h4>
              <div className="payment-grid">
                <label className="field">
                  <span>Limite de alerta</span>
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    value={alertLimitEdit}
                    onChange={(event) => setAlertLimitEdit(event.target.value)}
                  />
                </label>
                <div />
                <div />
                <button
                  type="button"
                  className="button-soft"
                  onClick={handleUpdateAlertLimit}
                  disabled={savingCustomerConfig}
                >
                  {savingCustomerConfig ? "Guardando..." : "Guardar limite"}
                </button>
              </div>
            </div>

            <div className="payment-box">
              <h4>Registrar abono</h4>
              <div className="payment-grid">
                <label className="field">
                  <span>Monto</span>
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    value={paymentAmount}
                    onChange={(event) => setPaymentAmount(event.target.value)}
                  />
                </label>

                <label className="field">
                  <span>Metodo</span>
                  <div className="select-wrap">
                    <select
                      value={paymentMethod}
                      onChange={(event) => setPaymentMethod(event.target.value as PaymentMethod)}
                    >
                      {PAYMENT_METHODS_FOR_PAYMENTS.map((method) => (
                        <option key={method} value={method}>
                          {method}
                        </option>
                      ))}
                    </select>
                  </div>
                </label>

                <label className="field">
                  <span>Nota</span>
                  <input
                    value={paymentNote}
                    onChange={(event) => setPaymentNote(event.target.value)}
                    placeholder="Opcional"
                  />
                </label>

                <button type="button" onClick={handleRegisterPayment} disabled={registeringPayment}>
                  {registeringPayment ? "Aplicando..." : "Aplicar abono"}
                </button>
              </div>
            </div>

            <div className="customers-tables">
              <article className="table-box">
                <h4>Deudas pendientes</h4>
                <div className="table-shell">
                  <table>
                    <thead>
                      <tr>
                        <th>Fecha</th>
                        <th>Total</th>
                        <th>Pagado</th>
                        <th>Debe</th>
                        <th>Vence</th>
                        <th>Dias venc.</th>
                      </tr>
                    </thead>
                    <tbody>
                      {account.debtSales.length <= 0 ? (
                        <tr>
                          <td colSpan={6} className="table-empty">
                            Sin deuda pendiente.
                          </td>
                        </tr>
                      ) : (
                        account.debtSales.map((sale) => (
                          <tr key={`debt-${sale.saleId}`}>
                            <td>{formatDateTime(sale.soldAt)}</td>
                            <td>{moneyFormatter.format(sale.total)}</td>
                            <td>{moneyFormatter.format(sale.paidAmount)}</td>
                            <td>{moneyFormatter.format(sale.balanceDue)}</td>
                            <td>{sale.dueDate ? formatDateTime(`${sale.dueDate}T00:00:00`) : "-"}</td>
                            <td>{sale.overdueDays > 0 ? sale.overdueDays : "-"}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </article>

              <article className="table-box">
                <h4>Pagos recientes</h4>
                <div className="table-shell">
                  <table>
                    <thead>
                      <tr>
                        <th>Fecha</th>
                        <th>Monto</th>
                        <th>Metodo</th>
                        <th>Nota</th>
                      </tr>
                    </thead>
                    <tbody>
                      {account.recentPayments.length <= 0 ? (
                        <tr>
                          <td colSpan={4} className="table-empty">
                            Sin pagos registrados.
                          </td>
                        </tr>
                      ) : (
                        account.recentPayments.map((payment) => (
                          <tr key={`pay-${payment.id}`}>
                            <td>{formatDateTime(payment.paidAt)}</td>
                            <td>{moneyFormatter.format(payment.amount)}</td>
                            <td>{payment.paymentMethod}</td>
                            <td>{payment.note || "-"}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </article>
            </div>
          </div>
        )}
      </section>
    </section>
  );
}
