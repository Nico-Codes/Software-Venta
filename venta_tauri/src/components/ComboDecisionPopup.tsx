import { useEffect, useId, useRef } from "react";

import { ComboChoiceOption } from "../types";
import { formatInteger, formatMoney } from "../utils/number";

type ComboDecisionGroup = {
  signature: string;
  selectedComboId: number;
  suggestedComboId: number;
  options: ComboChoiceOption[];
};

type ComboDecisionPopupProps = {
  open: boolean;
  comboNames: string;
  discountAmount: number;
  groups: ComboDecisionGroup[];
  onSelectCombo: (signature: string, comboId: number) => void;
  onApply: () => void;
  onSkip: () => void;
};

export function ComboDecisionPopup({
  open,
  comboNames,
  discountAmount,
  groups,
  onSelectCombo,
  onApply,
  onSkip,
}: ComboDecisionPopupProps) {
  const titleId = useId();
  const applyButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    applyButtonRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    function onWindowKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onSkip();
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        onApply();
      }
    }
    window.addEventListener("keydown", onWindowKeyDown);
    return () => {
      window.removeEventListener("keydown", onWindowKeyDown);
    };
  }, [onApply, onSkip, open]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="combo-popup-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onSkip();
        }
      }}
    >
      <div className="combo-popup" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="combo-popup-header">
          <h3 id={titleId}>Combo detectado</h3>
          <p>{comboNames}</p>
          <small>{`Descuento estimado: ${formatMoney(discountAmount)}`}</small>
        </div>

        {groups.length > 0 && (
          <div className="combo-popup-groups">
            <p>Hay mas de un combo posible. Selecciona cual quiere el cliente:</p>
            {groups.map((group, groupIndex) => (
              <article key={group.signature} className="combo-popup-group">
                <strong>{`Conflicto ${groupIndex + 1}`}</strong>
                <div className="combo-popup-options">
                  {group.options.map((option) => (
                    <button
                      key={`${group.signature}-${option.comboId}`}
                      type="button"
                      className={`combo-popup-option ${group.selectedComboId === option.comboId ? "active" : ""}`}
                      onClick={() => onSelectCombo(group.signature, option.comboId)}
                    >
                      <span>{option.comboName}</span>
                      <small>
                        {`${formatInteger(option.requiredUnits)} unidades | ${formatInteger(
                          option.possibleApplications,
                        )} aplicacion(es) | ${formatInteger(option.discountPercent)}%`}
                      </small>
                      {option.comboId === group.suggestedComboId && <em>Sugerido</em>}
                    </button>
                  ))}
                </div>
              </article>
            ))}
          </div>
        )}

        <div className="combo-popup-actions">
          <button type="button" className="button-soft" onClick={onSkip}>
            No aplicar
          </button>
          <button ref={applyButtonRef} type="button" onClick={onApply}>
            Aplicar descuento
          </button>
        </div>
      </div>
    </div>
  );
}

