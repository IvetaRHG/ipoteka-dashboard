"""Ипотечный калькулятор с дашбордом (Streamlit + Plotly).

Запуск:  streamlit run app.py
"""

from __future__ import annotations

import math
from string import Template

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

st.set_page_config(
    page_title="Ипотечный калькулятор",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------
# Кегль: +2 пт ко всему тексту, кроме заголовка страницы (1 пт = 4/3 px)
# --------------------------------------------------------------------------
FONT_BUMP_PX = 2 * 4 / 3  # 2 пт ≈ 2.667 px
TEXT_BASE = 14  # базовый кегль Streamlit
TEXT_BIG = 16  # кнопки
CHART_BASE = 13  # базовый кегль графиков
CHART_TICK = 12  # подписи осей и легенды
CHART_TITLE = 16  # заголовки графиков


def px(base: float) -> float:
    """Базовый кегль плюс прибавка в пикселях."""
    return round(base + FONT_BUMP_PX, 1)


# --------------------------------------------------------------------------
# Темы интерфейса
# --------------------------------------------------------------------------
THEME_LABELS = {
    "light": "☀️ Светлая",
    "dark": "🌙 Тёмная",
    "system": "💻 Системная",
    "pastel": "🌸 Пастельно-лиловая",
}

THEMES: dict[str, dict] = {
    "light": dict(
        label=THEME_LABELS["light"],
        bg="#ffffff",
        secondary="#f8f8f7",
        text="#2f2d2b",
        muted="#78716c",
        border="#dcd8d4",
        soft="#efece8",
        card="#ffffff",
        card_border="#e4e0db",
        input_bg="#f1f0ee",
        input_border="#d7d3cf",
        hover="#f4f2ef",
        row_alt="#faf9f7",
        header="rgba(255,255,255,.92)",
        accent="#c53948",
        accent_soft="rgba(197,57,72,.07)",
        template="plotly_white",
        grid="#eef2f7",
        sankey_neutral="#334155",
        sankey_bank="#dc2626",
        chart=dict(
            principal="#2563eb", interest="#f59e0b", balance="#7c3aed",
            annuity="#2563eb", diff="#10b981", down="#0ea5e9",
        ),
    ),
    "dark": dict(
        label=THEME_LABELS["dark"],
        bg="#0e1117",
        secondary="#161a21",
        text="#f2f3f5",
        muted="#9aa3b2",
        border="#2a2f3a",
        soft="#22262f",
        card="#151a21",
        card_border="#262c38",
        input_bg="#1a1f28",
        input_border="#333a47",
        hover="#1d232d",
        row_alt="#12161d",
        header="rgba(14,17,23,.92)",
        accent="#e06c75",
        accent_soft="rgba(224,108,117,.12)",
        template="plotly_dark",
        grid="#242a35",
        sankey_neutral="#94a3b8",
        sankey_bank="#f87171",
        chart=dict(
            principal="#60a5fa", interest="#fbbf24", balance="#a78bfa",
            annuity="#60a5fa", diff="#34d399", down="#22d3ee",
        ),
    ),
    "pastel": dict(
        label=THEME_LABELS["pastel"],
        bg="#f7f3fc",
        secondary="#efe8fa",
        text="#3b3352",
        muted="#7b6f9b",
        border="#ded2f0",
        soft="#eee8f8",
        card="#ffffff",
        card_border="#e9e0f7",
        input_bg="#ffffff",
        input_border="#ded2f0",
        hover="#f5f0fc",
        row_alt="#faf8fe",
        header="rgba(247,243,252,.92)",
        accent="#8667cf",
        accent_soft="rgba(134,103,207,.10)",
        template="plotly_white",
        grid="#efe9f8",
        sankey_neutral="#5f5580",
        sankey_bank="#d4708f",
        chart=dict(
            principal="#8b76e3", interest="#f0a865", balance="#c07bd6",
            annuity="#8b76e3", diff="#5cbf9a", down="#7fd4e8",
        ),
    ),
}

# Тема «Системная» разворачивается в светлую или тёмную по настройке ОС
SYSTEM_KEY = "light"
P: dict = THEMES["light"]  # активная палитра (заполняется при каждом запуске)


def detect_system_theme() -> str:
    """Светлая или тёмная тема задана в Windows (для варианта «Системная»)."""
    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if int(value) else "dark"
    except Exception:
        return "light"


def app_css(p: dict) -> str:
    """Весь CSS приложения: палитра темы + прибавка кегля +2 пт (кроме h1)."""
    c = p["chart"]
    tpl = Template("""
<style>
:root { --bump: ${bump}px; }

/* ===== Тема «${label}» ===== */
.stApp, body { background-color: ${bg} !important; }
[data-testid="stSidebar"] { background-color: ${secondary} !important; }
.stApp, .stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3,
[data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] h2,
[data-testid="stMetricValue"], [data-testid="stWidgetLabel"], [role="tab"],
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"],
[data-testid="stNumberInputField"], [data-testid="stRadioOption"] { color: ${text} !important; }

[data-testid="stMetricLabel"], [data-testid="stMetricDelta"] { color: ${muted} !important; }
[data-testid="stMetricDelta"] { background-color: ${soft} !important; }

/* шапка и боковая панель */
[data-testid="stHeader"] { background-color: ${header} !important; }
[data-testid="stHeader"] button, [data-testid="stHeader"] svg { color: ${text} !important; }
[data-testid="stSidebarCollapsedControl"] { background-color: ${secondary} !important; color: ${text} !important; }
[data-testid="stSidebar"] hr { border-color: ${border} !important; }
[data-testid="stSidebarCollapsedControl"] svg { stroke: ${text}; }

/* вкладки */
[role="tab"][aria-selected="true"] { color: ${accent} !important; }
[role="tab"][aria-selected="false"] { color: ${muted} !important; }
[class*="SelectionIndicator"] { background-color: ${accent} !important; }
[role="tablist"]::after { background-color: ${soft} !important; }

/* карточки метрик и графиков */
[data-testid="stMetric"] {
    background: ${card} !important;
    border: 1px solid ${card_border} !important;
    box-shadow: none;
}
[data-testid="stPlotlyChart"] {
    background: ${card} !important;
    border: 1px solid ${card_border} !important;
    border-radius: 14px;
    padding: 6px;
}

/* поля ввода и кнопки */
[data-testid="stNumberInputContainer"] { background: ${input_bg} !important; border-color: ${input_border} !important; }
[data-testid="stNumberInputContainer"] * { border-color: ${input_border} !important; }
[data-testid="stNumberInputField"] { color: ${text} !important; }
[data-testid="stNumberInput"] button { color: ${text} !important; }
[data-testid="stNumberInput"] button svg { stroke: ${text}; }
[data-testid="stTooltipHoverTarget"] button svg { stroke: ${muted} !important; }
[data-testid="stBaseButton-secondary"] { background: ${card} !important; border-color: ${input_border} !important; }
[data-testid="stRadioOption"][data-selected="true"] > div > div { border-color: ${accent} !important; }
[data-testid="stRadioOption"][data-selected="true"] > div > div > div { background-color: ${accent} !important; }

/* слайдер */
[data-testid="stSlider"] div[data-rac][style*="left:"] { background-color: ${accent} !important; }

/* таблицы */
.mt-wrap { background: ${card}; border: 1px solid ${card_border}; border-radius: 12px; overflow: hidden; }
.mt-wrap.scroll { max-height: 470px; overflow-y: auto; }
.mt {
    width: 100%;
    border-collapse: collapse;
    font-size: calc(${base}px + var(--bump));
    color: ${text};
}
.mt thead th {
    position: sticky; top: 0; z-index: 1;
    background: ${secondary};
    color: ${text};
    font-weight: 600;
    padding: 10px 14px;
    border-bottom: 1px solid ${border};
    white-space: nowrap;
}
.mt td {
    padding: 7px 14px;
    border-bottom: 1px solid ${soft};
    white-space: nowrap;
}
.mt .txt { text-align: left; }
.mt .num { text-align: right; }
.mt tbody tr:nth-child(even) { background: ${row_alt}; }
.mt tbody tr:hover { background: ${hover}; }
.mt tr.total td {
    font-weight: 700;
    background: ${accent_soft};
    border-top: 1px solid ${accent};
}

/* ===== +2 пт ко всему тексту, кроме заголовка страницы (h1) ===== */
p, li, label, [role="tab"], [data-testid="stCaptionContainer"],
[data-testid="stWidgetLabel"], [data-testid="stMetricLabel"], [data-testid="stMetricDelta"],
[data-testid="stNumberInputField"], [data-testid="stMarkdownContainer"], .mt,
.mt th, .mt td { font-size: calc(${base}px + var(--bump)) !important; }

[data-testid="stMetricValue"] { font-size: calc(1.35rem + var(--bump)) !important; }

button { font-size: calc(${base}px + var(--bump)) !important; }
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primary"] { font-size: calc(${big}px + var(--bump)) !important; }
[data-testid="stNumberInput"] button { font-size: calc(${base}px + var(--bump)) !important; }

h2 { font-size: calc(20px + var(--bump)) !important; }
h3 { font-size: calc(28px + var(--bump)) !important; }

/* заголовок страницы — без изменений */
[data-testid="stTitleElement"], h1 { font-size: 2.75rem !important; }
</style>
""")
    return tpl.substitute(
        bump=round(FONT_BUMP_PX, 3),
        label=p["label"],
        bg=p["bg"],
        secondary=p["secondary"],
        text=p["text"],
        muted=p["muted"],
        border=p["border"],
        soft=p["soft"],
        card=p["card"],
        card_border=p["card_border"],
        input_bg=p["input_bg"],
        input_border=p["input_border"],
        hover=p["hover"],
        row_alt=p["row_alt"],
        header=p["header"],
        accent=p["accent"],
        accent_soft=p["accent_soft"],
        base=TEXT_BASE,
        big=TEXT_BIG,
        chart_principal=c["principal"],
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


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def html_table(
    headers: list[str],
    rows: list[tuple],
    aligns: list[str],
    cls: str = "",
    total: tuple | None = None,
) -> str:
    """Таблица в HTML — подчиняется теме приложения и общему кеглю."""
    th = "".join(f'<th class="{a}">{h}</th>' for h, a in zip(headers, aligns))
    body = [
        "<tr>" + "".join(f'<td class="{a}">{v}</td>' for v, a in zip(row, aligns)) + "</tr>"
        for row in rows
    ]
    if total is not None:
        cells = "".join(f'<td class="{a}">{v}</td>' for v, a in zip(total, aligns))
        body.append(f'<tr class="total">{cells}</tr>')
    return (
        f'<div class="mt-wrap {cls}"><table class="mt">'
        f"<thead><tr>{th}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def schedule_table_html(res: MortgageResult) -> str:
    headers = ["№", "Месяц", "Платёж, ₽", "Основной долг, ₽", "Проценты, ₽", "Остаток долга, ₽"]
    aligns = ["txt", "txt", "num", "num", "num", "num"]
    rows = [
        (num, f"{dt:%m.%Y}", money(pay), money(part), money(intr), money(bal))
        for num, dt, pay, part, intr, bal in res.schedule.itertuples(index=False, name=None)
    ]
    return html_table(headers, rows, aligns, cls="scroll")


def yearly_table_html(res: MortgageResult) -> str:
    headers = ["Год", "Месяцев", "Сумма платежей, ₽", "Погашено тела, ₽", "Проценты, ₽", "Остаток долга, ₽"]
    aligns = ["txt", "num", "num", "num", "num", "num"]
    rows = [
        (
            str(rec["Год"]),
            rec["Месяцев"],
            money(rec["Платежи"]),
            money(rec["Основной долг"]),
            money(rec["Проценты"]),
            money(rec["Остаток на конец года"]),
        )
        for rec in yearly_summary(res).to_dict("records")
    ]
    total = (
        "ИТОГО",
        res.n_months,
        money(res.total_paid),
        money(res.principal),
        money(res.total_interest),
        money(0),
    )
    return html_table(headers, rows, aligns, total=total)


def show_chart(fig: go.Figure, key: str | None = None) -> None:
    """Рендер Plotly-графика: палитра активной темы и общий кегль +2 пт."""
    fig.update_layout(
        template=P["template"],
        font=dict(family="Segoe UI, Arial, sans-serif", size=px(CHART_BASE), color=P["text"]),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=45, b=75),
        title=dict(
            x=0.005, xanchor="left", y=0.98, yanchor="top",
            font=dict(size=px(CHART_TITLE), color=P["text"]),
        ),
        legend=dict(
            orientation="h", yanchor="top", y=-0.22, xanchor="left", x=0,
            font=dict(size=px(CHART_TICK), color=P["text"]),
        ),
        hoverlabel=dict(
            bgcolor=P["card"],
            font=dict(color=P["text"], size=px(CHART_BASE)),
        ),
    )
    tick = dict(size=px(CHART_TICK), color=P["text"])
    fig.update_xaxes(tickfont=tick, gridcolor=P["grid"], zeroline=False)
    fig.update_yaxes(tickfont=tick, gridcolor=P["grid"], zeroline=False)
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
    fig.update_yaxes(title=y_title)
    fig.update_xaxes(title=x_title)
    return fig


# --------------------------------------------------------------------------
# Графики дашборда
# --------------------------------------------------------------------------
def donut_figure(res: MortgageResult) -> go.Figure:
    c = P["chart"]
    labels = ["Основной долг (тело кредита)", "Проценты (переплата банку)"]
    values = [res.principal, res.total_interest]
    colors = [c["principal"], c["interest"]]
    if res.total_interest <= 0:
        labels, values, colors = ["Основной долг (тело кредита)"], [res.principal], [c["principal"]]

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.6,
            marker=dict(colors=colors, line=dict(color=P["card"], width=3)),
            textinfo="percent",
            textposition="inside",
            textfont=dict(size=px(15), color="#ffffff"),
            hovertemplate="%{label}<br>%{value:,.0f} ₽ (%{percent})<extra></extra>",
        )
    )
    fig.update_layout(
        title="Структура выплат",
        annotations=[
            dict(
                text=(
                    f"<b>{money(res.total_paid)} ₽</b><br>"
                    f"<span style='font-size:{px(12)}px;color:{P['muted']}'>всего выплачено</span>"
                ),
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=px(14), color=P["text"]),
            )
        ],
    )
    return fig


def yearly_bar_figure(res: MortgageResult) -> go.Figure:
    c = P["chart"]
    df = res.schedule.copy()
    df["Год"] = df["Дата"].dt.year
    g = df.groupby("Год", as_index=False)[["Основной долг", "Проценты"]].sum()

    fig = go.Figure()
    fig.add_bar(
        x=g["Год"].astype(str), y=g["Основной долг"], name="Основной долг",
        marker_color=c["principal"], hovertemplate="%{x}: %{y:,.0f} ₽<extra>тело долга</extra>",
    )
    fig.add_bar(
        x=g["Год"].astype(str), y=g["Проценты"], name="Проценты",
        marker_color=c["interest"], hovertemplate="%{x}: %{y:,.0f} ₽<extra>проценты</extra>",
    )
    fig.update_layout(barmode="stack", title="Платежи по годам")
    ticks, tick_labels = rub_ticks((g["Основной долг"] + g["Проценты"]).tolist())
    return base_layout(fig, "₽").update_yaxes(tickvals=ticks, ticktext=tick_labels)


def balance_figure(res: MortgageResult) -> go.Figure:
    c = P["chart"]
    df = res.schedule.copy()
    df["Накопленные проценты"] = df["Проценты"].cumsum()
    df["Накопленный основной долг"] = df["Основной долг"].cumsum()

    fig = go.Figure()
    fig.add_scatter(
        x=df["Дата"], y=df["Остаток долга"], mode="lines", name="Остаток долга",
        line=dict(color=c["balance"], width=2.5), fill="tozeroy",
        fillcolor=rgba(c["balance"], 0.10),
        hovertemplate="%{x|%m.%Y}<br>остаток: %{y:,.0f} ₽<extra></extra>",
    )
    fig.add_scatter(
        x=df["Дата"], y=df["Накопленные проценты"], mode="lines", name="Накопленные проценты",
        line=dict(color=c["interest"], width=2, dash="dot"),
        hovertemplate="%{x|%m.%Y}<br>проценты: %{y:,.0f} ₽<extra></extra>",
    )
    fig.add_scatter(
        x=df["Дата"], y=df["Накопленный основной долг"], mode="lines", name="Погашено основного долга",
        line=dict(color=c["principal"], width=2, dash="dash"),
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
            textfont=dict(color="#111827"),
            colorbar=dict(
                title=dict(text="% тела<br>в платеже", font=dict(color=P["text"])),
                tickfont=dict(color=P["text"]),
                thickness=14,
            ),
            hovertemplate="Год %{y}, месяц %{x}<br>доля основного долга: %{z:.1f} %<extra></extra>",
        )
    )
    fig.update_layout(
        title="Доля основного долга в платеже, %",
        yaxis=dict(autorange="reversed", title=""),
        xaxis=dict(title="Месяц периода", dtick=1),
    )
    return fig


def sankey_figure(res: MortgageResult, down_payment: float) -> go.Figure:
    """Схема движения средств: откуда берутся и куда уходят деньги."""
    c = P["chart"]
    labels = [
        "Первоначальный взнос", "Кредит (тело)", "Переплата (проценты)",
        "Стоимость жилья", "Доход банка",
    ]
    fig = go.Figure(
        go.Sankey(
            textfont=dict(size=px(CHART_TICK), color=P["text"]),
            node=dict(
                label=labels,
                color=[c["down"], c["principal"], c["interest"], P["sankey_neutral"], P["sankey_bank"]],
                pad=16, thickness=22,
                line=dict(color=P["card_border"], width=1),
            ),
            link=dict(
                source=[0, 1, 2],
                target=[3, 3, 4],
                value=[max(down_payment, 0), res.principal, max(res.total_interest, 0)],
                color=[
                    rgba(c["down"], 0.35),
                    rgba(c["principal"], 0.35),
                    rgba(c["interest"], 0.35),
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
    c = P["chart"]
    fig = go.Figure()
    for method, color in ((METHOD_ANNUITY, c["annuity"]), (METHOD_DIFFERENTIATED, c["diff"])):
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
    c = P["chart"]
    methods = [METHOD_ANNUITY, METHOD_DIFFERENTIATED]
    fig = go.Figure()
    fig.add_bar(
        x=[METHOD_LABELS[m] for m in methods],
        y=[results[m].total_interest for m in methods],
        name="Переплата (проценты)",
        marker_color=[c["annuity"], c["diff"]],
        text=[money(results[m].total_interest) for m in methods],
        textposition="outside",
        hovertemplate="%{x}<br>%{y:,.0f} ₽<extra></extra>",
    )
    fig.update_layout(title="Переплата по схемам")
    values = [results[m].total_interest for m in methods]
    ticks, tick_labels = rub_ticks(values, lo=0.0)
    return base_layout(fig, "₽").update_yaxes(tickvals=ticks, ticktext=tick_labels)


def compare_rows(results: dict[str, MortgageResult]) -> list[tuple]:
    a, d = results[METHOD_ANNUITY], results[METHOD_DIFFERENTIATED]
    return [
        ("Платёж в первый месяц", money(a.monthly_payment), money(d.monthly_payment)),
        ("Платёж в последний месяц", money(a.last_payment), money(d.last_payment)),
        ("Общая сумма выплат", money(a.total_paid), money(d.total_paid)),
        ("Переплата (проценты)", money(a.total_interest), money(d.total_interest)),
        ("Доля переплаты в выплатах", pct(a.overpay_share), pct(d.overpay_share)),
        ("Разница в переплате", "—", money(d.total_interest - a.total_interest)),
    ]


# --------------------------------------------------------------------------
# Боковая панель: переключатель тем и входные параметры
# --------------------------------------------------------------------------
st.sidebar.markdown("## 🎨 Тема")
theme_label = st.sidebar.radio(
    "Тема оформления",
    options=list(THEME_LABELS.values()),
    key="theme_label",
    label_visibility="collapsed",
    help="Системная берёт светлую или тёмную оформление из настроек Windows",
)
theme_key = next(k for k, v in THEME_LABELS.items() if v == theme_label)
SYSTEM_KEY = detect_system_theme()
P = THEMES[SYSTEM_KEY if theme_key == "system" else theme_key]
st.markdown(app_css(P), unsafe_allow_html=True)

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
    f"Тема: **{P['label']}** · Схема: **{method_label}** · Ставка: **{rate:.1f}%** · "
    f"Срок: **{years} лет** · Кредит: **{money(principal)} ₽** · "
    f"Первый платёж: **{result.schedule['Дата'].iloc[0]:%m.%Y}**"
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

    st.markdown(schedule_table_html(result), unsafe_allow_html=True)

    st.subheader("Итоги по годам")
    st.markdown(yearly_table_html(result), unsafe_allow_html=True)

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
    st.markdown(
        html_table(
            ["Показатель", METHOD_LABELS[METHOD_ANNUITY], METHOD_LABELS[METHOD_DIFFERENTIATED]],
            compare_rows(results),
            ["txt", "num", "num"],
        ),
        unsafe_allow_html=True,
    )

    st.caption(
        "Аннуитетный платёж постоянный весь срок и удобнее для бюджета; при дифференцированном "
        "платеже сумма убывает, но в первые годы нагрузка выше, а общая переплата меньше."
    )
