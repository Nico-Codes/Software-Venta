import { useEffect, useState } from "react";

import {
  backupConfig,
  backupStatus,
  createBackup,
  listBackupFiles,
  restoreBackup,
  runBackupMaintenance,
  updateBackupConfig,
  verifyBackupFile,
} from "../tauri";
import {
  BackupConfigResponse,
  BackupFileInfo,
  BackupMaintenanceResponse,
  BackupStatusResponse,
} from "../types";

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

function formatDateTime(value: string | null): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(parsed);
}

function formatBytes(value: number): string {
  if (value <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  let current = value;
  let unitIndex = 0;
  while (current >= 1024 && unitIndex < units.length - 1) {
    current /= 1024;
    unitIndex += 1;
  }
  return `${current.toFixed(unitIndex === 0 ? 0 : 2)} ${units[unitIndex]}`;
}

export function BackupPage() {
  const [status, setStatus] = useState<BackupStatusResponse | null>(null);
  const [config, setConfig] = useState<BackupConfigResponse | null>(null);
  const [files, setFiles] = useState<BackupFileInfo[]>([]);
  const [targetPathInput, setTargetPathInput] = useState("");
  const [sourcePathInput, setSourcePathInput] = useState("");
  const [verifyPathInput, setVerifyPathInput] = useState("");
  const [configDraft, setConfigDraft] = useState({
    autoEnabled: true,
    intervalHours: "24",
    retentionCount: "60",
  });
  const [maintenanceInfo, setMaintenanceInfo] = useState<BackupMaintenanceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [savingConfig, setSavingConfig] = useState(false);
  const [runningMaintenance, setRunningMaintenance] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);

  function syncConfigDraft(nextConfig: BackupConfigResponse) {
    setConfigDraft({
      autoEnabled: nextConfig.autoEnabled,
      intervalHours: String(nextConfig.intervalHours),
      retentionCount: String(nextConfig.retentionCount),
    });
  }

  function parseStrictInt(raw: string): number | null {
    const parsed = Number.parseInt(raw.trim(), 10);
    if (!Number.isFinite(parsed)) {
      return null;
    }
    return parsed;
  }

  async function refreshData() {
    setLoading(true);
    try {
      const [statusResult, filesResult, configResult] = await Promise.all([
        backupStatus(),
        listBackupFiles(200),
        backupConfig(),
      ]);
      setStatus(statusResult);
      setFiles(filesResult);
      setConfig(configResult);
      syncConfigDraft(configResult);
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshData();
  }, []);

  async function handleCreateAuto() {
    setCreating(true);
    try {
      const created = await createBackup();
      setNotice({ tone: "ok", text: `Backup creado en ${created.backupPath}` });
      await refreshData();
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setCreating(false);
    }
  }

  async function handleCreateWithPath() {
    const path = targetPathInput.trim();
    if (!path) {
      setNotice({ tone: "error", text: "Ingresa ruta destino para backup." });
      return;
    }
    setCreating(true);
    try {
      const created = await createBackup(path);
      setNotice({ tone: "ok", text: `Backup exportado en ${created.backupPath}` });
      await refreshData();
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setCreating(false);
    }
  }

  async function handleRestore(path: string) {
    const cleanPath = path.trim();
    if (!cleanPath) {
      setNotice({ tone: "error", text: "Ingresa ruta de backup para restaurar." });
      return;
    }
    if (!window.confirm(`Restaurar backup desde:\n${cleanPath}\n\nEsta accion reemplaza la base actual.`)) {
      return;
    }

    setRestoring(true);
    try {
      const result = await restoreBackup(cleanPath);
      const extra = result.preRestoreBackupPath
        ? ` Backup previo en ${result.preRestoreBackupPath}.`
        : "";
      setNotice({ tone: "ok", text: `${result.message}.${extra}` });
      await refreshData();
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setRestoring(false);
    }
  }

  async function handleSaveConfig() {
    const intervalHours = parseStrictInt(configDraft.intervalHours);
    const retentionCount = parseStrictInt(configDraft.retentionCount);
    if (intervalHours === null || intervalHours < 1) {
      setNotice({ tone: "error", text: "El intervalo automatico debe ser >= 1 hora." });
      return;
    }
    if (intervalHours > 168) {
      setNotice({ tone: "error", text: "El intervalo automatico no puede superar 168 horas." });
      return;
    }
    if (retentionCount === null || retentionCount < 3) {
      setNotice({ tone: "error", text: "La retencion debe ser >= 3 archivos." });
      return;
    }
    if (retentionCount > 400) {
      setNotice({ tone: "error", text: "La retencion no puede superar 400 backups." });
      return;
    }

    setSavingConfig(true);
    try {
      const updated = await updateBackupConfig({
        autoEnabled: configDraft.autoEnabled,
        intervalHours,
        retentionCount,
      });
      setConfig(updated);
      syncConfigDraft(updated);
      setNotice({ tone: "ok", text: "Configuracion de backup actualizada." });
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setSavingConfig(false);
    }
  }

  async function handleMaintenance(force: boolean) {
    setRunningMaintenance(true);
    try {
      const result = await runBackupMaintenance(force);
      setMaintenanceInfo(result);
      const summary = result.createdBackupPath
        ? `Mantenimiento ejecutado. Backup: ${result.createdBackupPath}`
        : result.skippedReason
          ? `Mantenimiento omitido: ${result.skippedReason}`
          : "Mantenimiento ejecutado sin crear backup.";
      setNotice({ tone: "info", text: summary });
      await refreshData();
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setRunningMaintenance(false);
    }
  }

  async function handleVerify(path: string) {
    const clean = path.trim();
    if (!clean) {
      setNotice({ tone: "error", text: "Ingresa una ruta de backup para verificar." });
      return;
    }
    setVerifying(true);
    try {
      const result = await verifyBackupFile(clean);
      setNotice({
        tone: result.ok ? "ok" : "error",
        text: result.ok ? `Backup valido: ${result.path}` : `Backup invalido: ${result.message}`,
      });
    } catch (error) {
      setNotice({ tone: "error", text: toErrorMessage(error) });
    } finally {
      setVerifying(false);
    }
  }

  return (
    <section className="backup-grid">
      <section className="panel backup-status-panel">
        <header className="section-head">
          <h2>Respaldo</h2>
          <p>Exporta y restaura la base local de forma segura.</p>
        </header>

        {notice && (
          <div className={`notice-strip notice-${notice.tone}`}>
            <span>{notice.text}</span>
          </div>
        )}

        <div className="backup-status-cards">
          <article>
            <span>Base de datos</span>
            <strong>{status?.dbPath ?? "-"}</strong>
            <small>Tamano: {status ? formatBytes(status.dbSizeBytes) : "-"}</small>
            <small>Modificado: {formatDateTime(status?.dbModifiedAt ?? null)}</small>
          </article>
          <article>
            <span>Carpeta de backups</span>
            <strong>{status?.backupDir ?? "-"}</strong>
            <small>Archivos listados: {files.length}</small>
            <small>Ultima corrida auto: {formatDateTime(config?.lastRunAt ?? null)}</small>
          </article>
        </div>

        <div className="backup-config-box">
          <h3>Automatizacion</h3>
          <div className="backup-config-grid">
            <label className="switch-row">
              <input
                type="checkbox"
                checked={configDraft.autoEnabled}
                onChange={(event) =>
                  setConfigDraft((current) => ({
                    ...current,
                    autoEnabled: event.target.checked,
                  }))
                }
              />
              <span>Crear backup automatico</span>
            </label>
            <label className="field">
              <span>Intervalo (horas)</span>
              <input
                type="number"
                min={1}
                max={168}
                value={configDraft.intervalHours}
                onChange={(event) =>
                  setConfigDraft((current) => ({
                    ...current,
                    intervalHours: event.target.value,
                  }))
                }
              />
            </label>
            <label className="field">
              <span>Retencion (archivos)</span>
              <input
                type="number"
                min={3}
                max={400}
                value={configDraft.retentionCount}
                onChange={(event) =>
                  setConfigDraft((current) => ({
                    ...current,
                    retentionCount: event.target.value,
                  }))
                }
              />
            </label>
            <button
              type="button"
              className="button-soft"
              onClick={handleSaveConfig}
              disabled={savingConfig || loading || creating || restoring}
            >
              {savingConfig ? "Guardando..." : "Guardar config"}
            </button>
          </div>
        </div>

        <div className="backup-actions">
          <button type="button" onClick={handleCreateAuto} disabled={creating || restoring || loading}>
            {creating ? "Creando..." : "Crear backup automatico"}
          </button>
          <button
            type="button"
            className="button-soft"
            onClick={() => void handleMaintenance(false)}
            disabled={runningMaintenance || loading || creating || restoring}
          >
            {runningMaintenance ? "Procesando..." : "Mantenimiento auto"}
          </button>
          <button
            type="button"
            className="button-soft"
            onClick={() => void handleMaintenance(true)}
            disabled={runningMaintenance || loading || creating || restoring}
          >
            Forzar mantenimiento
          </button>
          <button
            type="button"
            className="button-soft"
            onClick={() => void refreshData()}
            disabled={loading || creating || restoring || runningMaintenance}
          >
            {loading ? "Actualizando..." : "Refrescar"}
          </button>
        </div>

        <div className="backup-manual-box">
          <h3>Backup manual</h3>
          <div className="backup-manual-grid">
            <label className="field">
              <span>Ruta destino (.db)</span>
              <input
                value={targetPathInput}
                onChange={(event) => setTargetPathInput(event.target.value)}
                placeholder="C:\\Respaldos\\venta_backup.db"
              />
            </label>
            <button
              type="button"
              onClick={handleCreateWithPath}
              disabled={creating || restoring || loading}
            >
              Exportar backup
            </button>
          </div>
        </div>

        <div className="backup-manual-box">
          <h3>Verificar backup</h3>
          <div className="backup-manual-grid">
            <label className="field">
              <span>Ruta backup (.db)</span>
              <input
                value={verifyPathInput}
                onChange={(event) => setVerifyPathInput(event.target.value)}
                placeholder="C:\\Respaldos\\venta_backup.db"
              />
            </label>
            <button
              type="button"
              className="button-soft"
              onClick={() => void handleVerify(verifyPathInput)}
              disabled={verifying || creating || restoring || loading}
            >
              {verifying ? "Verificando..." : "Verificar"}
            </button>
          </div>
        </div>

        <div className="backup-manual-box">
          <h3>Restaurar desde ruta</h3>
          <div className="backup-manual-grid">
            <label className="field">
              <span>Archivo backup (.db)</span>
              <input
                value={sourcePathInput}
                onChange={(event) => setSourcePathInput(event.target.value)}
                placeholder="C:\\Respaldos\\venta_backup.db"
              />
            </label>
            <button
              type="button"
              className="button-soft"
              onClick={() => void handleRestore(sourcePathInput)}
              disabled={restoring || creating || loading || runningMaintenance}
            >
              {restoring ? "Restaurando..." : "Restaurar"}
            </button>
          </div>
        </div>

        {maintenanceInfo && (
          <div className="backup-maintenance-result">
            <strong>Ultimo mantenimiento</strong>
            <small>Fecha: {formatDateTime(maintenanceInfo.executedAt)}</small>
            <small>Backup creado: {maintenanceInfo.createdBackupPath ?? "-"}</small>
            <small>Eliminados: {maintenanceInfo.deletedFiles.length}</small>
            {maintenanceInfo.skippedReason && <small>Motivo: {maintenanceInfo.skippedReason}</small>}
          </div>
        )}
      </section>

      <section className="panel backup-files-panel">
        <header className="section-head">
          <h2>Backups detectados</h2>
          <p>Puedes restaurar cualquiera de los respaldos listados.</p>
        </header>

        <div className="backup-file-list">
          {files.length <= 0 ? (
            <p className="empty-copy">No se encontraron backups en la carpeta configurada.</p>
          ) : (
            files.map((file) => (
              <article key={file.path}>
                <div>
                  <strong>{file.fileName}</strong>
                  <small>{file.path}</small>
                  <small>
                    {formatBytes(file.sizeBytes)} | {formatDateTime(file.modifiedAt)}
                  </small>
                </div>
                <div className="backup-file-actions">
                  <button
                    type="button"
                    className="button-soft button-xs"
                    onClick={() => void handleVerify(file.path)}
                    disabled={verifying || restoring || creating || loading}
                  >
                    Verificar
                  </button>
                  <button
                    type="button"
                    className="button-soft button-xs"
                    onClick={() => void handleRestore(file.path)}
                    disabled={restoring || creating || loading}
                  >
                    Restaurar
                  </button>
                </div>
              </article>
            ))
          )}
        </div>
      </section>
    </section>
  );
}
