"""Ядро ипотечного калькулятора.

Содержит расчёт аннуитетных и дифференцированных платежей,
построение графика платежей (амортизационной таблицы)
и агрегацию данных по годам.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

METHOD_ANNUITY = "annuity"
METHOD_DIFFERENTIATED = "differentiated"

METHOD_LABELS = {
    METHOD_ANNUITY: "Аннуитетный",
    METHOD_DIFFERENTIATED: "Дифференцированный",
}


def add_months(d: date, months: int) -> date:
    """Первое число месяца, наступающего через `months` месяцев после `d`."""
    total = d.year * 12 + (d.month - 1) + months
    year, month = divmod(total, 12)
    return date(year, month + 1, 1)


def annuity_payment(principal: float, annual_rate: float, n_months: int) -> float:
    """Фиксированный ежемесячный аннуитетный платёж."""
    if n_months <= 0:
        return 0.0
    r = annual_rate / 100.0 / 12.0
    if r == 0.0:
        return principal / n_months
    q = (1.0 + r) ** n_months
    return principal * r * q / (q - 1.0)


@dataclass
class MortgageResult:
    """Готовый результат расчёта ипотеки."""

    method: str
    principal: float
    annual_rate: float
    n_months: int
    start_date: date
    schedule: pd.DataFrame
    monthly_payment: float  # аннуитетный — постоянный; дифференцированный — первый платёж
    last_payment: float
    total_paid: float
    total_interest: float

    @property
    def payoff_date(self) -> date:
        """Дата последнего платежа."""
        return add_months(self.start_date, self.n_months - 1)

    @property
    def overpay_share(self) -> float:
        """Доля процентов в общей сумме выплат, %."""
        return self.total_interest / self.total_paid * 100.0 if self.total_paid else 0.0


def build_schedule(
    principal: float,
    annual_rate: float,
    n_months: int,
    method: str = METHOD_ANNUITY,
    start: date | None = None,
) -> MortgageResult:
    """Строит пошаговый график платежей.

    Каждая строка — один месяц: платёж, его части (тело и проценты)
    и остаток долга на конец месяца.
    """
    if n_months <= 0:
        raise ValueError("Срок кредита должен быть больше нуля месяцев")
    if principal <= 0:
        raise ValueError("Сумма кредита должна быть больше нуля")

    start = start or date.today().replace(day=1)
    r = annual_rate / 100.0 / 12.0
    annuity = annuity_payment(principal, annual_rate, n_months)
    diff_part = principal / n_months

    rows: list[dict] = []
    balance = principal
    total_paid = 0.0
    total_interest = 0.0
    first_payment = 0.0
    last_payment = 0.0

    for i in range(1, n_months + 1):
        interest = balance * r

        if method == METHOD_ANNUITY:
            if i == n_months:
                # Последний платёж закрывает остаток с учётом погрешности округлений
                principal_part = balance
                payment = principal_part + interest
            else:
                principal_part = annuity - interest
                if principal_part > balance:
                    principal_part = balance
                payment = principal_part + interest
        elif method == METHOD_DIFFERENTIATED:
            principal_part = diff_part if i < n_months else balance
            payment = principal_part + interest
        else:
            raise ValueError(f"Неизвестная схема платежа: {method}")

        balance = max(balance - principal_part, 0.0)
        total_paid += payment
        total_interest += interest
        if i == 1:
            first_payment = payment
        last_payment = payment

        rows.append(
            {
                "№": i,
                "Дата": pd.Timestamp(add_months(start, i - 1)),
                "Платёж": payment,
                "Основной долг": principal_part,
                "Проценты": interest,
                "Остаток долга": balance,
            }
        )

    schedule = pd.DataFrame(rows)
    return MortgageResult(
        method=method,
        principal=principal,
        annual_rate=annual_rate,
        n_months=n_months,
        start_date=start,
        schedule=schedule,
        monthly_payment=first_payment,
        last_payment=last_payment,
        total_paid=total_paid,
        total_interest=total_interest,
    )


def yearly_summary(res: MortgageResult) -> pd.DataFrame:
    """Агрегация графика платежей по календарным годам."""
    df = res.schedule.copy()
    df["Год"] = df["Дата"].dt.year
    grouped = (
        df.groupby("Год", as_index=False)
        .agg(
            Платежи=("Платёж", "sum"),
            **{"Основной долг": ("Основной долг", "sum"), "Проценты": ("Проценты", "sum")},
        )
        .sort_values("Год")
    )
    last_balances = df.groupby("Год")["Остаток долга"].last().rename("Остаток на конец года")
    grouped = grouped.merge(last_balances, left_on="Год", right_index=True)
    grouped.insert(1, "Месяцев", df.groupby("Год")["№"].count().reindex(grouped["Год"]).values)
    return grouped.reset_index(drop=True)


def compare_schemes(principal: float, annual_rate: float, n_months: int, start: date | None = None) -> dict[str, MortgageResult]:
    """Расчёт одной и той же ипотеки двумя схемами для сравнения."""
    return {
        METHOD_ANNUITY: build_schedule(principal, annual_rate, n_months, METHOD_ANNUITY, start),
        METHOD_DIFFERENTIATED: build_schedule(principal, annual_rate, n_months, METHOD_DIFFERENTIATED, start),
    }
