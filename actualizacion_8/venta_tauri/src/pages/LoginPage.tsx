import { FormEvent, useMemo, useState } from "react";

import { Icon } from "../components/Icon";

type LoginPageProps = {
  backendStatus: string;
  loadingSession: boolean;
  submitting: boolean;
  error: string | null;
  bootstrapNeedsSetup: boolean;
  onSubmit: (username: string, password: string) => Promise<void>;
  onBootstrapCreate: (username: string, displayName: string, password: string) => Promise<void>;
};

export function LoginPage({
  backendStatus,
  loadingSession,
  submitting,
  error,
  bootstrapNeedsSetup,
  onSubmit,
  onBootstrapCreate,
}: LoginPageProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const [setupUsername, setSetupUsername] = useState("");
  const [setupDisplayName, setSetupDisplayName] = useState("");
  const [setupPassword, setSetupPassword] = useState("");
  const [setupPasswordRepeat, setSetupPasswordRepeat] = useState("");
  const [setupError, setSetupError] = useState<string | null>(null);

  const actionLabel = useMemo(() => {
    if (loadingSession) {
      return "Cargando...";
    }
    if (submitting) {
      return bootstrapNeedsSetup ? "Creando admin..." : "Ingresando...";
    }
    return bootstrapNeedsSetup ? "Crear administrador" : "Ingresar";
  }, [bootstrapNeedsSetup, loadingSession, submitting]);

  async function handleLoginSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit(username, password);
  }

  async function handleBootstrapSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSetupError(null);

    const cleanUsername = setupUsername.trim();
    const cleanDisplay = setupDisplayName.trim();
    if (!cleanUsername || !cleanDisplay || !setupPassword.trim()) {
      setSetupError("Completa todos los campos para crear el administrador.");
      return;
    }
    if (setupPassword.trim().length < 6) {
      setSetupError("La clave debe tener al menos 6 caracteres.");
      return;
    }
    if (setupPassword !== setupPasswordRepeat) {
      setSetupError("Las claves no coinciden.");
      return;
    }

    await onBootstrapCreate(cleanUsername, cleanDisplay, setupPassword);
  }

  return (
    <div className="login-shell">
      <section className="login-card">
        <header className="login-header">
          <div className="login-logo">
            <Icon name="spark" size={18} />
          </div>
          <div>
            <h1>ALTO TRAGO</h1>
            <p>{bootstrapNeedsSetup ? "Configuracion inicial segura" : "Ingreso seguro por usuario y rol."}</p>
          </div>
        </header>

        {bootstrapNeedsSetup ? (
          <form className="login-form" onSubmit={(event) => void handleBootstrapSubmit(event)}>
            <label className="field">
              <span>Usuario administrador</span>
              <input
                value={setupUsername}
                onChange={(event) => setSetupUsername(event.target.value)}
                placeholder="Usuario"
                autoComplete="username"
                disabled={loadingSession || submitting}
              />
            </label>

            <label className="field">
              <span>Nombre visible</span>
              <input
                value={setupDisplayName}
                onChange={(event) => setSetupDisplayName(event.target.value)}
                placeholder="Nombre del operador"
                autoComplete="name"
                disabled={loadingSession || submitting}
              />
            </label>

            <label className="field">
              <span>Clave inicial</span>
              <input
                type="password"
                value={setupPassword}
                onChange={(event) => setSetupPassword(event.target.value)}
                placeholder="Minimo 6 caracteres"
                autoComplete="new-password"
                disabled={loadingSession || submitting}
              />
            </label>

            <label className="field">
              <span>Repetir clave</span>
              <input
                type="password"
                value={setupPasswordRepeat}
                onChange={(event) => setSetupPasswordRepeat(event.target.value)}
                placeholder="Repetir clave"
                autoComplete="new-password"
                disabled={loadingSession || submitting}
              />
            </label>

            {setupError && <div className="notice-strip notice-error">{setupError}</div>}
            {error && <div className="notice-strip notice-error">{error}</div>}

            <button type="submit" disabled={loadingSession || submitting}>
              {actionLabel}
            </button>
          </form>
        ) : (
          <form className="login-form" onSubmit={(event) => void handleLoginSubmit(event)}>
            <label className="field">
              <span>Usuario</span>
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="Ingresa tu usuario"
                autoComplete="username"
                disabled={loadingSession || submitting}
              />
            </label>

            <label className="field">
              <span>Clave</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Ingresa tu clave"
                autoComplete="current-password"
                disabled={loadingSession || submitting}
              />
            </label>

            {error && <div className="notice-strip notice-error">{error}</div>}

            <button type="submit" disabled={loadingSession || submitting}>
              {actionLabel}
            </button>
          </form>
        )}

        <footer className="login-footer">
          <span>{backendStatus}</span>
          <small>{bootstrapNeedsSetup ? "Primera ejecucion: define el admin inicial." : "Acceso restringido a usuarios habilitados."}</small>
        </footer>
      </section>
    </div>
  );
}
