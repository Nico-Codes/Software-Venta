import { useEffect, useMemo, useState } from "react";

import { Icon, IconName } from "./components/Icon";
import { LoginPage } from "./pages/LoginPage";
import { CustomersPage } from "./pages/CustomersPage";
import { DashboardPage } from "./pages/DashboardPage";
import { InventoryPage } from "./pages/InventoryPage";
import { ProductsPage } from "./pages/ProductsPage";
import { QuickSalePage } from "./pages/QuickSalePage";
import { QuickStockPage } from "./pages/QuickStockPage";
import { ReportsPage } from "./pages/ReportsPage";
import { CategoriesPage } from "./pages/CategoriesPage";
import { UsersPage } from "./pages/UsersPage";
import { BackupPage } from "./pages/BackupPage";
import { TicketsPage } from "./pages/TicketsPage";
import { QualityPage } from "./pages/QualityPage";
import { UtilityPlaceholderPage } from "./pages/UtilityPlaceholderPage";
import {
  APP_FALLBACK_VERSION,
  authBootstrapCreateAdmin,
  authBootstrapStatus,
  authLogin,
  authLogout,
  authSession,
  getAppVersion,
  healthCheck,
} from "./tauri";
import { AuthBootstrapStatusResponse, SessionUser, UserRole, ViewKey } from "./types";

type NavEntry = {
  key: ViewKey;
  label: string;
  icon: IconName;
  hint: string;
};

const primaryEntries: NavEntry[] = [
  {
    key: "quick-sale",
    label: "Venta rapida",
    icon: "sale",
    hint: "POS con scanner",
  },
  {
    key: "quick-stock",
    label: "Agregar stock",
    icon: "stock",
    hint: "Reposicion express",
  },
];

const utilityEntries: NavEntry[] = [
  { key: "dashboard", label: "Dashboard", icon: "dashboard", hint: "KPIs" },
  { key: "products", label: "Productos", icon: "products", hint: "ABM" },
  { key: "categories", label: "Categorias", icon: "categories", hint: "Margenes" },
  { key: "inventory", label: "Inventario", icon: "inventory", hint: "Movimientos" },
  { key: "reports", label: "Reportes", icon: "reports", hint: "Metricas" },
  { key: "customers", label: "Clientes", icon: "customers", hint: "Deudas" },
  { key: "users", label: "Usuarios", icon: "users", hint: "Permisos" },
  { key: "tickets", label: "Tickets", icon: "tickets", hint: "Plantilla e impresion" },
  { key: "backup", label: "Respaldo", icon: "backup", hint: "Restore" },
  { key: "quality", label: "Calidad", icon: "quality", hint: "Auditoria de datos" },
];

const utilityKeySet = new Set<ViewKey>(utilityEntries.map((entry) => entry.key));

function isUtilitySection(value: ViewKey): boolean {
  return utilityKeySet.has(value);
}

function resolveRole(rawRole: string): UserRole {
  return rawRole === "admin" ? "admin" : "seller";
}

function canAccessSection(role: UserRole | null, section: ViewKey): boolean {
  if (section === "quick-sale") {
    return true;
  }
  return role === "admin";
}

function toErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  return "No se pudo completar la operacion";
}

export default function App() {
  const [activeSection, setActiveSection] = useState<ViewKey>("quick-sale");
  const [utilitiesOpen, setUtilitiesOpen] = useState(false);
  const [backendStatus, setBackendStatus] = useState("Conectando backend...");
  const [appVersion, setAppVersion] = useState(APP_FALLBACK_VERSION);
  const [sessionUser, setSessionUser] = useState<SessionUser | null>(null);
  const [loadingSession, setLoadingSession] = useState(true);
  const [bootstrapStatus, setBootstrapStatus] = useState<AuthBootstrapStatusResponse | null>(null);
  const [loginSubmitting, setLoginSubmitting] = useState(false);
  const [logoutSubmitting, setLogoutSubmitting] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const role = sessionUser ? resolveRole(String(sessionUser.role)) : null;
  const isAdmin = role === "admin";
  const availablePrimaryEntries = useMemo(
    () => (isAdmin ? primaryEntries : primaryEntries.filter((entry) => entry.key === "quick-sale")),
    [isAdmin],
  );
  const availableUtilityEntries = useMemo(
    () => (isAdmin ? utilityEntries : []),
    [isAdmin],
  );

  useEffect(() => {
    let mounted = true;
    healthCheck().then((result) => {
      if (!mounted) {
        return;
      }
      if (result === "ok") {
        setBackendStatus("Backend Rust activo");
      } else {
        setBackendStatus("Vista web (sin runtime Tauri)");
      }
    });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    getAppVersion().then((version) => {
      if (!mounted) {
        return;
      }
      setAppVersion(version);
    });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (isAdmin && isUtilitySection(activeSection)) {
      setUtilitiesOpen(true);
    }
  }, [activeSection, isAdmin]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const [response, bootstrap] = await Promise.all([
          authSession(),
          authBootstrapStatus().catch(() => ({ needsSetup: false, usersCount: 0 })),
        ]);
        if (!mounted) {
          return;
        }
        setBootstrapStatus(bootstrap);
        if (response.authenticated && response.user) {
          setSessionUser(response.user);
        }
      } catch {
        if (!mounted) {
          return;
        }
        setSessionUser(null);
        setBootstrapStatus({ needsSetup: false, usersCount: 0 });
      } finally {
        if (mounted) {
          setLoadingSession(false);
        }
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (role === "admin") {
      return;
    }
    setUtilitiesOpen(false);
    if (!canAccessSection(role, activeSection)) {
      setActiveSection("quick-sale");
    }
  }, [activeSection, role]);

  async function handleLogin(username: string, password: string) {
    setAuthError(null);
    setLoginSubmitting(true);
    try {
      if (bootstrapStatus?.needsSetup) {
        throw new Error("Completa primero la configuracion inicial del administrador.");
      }
      const response = await authLogin({ username, password });
      if (!response.authenticated || !response.user) {
        throw new Error("No se pudo iniciar sesion.");
      }
      setSessionUser(response.user);
      setActiveSection("quick-sale");
      setUtilitiesOpen(false);
    } catch (error) {
      setAuthError(toErrorMessage(error));
    } finally {
      setLoginSubmitting(false);
    }
  }

  async function handleBootstrapCreateAdmin(username: string, displayName: string, password: string) {
    setAuthError(null);
    setLoginSubmitting(true);
    try {
      const response = await authBootstrapCreateAdmin({
        username,
        displayName,
        password,
      });
      if (!response.authenticated || !response.user) {
        throw new Error("No se pudo crear el usuario administrador inicial.");
      }
      setSessionUser(response.user);
      setBootstrapStatus({ needsSetup: false, usersCount: 1 });
      setActiveSection("quick-sale");
      setUtilitiesOpen(false);
    } catch (error) {
      setAuthError(toErrorMessage(error));
    } finally {
      setLoginSubmitting(false);
    }
  }

  async function handleLogout() {
    setLogoutSubmitting(true);
    try {
      await authLogout();
    } catch {
      // Se limpia sesion local aunque falle el comando.
    } finally {
      setSessionUser(null);
      setActiveSection("quick-sale");
      setUtilitiesOpen(false);
      setAuthError(null);
      setLogoutSubmitting(false);
    }
  }

  function navigate(nextSection: ViewKey) {
    if (!canAccessSection(role, nextSection)) {
      return;
    }
    setActiveSection(nextSection);
  }

  const activeMeta = useMemo(() => {
    const entries = [...availablePrimaryEntries, ...availableUtilityEntries];
    return entries.find((entry) => entry.key === activeSection) ?? primaryEntries[0];
  }, [activeSection, availablePrimaryEntries, availableUtilityEntries]);

  const activeView = useMemo(() => {
    if (!canAccessSection(role, activeSection)) {
      return <QuickSalePage />;
    }

    if (activeSection === "quick-sale") {
      return <QuickSalePage />;
    }

    if (activeSection === "quick-stock") {
      return <QuickStockPage />;
    }

    if (activeSection === "dashboard") {
      return <DashboardPage />;
    }

    if (activeSection === "customers") {
      return <CustomersPage />;
    }

    if (activeSection === "reports") {
      return <ReportsPage />;
    }

    if (activeSection === "products") {
      return <ProductsPage />;
    }

    if (activeSection === "categories") {
      return <CategoriesPage />;
    }

    if (activeSection === "inventory") {
      return <InventoryPage />;
    }

    if (activeSection === "users") {
      return <UsersPage />;
    }

    if (activeSection === "backup") {
      return <BackupPage />;
    }

    if (activeSection === "tickets") {
      return <TicketsPage />;
    }

    if (activeSection === "quality") {
      return <QualityPage />;
    }

    return <UtilityPlaceholderPage section={activeSection} />;
  }, [activeSection, role]);

  if (!sessionUser || loadingSession) {
    return (
      <LoginPage
        backendStatus={backendStatus}
        appVersion={appVersion}
        loadingSession={loadingSession}
        submitting={loginSubmitting}
        error={authError}
        bootstrapNeedsSetup={Boolean(bootstrapStatus?.needsSetup)}
        onSubmit={handleLogin}
        onBootstrapCreate={handleBootstrapCreateAdmin}
      />
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-icon">
            <Icon name="spark" size={18} />
          </div>
          <div>
            <h1>BUEN TRAGO</h1>
            <p>Desktop local offline</p>
          </div>
        </div>

        <div className="operator-card">
          <span className="operator-label">Sesion</span>
          <strong>{sessionUser.displayName}</strong>
          <small>{isAdmin ? "Acceso completo (admin)" : "Solo venta rapida (seller)"}</small>
          <button
            type="button"
            className="button-soft button-xs operator-logout"
            onClick={() => void handleLogout()}
            disabled={logoutSubmitting}
          >
            {logoutSubmitting ? "Cerrando..." : "Cerrar sesion"}
          </button>
        </div>

        <nav className="nav-stack">
          <span className="stack-title">Operacion</span>
          {availablePrimaryEntries.map((entry) => (
            <button
              type="button"
              key={entry.key}
              className={`nav-button ${activeSection === entry.key ? "active" : ""}`}
              onClick={() => navigate(entry.key)}
            >
              <Icon name={entry.icon} size={16} />
              <span className="nav-copy">
                <strong>{entry.label}</strong>
                <small>{entry.hint}</small>
              </span>
            </button>
          ))}

          {isAdmin && (
            <>
              <button
                type="button"
                className={`nav-button group-toggle ${utilitiesOpen ? "open" : ""}`}
                onClick={() => setUtilitiesOpen((value) => !value)}
              >
                <Icon name="utilities" size={16} />
                <span className="nav-copy">
                  <strong>Utilidades</strong>
                  <small>Modulos administrativos</small>
                </span>
                <Icon
                  name={utilitiesOpen ? "chevron-down" : "chevron-right"}
                  size={14}
                  className="tail-icon"
                />
              </button>

              <div className={`utility-list ${utilitiesOpen ? "open" : ""}`}>
                {availableUtilityEntries.map((entry) => (
                  <button
                    type="button"
                    key={entry.key}
                    className={`nav-button utility ${activeSection === entry.key ? "active" : ""}`}
                    onClick={() => navigate(entry.key)}
                  >
                    <Icon name={entry.icon} size={14} />
                    <span className="nav-copy">
                      <strong>{entry.label}</strong>
                      <small>{entry.hint}</small>
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}
        </nav>

        <footer className="sidebar-footer">{`Version ${appVersion} | Python -> Tauri + React + Rust`}</footer>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h2>{activeMeta.label}</h2>
            <p>{activeMeta.hint}. Interfaz moderna, foco en velocidad de caja.</p>
          </div>
          <div className="topbar-actions">
            {!isAdmin && <span className="status-badge">Modo vendedor</span>}
            <span className="status-badge">{backendStatus}</span>
            <span className="status-badge">{`v${appVersion}`}</span>
          </div>
        </header>

        <div className="view-host">
          <div key={activeSection} className="view-anim">
            {activeView}
          </div>
        </div>
      </section>
    </div>
  );
}
