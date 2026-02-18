import { useEffect, useState } from "react";

import { createUser, deleteUser, listUsers, updateUser } from "../tauri";
import { UserRole, UserRow } from "../types";

type Notice = {
  tone: "ok" | "error" | "info";
  text: string;
};

type UserFormState = {
  username: string;
  displayName: string;
  role: UserRole;
  active: boolean;
  password: string;
};

const EMPTY_FORM: UserFormState = {
  username: "",
  displayName: "",
  role: "seller",
  active: true,
  password: "",
};

const roleLabel: Record<string, string> = {
  admin: "Admin",
  seller: "Vendedor",
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

function mapUserToForm(user: UserRow): UserFormState {
  return {
    username: user.username,
    displayName: user.displayName,
    role: user.role === "admin" ? "admin" : "seller",
    active: user.active,
    password: "",
  };
}

export function UsersPage() {
  const [users, setUsers] = useState<UserRow[]>([]);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [includeInactive, setIncludeInactive] = useState(true);
  const [form, setForm] = useState<UserFormState>(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);

  async function reloadUsers(preferUserId?: string) {
    setLoading(true);
    try {
      const rows = await listUsers(includeInactive);
      setUsers(rows);

      const selected =
        rows.find((row) => String(row.id) === (preferUserId ?? selectedUserId)) ?? null;
      if (selected) {
        setSelectedUserId(String(selected.id));
        setForm(mapUserToForm(selected));
      } else {
        setSelectedUserId("");
      }
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
      setUsers([]);
      setSelectedUserId("");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reloadUsers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeInactive]);

  const selectedUser = users.find((row) => String(row.id) === selectedUserId) ?? null;

  function handleNew() {
    setSelectedUserId("");
    setForm(EMPTY_FORM);
  }

  async function handleSave() {
    const cleanUsername = form.username.trim().toLowerCase();
    const cleanDisplayName = form.displayName.trim();
    if (!cleanUsername) {
      setNotice({ tone: "error", text: "Ingresa username." });
      return;
    }
    if (!cleanDisplayName) {
      setNotice({ tone: "error", text: "Ingresa nombre visible." });
      return;
    }
    if (!selectedUserId && !form.password.trim()) {
      setNotice({ tone: "error", text: "Ingresa clave para nuevo usuario." });
      return;
    }

    setSaving(true);
    try {
      if (!selectedUserId) {
        const created = await createUser({
          username: cleanUsername,
          displayName: cleanDisplayName,
          role: form.role,
          password: form.password.trim(),
          active: form.active,
        });
        setNotice({ tone: "ok", text: `Usuario ${created.username} creado.` });
        setForm((current) => ({ ...current, password: "" }));
        await reloadUsers(String(created.id));
      } else {
        const updated = await updateUser({
          id: Number.parseInt(selectedUserId, 10),
          username: cleanUsername,
          displayName: cleanDisplayName,
          role: form.role,
          password: form.password.trim() || undefined,
          active: form.active,
        });
        setNotice({ tone: "ok", text: `Usuario ${updated.username} actualizado.` });
        setForm((current) => ({ ...current, password: "" }));
        await reloadUsers(String(updated.id));
      }
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!selectedUser) {
      return;
    }
    if (!window.confirm(`Eliminar usuario ${selectedUser.username}?`)) {
      return;
    }

    setDeleting(true);
    try {
      await deleteUser(selectedUser.id);
      setNotice({ tone: "ok", text: `Usuario ${selectedUser.username} eliminado.` });
      handleNew();
      await reloadUsers();
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setDeleting(false);
    }
  }

  return (
    <section className="users-grid">
      <aside className="panel users-list-panel">
        <header className="section-head">
          <h2>Usuarios</h2>
          <p>Gestiona cuentas admin y vendedor para operar en caja.</p>
        </header>

        {notice && (
          <div className={`notice-strip notice-${notice.tone}`}>
            <span>{notice.text}</span>
          </div>
        )}

        <div className="users-toolbar">
          <label className="switch-row">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(event) => setIncludeInactive(event.target.checked)}
            />
            <span>Mostrar inactivos</span>
          </label>
          <button type="button" onClick={() => void reloadUsers()} disabled={loading}>
            {loading ? "Actualizando..." : "Refrescar"}
          </button>
          <button type="button" className="button-soft" onClick={handleNew}>
            Nuevo usuario
          </button>
        </div>

        <div className="users-list">
          {users.length <= 0 ? (
            <p className="empty-copy">No hay usuarios cargados.</p>
          ) : (
            users.map((user) => (
              <button
                key={user.id}
                type="button"
                className={`user-row ${String(user.id) === selectedUserId ? "active" : ""}`}
                onClick={() => {
                  setSelectedUserId(String(user.id));
                  setForm(mapUserToForm(user));
                }}
              >
                <span className="row-main">
                  <strong>{user.displayName}</strong>
                  <small>@{user.username}</small>
                </span>
                <span className={`row-badge ${user.active ? "" : "alert"}`}>
                  {roleLabel[user.role] ?? user.role} | {user.active ? "Activo" : "Inactivo"}
                </span>
              </button>
            ))
          )}
        </div>
      </aside>

      <section className="panel users-editor-panel">
        <header className="section-head">
          <h2>{selectedUser ? "Editar usuario" : "Crear usuario"}</h2>
          <p>Define rol, estado y clave de acceso.</p>
        </header>

        <div className="users-form">
          <label className="field">
            <span>Username</span>
            <input
              value={form.username}
              onChange={(event) =>
                setForm((prev) => ({ ...prev, username: event.target.value.toLowerCase() }))
              }
              placeholder="ej: admin"
            />
          </label>

          <label className="field">
            <span>Nombre visible</span>
            <input
              value={form.displayName}
              onChange={(event) => setForm((prev) => ({ ...prev, displayName: event.target.value }))}
              placeholder="ej: Administrador"
            />
          </label>

          <label className="field">
            <span>Rol</span>
            <div className="select-wrap">
              <select
                value={form.role}
                onChange={(event) => setForm((prev) => ({ ...prev, role: event.target.value as UserRole }))}
              >
                <option value="admin">Admin</option>
                <option value="seller">Vendedor</option>
              </select>
            </div>
          </label>

          <label className="switch-row">
            <input
              type="checkbox"
              checked={form.active}
              onChange={(event) => setForm((prev) => ({ ...prev, active: event.target.checked }))}
            />
            <span>Usuario activo</span>
          </label>

          <label className="field">
            <span>{selectedUser ? "Nueva clave (opcional)" : "Clave"}</span>
            <input
              type="password"
              value={form.password}
              onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
              placeholder={selectedUser ? "Dejar vacio para no cambiar" : "Ingresar clave"}
            />
          </label>

          <div className="users-actions">
            <button type="button" onClick={handleSave} disabled={saving}>
              {saving ? "Guardando..." : selectedUser ? "Actualizar usuario" : "Crear usuario"}
            </button>
            <button
              type="button"
              className="button-soft"
              onClick={handleDelete}
              disabled={!selectedUser || deleting}
            >
              {deleting ? "Eliminando..." : "Eliminar"}
            </button>
          </div>
        </div>
      </section>
    </section>
  );
}
