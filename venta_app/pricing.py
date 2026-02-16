from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def round_to_nearest_base(value: float | Decimal, base: int = 100) -> float:
    if base <= 0:
        raise ValueError("La base de redondeo debe ser mayor a cero")

    value_decimal = Decimal(str(value))
    base_decimal = Decimal(str(base))
    rounded = (value_decimal / base_decimal).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * base_decimal
    return float(rounded)


def calculate_auto_price(cost: float, margin_percent: float, rounding_base: int = 100) -> float:
    if cost < 0:
        raise ValueError("El costo no puede ser negativo")

    raw_price = Decimal(str(cost)) * (Decimal("1") + Decimal(str(margin_percent)) / Decimal("100"))
    return round_to_nearest_base(raw_price, rounding_base)
