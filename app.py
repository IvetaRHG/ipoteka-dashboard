"""Ипотечный калькулятор с дашбордом (Streamlit + Plotly).

Запуск:  streamlit run app.py
"""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from mortgage import (
    METHOD_ANNUITY,
    METHOD_DIFFERENTIATED,
    METHOD_LABELS,
    MortgageResult,
    build_schedule,
    compare_schemes,
    yearly_summary,
)

# --------------------------------------------------------------------------
# Настройка страницы и стилей
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Ипотечный калькулятор",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Палитра
C_PRINCIPAL = "#2563eb"  # основной долг
C_INTEREST = "#f59e0b"  # проценты
C_BALANCE = "#7c3aed"  # остаток долга
C_ANNUITY = "#2563eb"
C_DIFF = "#10b981"
C_TEXT = "#0f172a"
C_MUTED = "#64748b"

st.markdown(
    """
    <style>
      [data-testid="stMetric"] {
          background: #ffffff;
          border: 1px solid #e2e8f0;
          border-radius: 14px;
          padding: 14px 18px;
          box-shadow: 0 1px 2px rgba(15, 23, 42, .04);
      }
      [data-testid="stMetricValue"] { font-size: 1.35rem; font-weight: 700; color: #0f172a; }
      [data-testid="stMetricLabel"] { color: #64748b; font-size: .85rem; }
      [data-testid="stPlotlyChart"] {
          background: #ffffff;
          border: 1px solid #e2e8f0;
          border-radius: 14px;
          padding: 6px;
      }
      [data-testid="stDataFrame"] { border: 1px solid #e2e8f0; border-radius: 12px; }
      div[data-testid="stVerticalBlockGap"] > div:has(> div[data-testid="stTabs"]) { gap: .4rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# Вспомогательные функции
# --------------------------------------------------------------------------
def money(x: float) -> str:
    """Число в рублях с неразрывными пробелами: 1 234 567 ₽."""
    return f"{x:,.0f}".replace(",", "\u00a0")


def pct(x: float, nd: int = 1) -> str:
    return f"{x:.{nd}f}".replace(".", ",") + " %"


def years_word(n: int) -> str:
    """Склонение слова «год» для числа лет."""
    if n % 10 == 1 and n % 100 != 11:
        return "год"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "года"
    return "лет"


def show_chart(fig: go.Figure, key: str | None = None) -> None:
    """Рендер Plotly-графика на всю ширину колонки."""
    fig.update_layout(
        template="plotly_white",
        font=dict(family="Segoe UI, Arial, sans-serif", size=13, color=C_TEXT),
        margin=dict(l=10, r=10, t=45, b=75),
        title=dict(x=0.005, xanchor="left", y=0.98, yanchor="top"),
        legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="left", x=0),
    )
    try:
        st.plotly_chart(fig, width="stretch", key=key, config={"displaylogo": False})
    except TypeError:  # старые версии Streamlit
        st.plotly_chart(fig, use_container_width=True, key=key, config={"displaylogo": False})


def rub_ticks(values, n: int = 5, lo: float | None = None) -> tuple[list[float], list[str]]:
    """Красивые деления оси в рублях: 0, 2 000 000, 4 000 000 …"""
    lo = min(values) if lo is None else lo
    hi = max(values)
    if hi <= lo:
        hi = lo + 1.0
    span = hi - lo
    raw = span / n
    mag = 10.0 ** math.floor(math.log10(raw)) if raw > 0 else 1.0
    step = mag * 10
    for m in (1, 2, 2.5, 5, 10):
        if span / (mag * m) <= n:
            step = mag * m
            break
    ticks: list[float] = []
    t = math.ceil(lo / step) * step
    while t <= hi + step * 0.5:
        ticks.append(round(t, 6))
        t += step
    return ticks, [money(v) for v in ticks]


def base_layout(fig: go.Figure, y_title: str = "", x_title: str = "") -> go.Figure:
    fig.update_yaxes(title=y_title, gridcolor="#eef2f7", zeroline=False)
    fig.update_xaxes(title=x_title, gridcolor="#eef2f7")
    return fig


# --------------------------------------------------------------------------
# Графики дашборда
# --------------------------------------------------------------------------
def donut_figure(res: MortgageResult) -> go.Figure:
    labels = ["Основной долг (тело кредита)", "Проценты (переплата банку)"]
    values = [res.principal, res.total_interest]
    colors = [C_PRINCIPAL, C_INTEREST]
    if res.total_interest <= 0:
        labels, values, colors = ["Основной долг (тело кредита)"], [res.principal], [C_PRINCIPAL]

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.6,
            marker=dict(colors=colors, line=dict(color="#ffffff", width=3)),
            textinfo="percent",
            textposition="inside",
            textfont=dict(size=15, color="#ffffff"),
            hovertemplate="%{label}<br>%{value:,.0f} ₽ (%{percent})<extra></extra>",
        )
    )
    fig.update_layout(
        title="Структура выплат",
        annotations=[
            dict(
                text=f"<b>{money(res.total_paid)} ₽</b><br><span style='font-size:12px;color:{C_MUTED}'>всего выплачено</span>",
                x=0.5, y=0.5, showarrow=False, font=dict(size=14),
            )
        ],
    )
    return fig


def yearly_bar_figure(res: MortgageResult) -> go.Figure:
    df = res.schedule.copy()
    df["Год"] = df["Дата"].dt.year
    g = df.groupby("Год", as_index=False)[["Основной долг", "Проценты"]].sum()

    fig = go.Figure()
    fig.add_bar(
        x=g["Год"].astype(str), y=g["Основной долг"], name="Основной долг",
        marker_color=C_PRINCIPAL, hovertemplate="%{x}: %{y:,.0f} ₽<extra>тело долга</extra>",
    )
    fig.add_bar(
        x=g["Год"].astype(str), y=g["Проценты"], name="Проценты",
        marker_color=C_INTEREST, hovertemplate="%{x}: %{y:,.0f} ₽<extra>проценты</extra>",
    )
    fig.update_layout(barmode="stack", title="Платежи по годам")
    ticks, tick_labels = rub_ticks((g["Основной долг"] + g["Проценты"]).tolist())
    return base_layout(fig, "₽").update_yaxes(tickvals=ticks, ticktext=tick_labels)


def balance_figure(res: MortgageResult) -> go.Figure:
    df = res.schedule.copy()
    df["Накопленные проценты"] = df["Проценты"].cumsum()
    df["Накопленный основной долг"] = df["Основной долг"].cumsum()

    fig = go.Figure()
    fig.add_scatter(
        x=df["Дата"], y=df["Остаток долга"], mode="lines", name="Остаток долга",
        line=dict(color=C_BALANCE, width=2.5), fill="tozeroy",
        fillcolor="rgba(124, 58, 237, .10)",
        hovertemplate="%{x|%m.%Y}<br>остаток: %{y:,.0f} ₽<extra></extra>",
    )
    fig.add_scatter(
        x=df["Дата"], y=df["Накопленные проценты"], mode="lines", name="Накопленные проценты",
        line=dict(color=C_INTEREST, width=2, dash="dot"),
        hovertemplate="%{x|%m.%Y}<br>проценты: %{y:,.0f} ₽<extra></extra>",
    )
    fig.add_scatter(
        x=df["Дата"], y=df["Накопленный основной долг"], mode="lines", name="Погашено основного долга",
        line=dict(color=C_PRINCIPAL, width=2, dash="dash"),
        hovertemplate="%{x|%m.%Y}<br>погашено: %{y:,.0f} ₽<extra></extra>",
    )
    fig.update_layout(title="Остаток долга и накопления")
    scale = df[["Остаток долга", "Накопленные проценты", "Накопленный основной долг"]].to_numpy()
    ticks, tick_labels = rub_ticks([0.0, float(scale.max())])
    return base_layout(fig, "₽", "Дата платежа").update_yaxes(tickvals=ticks, ticktext=tick_labels)


def heatmap_figure(res: MortgageResult) -> go.Figure:
    """Схема-сетка: доля тела долга в каждом платеже по годам и месяцам периода."""
    df = res.schedule.copy()
    df["Год периода"] = (df["№"] - 1) // 12 + 1
    df["Месяц"] = (df["№"] - 1) % 12 + 1
    df["Доля тела"] = df["Основной долг"] / df["Платёж"].where(df["Платёж"] != 0) * 100

    years = int(df["Год периода"].max())
    pivot = (
        df.pivot_table(index="Год периода", columns="Месяц", values="Доля тела", aggfunc="last")
        .reindex(index=range(1, years + 1), columns=range(1, 13))
    )
    z = pivot.to_numpy(dtype=float)
    text = [["" if pd.isna(v) else f"{v:.0f}" for v in row] for row in z]

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=[str(m) for m in range(1, 13)],
            y=[f"Год {y}" for y in range(1, years + 1)],
            colorscale=[[0, "#fee2e2"], [0.5, "#fef3c7"], [1, "#dcfce7"]],
            zmin=0, zmax=100,
            xgap=1, ygap=1,
            text=text,
            texttemplate="%{text}%" if years <= 12 else "",
            colorbar=dict(title="% тела<br>в платеже", thickness=14),
            hovertemplate="Год %{y}, месяц %{x}<br>доля основного долга: %{z:.1f} %<extra></extra>",
        )
    )
    fig.update_layout(
        title="Доля основного долга в платеже, %",
        yaxis=dict(autorange="reversed", title="", gridcolor="#eef2f7"),
        xaxis=dict(title="Месяц периода", gridcolor="#eef2f7", dtick=1),
    )
    return fig


def sankey_figure(res: MortgageResult, down_payment: float) -> go.Figure:
    """Схема движения средств: откуда берутся и куда уходят деньги."""
    labels = [
        "Первоначальный взнос", "Кредит (тело)", "Переплата (проценты)",
        "Стоимость жилья", "Доход банка",
    ]
    fig = go.Figure(
        go.Sankey(
            node=dict(
                label=labels,
                color=["#0ea5e9", C_PRINCIPAL, C_INTEREST, "#334155", "#dc2626"],
                pad=16, thickness=22,
                line=dict(color="#e2e8f0", width=1),
            ),
            link=dict(
                source=[0, 1, 2],
                target=[3, 3, 4],
                value=[max(down_payment, 0), res.principal, max(res.total_interest, 0)],
                color=[
                    "rgba(14,165,233,.35)",
                    "rgba(37,99,235,.35)",
                    "rgba(245,158,11,.35)",
                ],
            ),
        )
    )
    fig.update_layout(title="Движение средств по кредиту", height=430)
    return fig


# --------------------------------------------------------------------------
# Сравнение схем платежа
# --------------------------------------------------------------------------
def payment_compare_figure(results: dict[str, MortgageResult]) -> go.Figure:
    fig = go.Figure()
    for method, color in ((METHOD_ANNUITY, C_ANNUITY), (METHOD_DIFFERENTIATED, C_DIFF)):
        df = results[method].schedule
        fig.add_scatter(
            x=df["Дата"], y=df["Платёж"], mode="lines", name=METHOD_LABELS[method],
            line=dict(color=color, width=2.4),
            hovertemplate=f"{METHOD_LABELS[method]}<br>%{{x|%m.%Y}}: %{{y:,.0f}} ₽<extra></extra>",
        )
    fig.update_layout(title="Платёж по месяцам")
    scale = [float(results[m].schedule["Платёж"].max()) for m in results]
    ticks, tick_labels = rub_ticks(scale, lo=0.0)
    return base_layout(fig, "₽", "Дата платежа").update_yaxes(tickvals=ticks, ticktext=tick_labels)


def overpay_compare_figure(results: dict[str, MortgageResult]) -> go.Figure:
    methods = [METHOD_ANNUITY, METHOD_DIFFERENTIATED]
    fig = go.Figure()
    fig.add_bar(
        x=[METHOD_LABELS[m] for m in methods],
        y=[results[m].total_interest for m in methods],
        name="Переплата (проценты)",
        marker_color=[C_ANNUITY, C_DIFF],
        text=[money(results[m].total_interest) for m in methods],
        textposition="outside",
        hovertemplate="%{x}<br>%{y:,.0f} ₽<extra></extra>",
    )
    fig.update_layout(title="Переплата по схемам")
    values = [results[m].total_interest for m in methods]
    ticks, tick_labels = rub_ticks(values, lo=0.0)
    return base_layout(fig, "₽").update_yaxes(tickvals=ticks, ticktext=tick_labels)


def compare_table(results: dict[str, MortgageResult]) -> pd.DataFrame:
    a, d = results[METHOD_ANNUITY], results[METHOD_DIFFERENTIATED]
    rows = [
        ("Платёж в первый месяц", money(a.monthly_payment), money(d.monthly_payment)),
        ("Платёж в последний месяц", money(a.last_payment), money(d.last_payment)),
        ("Общая сумма выплат", money(a.total_paid), money(d.total_paid)),
        ("Переплата (проценты)", money(a.total_interest), money(d.total_interest)),
        ("Доля переплаты в выплатах", pct(a.overpay_share), pct(d.overpay_share)),
        ("Разница в переплате", "—", money(d.total_interest - a.total_interest)),
    ]
    return pd.DataFrame(
        rows,
        columns=["Показатель", METHOD_LABELS[METHOD_ANNUITY], METHOD_LABELS[METHOD_DIFFERENTIATED]],
    )


# --------------------------------------------------------------------------
# Боковая панель: входные параметры
# --------------------------------------------------------------------------
st.sidebar.markdown("## ⚙️ Параметры кредита")

price = st.sidebar.number_input(
    "Стоимость недвижимости, ₽",
    min_value=100_000, max_value=1_000_000_000, value=8_000_000, step=100_000,
    help="Полная стоимость квартиры, дома или другой недвижимости",
)
down = st.sidebar.number_input(
    "Первоначальный взнос, ₽",
    min_value=0, max_value=int(price), value=min(2_000_000, int(price)), step=50_000,
    help="Собственные средства на руках",
)
down = min(down, price)  # защита при уменьшении стоимости недвижимости
principal = price - down

years = st.sidebar.slider("Срок кредита, лет", 1, 30, 20, help="Полный срок погашения")
rate = st.sidebar.number_input(
    "Процентная ставка, % годовых",
    min_value=0.0, max_value=100.0, value=14.0, step=0.1,
    help="Годовая ставка по кредиту",
)
method_label = st.sidebar.radio(
    "Схема платежа",
    options=[METHOD_LABELS[METHOD_ANNUITY], METHOD_LABELS[METHOD_DIFFERENTIATED]],
    help="Аннуитет — одинаковый платёж весь срок; дифференцированный — платёж убывает",
)
method = METHOD_ANNUITY if method_label == METHOD_LABELS[METHOD_ANNUITY] else METHOD_DIFFERENTIATED

income = st.sidebar.number_input(
    "Доход в месяц, ₽",
    min_value=0, max_value=100_000_000, value=300_000, step=10_000,
    help="Нужен для оценки кредитной нагрузки",
)

st.sidebar.markdown("---")
st.sidebar.metric("Сумма кредита", f"{money(principal)} ₽")
st.sidebar.caption(
    f"Первоначальный взнос: **{pct(down / price * 100 if price else 0, 0)}** от стоимости · "
    f"Срок: **{years * 12}** месяцев"
)

# --------------------------------------------------------------------------
# Расчёт
# --------------------------------------------------------------------------
n_months = years * 12
try:
    result = build_schedule(principal, rate, n_months, method)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

payment = result.monthly_payment
load = payment / income * 100 if income > 0 else None

# --------------------------------------------------------------------------
# Шапка
# --------------------------------------------------------------------------
st.title("🏠 Ипотечный калькулятор")
st.caption(
    f"Схема: **{method_label}** · Ставка: **{rate:.1f}%** · Срок: **{years} лет** · "
    f"Кредит: **{money(principal)} ₽** · Первый платёж: **{result.schedule['Дата'].iloc[0]:%m.%Y}**"
)

tab_dash, tab_table, tab_cmp = st.tabs(
    ["📊 Дашборд", "📅 График платежей", "⚖️ Сравнение схем"]
)

# --------------------------------------------------------------------------
# Вкладка 1: Дашборд
# --------------------------------------------------------------------------
with tab_dash:
    row_a = st.columns(3)
    row_b = st.columns(3)
    with row_a[0]:
        st.metric(
            "Платёж в месяц" if method == METHOD_ANNUITY else "Первый платёж",
            f"{money(payment)} ₽",
            delta=None if method == METHOD_ANNUITY else f"последний: {money(result.last_payment)} ₽",
            delta_color="off",
        )
    with row_a[1]:
        st.metric(
            "Сумма кредита",
            f"{money(principal)} ₽",
            delta=f"взнос {pct(down / price * 100 if price else 0, 0)}",
            delta_color="off",
        )
    with row_a[2]:
        st.metric(
            "Общая выплата",
            f"{money(result.total_paid)} ₽",
            delta=f"{n_months} платежей",
            delta_color="off",
        )
    with row_b[0]:
        st.metric(
            "Переплата процентами",
            f"{money(result.total_interest)} ₽",
            delta=f"{pct(result.overpay_share)} от выплат",
            delta_color="off",
        )
    with row_b[1]:
        st.metric(
            "Платёж от дохода",
            "—" if load is None else pct(load, 0),
            delta="норма ≤ 30–40 %" if load is not None else "укажите доход",
            delta_color="off",
        )
    with row_b[2]:
        years_passed = result.payoff_date.year - result.start_date.year
        st.metric(
            "Последний платёж",
            f"{result.payoff_date:%m.%Y}",
            delta=f"{years_passed} {years_word(years_passed)}",
            delta_color="off",
        )

    st.markdown("")
    row1 = st.columns([1, 1])
    with row1[0]:
        show_chart(donut_figure(result), key="donut")
    with row1[1]:
        show_chart(yearly_bar_figure(result), key="yearbar")

    show_chart(balance_figure(result), key="balance")

    row2 = st.columns([1, 1])
    with row2[0]:
        show_chart(heatmap_figure(result), key="heatmap")
    with row2[1]:
        show_chart(sankey_figure(result, down), key="sankey")

    st.caption(
        "Схема-сетка показывает, как доля основного долга в платеже растёт от месяца к месяцу: "
        "зелёное — платёж почти полностью идёт на погашение тела кредита, красное — большая часть "
        "уходит банку в качестве процентов."
    )

# --------------------------------------------------------------------------
# Вкладка 2: График платежей (таблицы)
# --------------------------------------------------------------------------
with tab_table:
    st.subheader("Помесячный график платежей")
    c1, c2 = st.columns([3, 1])
    with c2:
        csv = result.schedule.to_csv(index=False, sep=";", float_format="%.2f").encode("utf-8-sig")
        st.download_button(
            "⬇️ Скачать CSV",
            data=csv,
            file_name=f"ipoteka_grafik_{method}_{n_months}m.csv",
            mime="text/csv",
            use_container_width=True,
        )

    table = result.schedule.copy()
    table["Дата"] = table["Дата"].dt.strftime("%m.%Y")
    for col in ("Платёж", "Основной долг", "Проценты", "Остаток долга"):
        table[col] = table[col].map(lambda v: money(v))
    table = table.rename(
        columns={
            "№": "№",
            "Дата": "Месяц",
            "Платёж": "Платёж, ₽",
            "Основной долг": "Основной долг, ₽",
            "Проценты": "Проценты, ₽",
            "Остаток долга": "Остаток долга, ₽",
        }
    )
    st.dataframe(table, hide_index=True, height=460)

    st.subheader("Итоги по годам")
    ytab = yearly_summary(result)
    yshow = ytab.copy()
    yshow["Год"] = yshow["Год"].astype(str)
    for col in ("Платежи", "Основной долг", "Проценты", "Остаток на конец года"):
        yshow[col] = yshow[col].map(lambda v: money(v))
    yshow = yshow.rename(
        columns={
            "Год": "Год",
            "Месяцев": "Месяцев",
            "Платежи": "Сумма платежей, ₽",
            "Основной долг": "Погашено тела, ₽",
            "Проценты": "Проценты, ₽",
            "Остаток на конец года": "Остаток долга на конец года, ₽",
        }
    )
    st.dataframe(yshow, hide_index=True)

    total_row = pd.DataFrame(
        [{
            "Год": "ИТОГО",
            "Месяцев": n_months,
            "Сумма платежей, ₽": money(result.total_paid),
            "Погашено тела, ₽": money(result.principal),
            "Проценты, ₽": money(result.total_interest),
            "Остаток долга на конец года, ₽": money(0),
        }]
    )
    st.dataframe(total_row, hide_index=True)

# --------------------------------------------------------------------------
# Вкладка 3: Сравнение схем
# --------------------------------------------------------------------------
with tab_cmp:
    st.subheader("Аннуитетный против дифференцированного платежа")
    results = compare_schemes(principal, rate, n_months)

    a, d = results[METHOD_ANNUITY], results[METHOD_DIFFERENTIATED]
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Переплата: аннуитет", f"{money(a.total_interest)} ₽")
    with k2:
        st.metric("Переплата: дифференц.", f"{money(d.total_interest)} ₽")
    with k3:
        st.metric(
            "Разница переплаты",
            f"{money(abs(d.total_interest - a.total_interest))} ₽",
            delta="выигрыш дифференц." if d.total_interest < a.total_interest else "выигрыш аннуитета",
            delta_color="off",
        )
    with k4:
        st.metric(
            "Разница 1-го платежа",
            f"{money(abs(d.monthly_payment - a.monthly_payment))} ₽",
            delta="дифференц. стартует выше",
            delta_color="off",
        )

    row = st.columns(2)
    with row[0]:
        show_chart(payment_compare_figure(results), key="cmp_pay")
    with row[1]:
        show_chart(overpay_compare_figure(results), key="cmp_over")

    st.markdown("**Сводная таблица**")
    st.dataframe(compare_table(results), hide_index=True, width=700)

    st.caption(
        "Аннуитетный платёж постоянный весь срок и удобнее для бюджета; при дифференцированном "
        "платеже сумма убывает, но в первые годы нагрузка выше, а общая переплата меньше."
    )
