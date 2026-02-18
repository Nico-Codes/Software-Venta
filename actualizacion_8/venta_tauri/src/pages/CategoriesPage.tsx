import { useEffect, useState } from "react";

import {
  createCategory,
  deleteCategory,
  listCategoriesAdmin,
  updateCategory,
} from "../tauri";
import { CategoryAdminSummary } from "../types";

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
  return "No se pudo completar la operacion";
}

function parseDecimal(raw: string): number {
  const parsed = Number.parseFloat(raw.replace(",", "."));
  if (!Number.isFinite(parsed)) {
    return 0;
  }
  return parsed;
}

export function CategoriesPage() {
  const [categories, setCategories] = useState<CategoryAdminSummary[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [nameInput, setNameInput] = useState("");
  const [marginInput, setMarginInput] = useState("30");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);

  function syncFormFromCategory(target: CategoryAdminSummary | null) {
    if (!target) {
      setNameInput("");
      setMarginInput("30");
      return;
    }
    setNameInput(target.name);
    setMarginInput(target.marginPercent.toFixed(2));
  }

  async function reloadCategories(preferId?: string) {
    setLoading(true);
    try {
      const rows = await listCategoriesAdmin();
      setCategories(rows);

      const requested = preferId ?? selectedId;
      const found =
        rows.find((category) => String(category.id) === requested) ?? rows[0] ?? null;
      if (found) {
        setSelectedId(String(found.id));
        syncFormFromCategory(found);
      } else {
        setSelectedId("");
        syncFormFromCategory(null);
      }
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
      setCategories([]);
      setSelectedId("");
      syncFormFromCategory(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reloadCategories();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedCategory =
    categories.find((category) => String(category.id) === selectedId) ?? null;

  async function handleSave() {
    const cleanName = nameInput.trim();
    const margin = parseDecimal(marginInput);
    if (!cleanName) {
      setNotice({ tone: "error", text: "Ingresa nombre de categoria." });
      return;
    }
    if (margin < 0) {
      setNotice({ tone: "error", text: "El margen no puede ser negativo." });
      return;
    }

    setSaving(true);
    try {
      if (!selectedId) {
        const created = await createCategory({
          name: cleanName,
          marginPercent: margin,
        });
        setNotice({ tone: "ok", text: `Categoria ${created.name} creada.` });
        await reloadCategories(String(created.id));
      } else {
        const updated = await updateCategory({
          id: Number.parseInt(selectedId, 10),
          name: cleanName,
          marginPercent: margin,
        });
        setNotice({
          tone: "ok",
          text: `Categoria ${updated.name} actualizada. Precios automaticos recalculados.`,
        });
        await reloadCategories(String(updated.id));
      }
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!selectedCategory) {
      return;
    }
    setDeleting(true);
    try {
      await deleteCategory(selectedCategory.id);
      setNotice({ tone: "ok", text: `Categoria ${selectedCategory.name} eliminada.` });
      setSelectedId("");
      syncFormFromCategory(null);
      await reloadCategories();
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setDeleting(false);
    }
  }

  return (
    <section className="categories-grid">
      <aside className="panel categories-list-panel">
        <header className="section-head">
          <h2>Categorias y margenes</h2>
          <p>Editar margen actualiza precios automaticos sin tocar codigo.</p>
        </header>

        {notice && (
          <div className={`notice-strip notice-${notice.tone}`}>
            <span>{notice.text}</span>
          </div>
        )}

        <div className="categories-action-row">
          <button
            type="button"
            className="button-soft"
            onClick={() => {
              setSelectedId("");
              syncFormFromCategory(null);
            }}
          >
            Nueva categoria
          </button>
          <button type="button" onClick={() => void reloadCategories()} disabled={loading}>
            {loading ? "Actualizando..." : "Refrescar"}
          </button>
        </div>

        <div className="categories-list">
          {categories.length <= 0 ? (
            <p className="empty-copy">No hay categorias cargadas.</p>
          ) : (
            categories.map((category) => (
              <button
                key={category.id}
                type="button"
                className={`category-row ${String(category.id) === selectedId ? "active" : ""}`}
                onClick={() => {
                  setSelectedId(String(category.id));
                  syncFormFromCategory(category);
                }}
              >
                <span className="row-main">
                  <strong>{category.name}</strong>
                  <small>{category.marginPercent.toFixed(2)}%</small>
                </span>
                <span className="row-badge">{category.productCount} productos</span>
              </button>
            ))
          )}
        </div>
      </aside>

      <section className="panel categories-editor-panel">
        <header className="section-head">
          <h2>{selectedId ? "Editar categoria" : "Crear categoria"}</h2>
          <p>Margen aplicado a productos con precio automatico.</p>
        </header>

        <div className="category-editor-form">
          <label className="field">
            <span>Nombre</span>
            <input value={nameInput} onChange={(event) => setNameInput(event.target.value)} />
          </label>

          <label className="field">
            <span>Margen %</span>
            <input
              type="number"
              min={0}
              step="0.01"
              value={marginInput}
              onChange={(event) => setMarginInput(event.target.value)}
            />
          </label>

          <div className="categories-editor-actions">
            <button type="button" onClick={handleSave} disabled={saving}>
              {saving ? "Guardando..." : selectedId ? "Actualizar" : "Crear"}
            </button>
            <button
              type="button"
              className="button-soft"
              onClick={handleDelete}
              disabled={!selectedId || deleting}
            >
              {deleting ? "Eliminando..." : "Eliminar"}
            </button>
          </div>
        </div>
      </section>
    </section>
  );
}
