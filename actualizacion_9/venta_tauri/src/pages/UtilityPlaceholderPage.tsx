import { ViewKey } from "../types";

type UtilityPlaceholderPageProps = {
  section: ViewKey;
};

const copyMap: Record<string, { title: string; text: string }> = {
  dashboard: {
    title: "Dashboard financiero",
    text: "Graficos de ventas del mes, utilidad diaria y top productos.",
  },
  products: {
    title: "Productos",
    text: "ABM completo de productos, costo y precio por margen automatico.",
  },
  categories: {
    title: "Categorias y margenes",
    text: "Configurable por usuario admin sin tocar codigo.",
  },
  inventory: {
    title: "Inventario y movimientos",
    text: "Entradas, salidas y ajustes con trazabilidad historica.",
  },
  reports: {
    title: "Reportes",
    text: "Resumen mensual, productos mas vendidos y metodos de pago.",
  },
  customers: {
    title: "Clientes y deudas",
    text: "Cuenta corriente, pagos parciales y alertas por limite.",
  },
  users: {
    title: "Usuarios",
    text: "Roles admin/vendedor y permisos por seccion.",
  },
  backup: {
    title: "Respaldo",
    text: "Exportacion y restauracion local de datos.",
  },
};

export function UtilityPlaceholderPage({ section }: UtilityPlaceholderPageProps) {
  const sectionCopy = copyMap[section] ?? {
    title: "Utilidad",
    text: "Modulo en migracion a la nueva arquitectura.",
  };

  return (
    <section className="panel utility-panel">
      <h2>{sectionCopy.title}</h2>
      <p>{sectionCopy.text}</p>
      <div className="utility-placeholder-grid">
        <article>
          <h4>Estado</h4>
          <p>Diseno y estructura listos para conectar backend Rust + SQLite.</p>
        </article>
        <article>
          <h4>Proximo paso</h4>
          <p>Conectar comandos Tauri y consultas reales por modulo.</p>
        </article>
      </div>
    </section>
  );
}
