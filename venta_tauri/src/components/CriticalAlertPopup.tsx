import { useEffect, useId, useRef } from "react";

type CriticalAlertPopupProps = {
  open: boolean;
  title?: string;
  message: string;
  confirmLabel?: string;
  onClose: () => void;
};

export function CriticalAlertPopup({
  open,
  title = "Alerta critica",
  message,
  confirmLabel = "Entendido",
  onClose,
}: CriticalAlertPopupProps) {
  const titleId = useId();
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    closeButtonRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    function onWindowKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" || event.key === "Enter") {
        event.preventDefault();
        onClose();
      }
    }
    window.addEventListener("keydown", onWindowKeyDown);
    return () => {
      window.removeEventListener("keydown", onWindowKeyDown);
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="critical-popup-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div className="critical-popup" role="alertdialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="critical-popup-badge" aria-hidden="true">
          !
        </div>
        <div className="critical-popup-copy">
          <h3 id={titleId}>{title}</h3>
          <p>{message}</p>
        </div>
        <div className="critical-popup-actions">
          <button ref={closeButtonRef} type="button" className="button-soft" onClick={onClose}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
