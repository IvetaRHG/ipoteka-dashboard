"""Быстрая проверка ядра калькулятора: python test_mortgage.py"""
from datetime import date

import pandas as pd

from mortgage import (
    METHOD_ANNUITY,
    METHOD_DIFFERENTIATED,
    annuity_payment,
    build_schedule,
    compare_schemes,
    yearly_summary,
)

# 1. Контрольный аннуитет: 1 000 000 ₽, 12% годовых, 12 месяцев
pmt = annuity_payment(1_000_000, 12.0, 12)
expected = 1_000_000 * 0.01 / (1 - 1.01 ** -12)  # эталонная формула
assert abs(pmt - expected) < 0.01, pmt

# 2. Нулевая ставка: платёж = тело / срок
assert abs(annuity_payment(1_200_000, 0.0, 12) - 100_000) < 1e-9

# 3. Аннуитет: сумма тела = сумма кредита, баланс обнуляется
res = build_schedule(5_000_000, 14.0, 240, METHOD_ANNUITY, date(2026, 1, 1))
assert abs(res.schedule["Основной долг"].sum() - 5_000_000) < 0.01
assert abs(res.schedule["Остаток долга"].iloc[-1]) < 0.01
assert len(res.schedule) == 240
assert pd.Timestamp(res.schedule["Дата"].iloc[0]) == pd.Timestamp(date(2026, 1, 1))
assert res.schedule["Дата"].iloc[-1].year == 2045

# 4. Дифференцированный: тело каждый месяц одинаковое
d = build_schedule(5_000_000, 14.0, 240, METHOD_DIFFERENTIATED, date(2026, 1, 1))
parts = d.schedule["Основной долг"].iloc[:-1]
assert (parts - parts.iloc[0]).abs().max() < 1e-6
assert abs(d.schedule["Основной долг"].sum() - 5_000_000) < 0.01
assert d.schedule["Платёж"].is_monotonic_decreasing
# Дифференцированный всегда дешевле по переплате
assert d.total_interest < res.total_interest

# 5. Годовая агрегация сходится с помесячной
y = yearly_summary(res)
assert abs(y["Платежи"].sum() - res.total_paid) < 0.01
assert abs(y["Проценты"].sum() - res.total_interest) < 0.01

# 6. Сравнение схем
both = compare_schemes(5_000_000, 14.0, 240, date(2026, 1, 1))
assert set(both) == {METHOD_ANNUITY, METHOD_DIFFERENTIATED}

print("Все проверки пройдены ✔")
print(f"Аннуитет: платёж {res.monthly_payment:,.2f} ₽, переплата {res.total_interest:,.2f} ₽")
print(f"Дифференцированный: 1-й платёж {d.monthly_payment:,.2f} ₽, "
      f"последний {d.last_payment:,.2f} ₽, переплата {d.total_interest:,.2f} ₽")
