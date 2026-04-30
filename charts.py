from collections import defaultdict
from datetime import date

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from strategy import Trade


def plot_equity_curve(equity_curve: list[dict]) -> go.Figure:
    if not equity_curve:
        fig = go.Figure()
        fig.add_annotation(text="No trades to display", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        return fig

    dates = [e["date"] for e in equity_curve]
    equity = [e["equity"] for e in equity_curve]
    drawdown = [e["drawdown_pct"] * 100 for e in equity_curve]

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.04,
        subplot_titles=("Portfolio Equity (₹)", "Drawdown (%)"),
    )

    fig.add_trace(
        go.Scatter(
            x=dates, y=equity, mode="lines", name="Equity",
            line=dict(color="#2196F3", width=2),
            fill="tozeroy", fillcolor="rgba(33,150,243,0.08)",
        ),
        row=1, col=1,
    )

    fig.add_trace(
        go.Bar(
            x=dates, y=[-d for d in drawdown], name="Drawdown",
            marker_color="rgba(244,67,54,0.7)",
        ),
        row=2, col=1,
    )

    fig.update_layout(
        template="plotly_dark",
        showlegend=False,
        margin=dict(l=10, r=10, t=30, b=10),
        hovermode="x unified",
    )
    fig.update_yaxes(title_text="₹", row=1, col=1, tickprefix="₹", tickformat=",.0f")
    fig.update_yaxes(title_text="%", row=2, col=1, ticksuffix="%", range=[-50, 0])
    return fig


def plot_trade_distribution(trades: list[Trade]) -> go.Figure:
    closed = [t for t in trades if t.r_multiple is not None and t.exit_reason not in ("NO_SIGNAL", "SKIP", None)]
    if not closed:
        fig = go.Figure()
        fig.add_annotation(text="No closed trades", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(template="plotly_dark")
        return fig

    r_values = [t.r_multiple for t in closed]
    colors = ["rgba(76,175,80,0.8)" if r >= 0 else "rgba(244,67,54,0.8)" for r in r_values]

    fig = go.Figure(
        go.Histogram(
            x=r_values,
            xbins=dict(start=-4, end=5, size=0.5),
            marker_color=colors,
            name="R-Multiple",
        )
    )
    fig.add_vline(x=0, line_dash="dash", line_color="white", line_width=1)
    fig.update_layout(
        title="R-Multiple Distribution",
        xaxis_title="R-Multiple",
        yaxis_title="# Trades",
        template="plotly_dark",
        margin=dict(l=10, r=10, t=40, b=10),
        bargap=0.05,
    )
    return fig


def plot_monthly_pnl(trades: list[Trade]) -> go.Figure:
    closed = [t for t in trades if t.pnl is not None and t.exit_date and t.exit_reason not in ("NO_SIGNAL", "SKIP", None)]
    if not closed:
        fig = go.Figure()
        fig.add_annotation(text="No closed trades", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        fig.update_layout(template="plotly_dark")
        return fig

    monthly: dict[tuple[int, int], float] = defaultdict(float)
    for t in closed:
        monthly[(t.exit_date.year, t.exit_date.month)] += t.pnl

    years = sorted({y for y, m in monthly})
    months = list(range(1, 13))
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    z = []
    text = []
    for y in years:
        row = []
        row_text = []
        for m in months:
            val = monthly.get((y, m), None)
            row.append(val)
            row_text.append(f"₹{val:,.0f}" if val is not None else "")
        z.append(row)
        text.append(row_text)

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=month_labels,
            y=[str(y) for y in years],
            text=text,
            texttemplate="%{text}",
            colorscale="RdYlGn",
            zmid=0,
            showscale=True,
            colorbar=dict(title="P&L (₹)"),
        )
    )
    fig.update_layout(
        title="Monthly P&L Heatmap",
        template="plotly_dark",
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis_title="Month",
        yaxis_title="Year",
    )
    return fig
