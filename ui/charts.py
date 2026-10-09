"""AnswerCard.chart -> Plotly figure with one consistent, validated light theme.

Palette: the dataviz skill's light categorical slots, validated against the white card
surface (all checks pass). Series with very different scales (e.g. a % and
LPA) are drawn as side-by-side small multiples — never a dual axis.
"""
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from agents.schemas import Chart

PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
INK, INK_2, MUTED, GRID, AXIS = "#0f172a", "#334155", "#64748b", "#e8ebf1", "#c9cfda"
SURFACE = "#ffffff"
FONT = "Inter, system-ui, -apple-system, Segoe UI, sans-serif, Noto Color Emoji"


def _base_layout(fig: go.Figure, height: int, legend: bool) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=36, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=13, color=INK_2),
        title=dict(font=dict(size=14, color=INK), x=0, xanchor="left", y=0.98),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=12, color=INK_2),
                    bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor="#d3d8e2", font=dict(family=FONT, size=13, color=INK)),
        bargap=0.28,
        bargroupgap=0.08,
        barcornerradius=4,
    )
    fig.update_xaxes(showgrid=False, linecolor=AXIS, tickfont=dict(color=MUTED, size=12), title_font=dict(color=MUTED, size=12),
                     automargin=True)
    fig.update_yaxes(gridcolor=GRID, gridwidth=1, zeroline=False, linecolor=AXIS, tickfont=dict(color=MUTED, size=12),
                     title_font=dict(color=MUTED, size=12), automargin=True)
    return fig


def _mixed_scales(chart: Chart) -> bool:
    peaks = [max((abs(v) for v in s.values), default=0) for s in chart.series]
    peaks = [p for p in peaks if p > 0]
    return len(peaks) >= 2 and max(peaks) / min(peaks) > 3


def _bar(fig, chart: Chart, s, i, horizontal: bool, row=None, col=None, show_text=True):
    color = PALETTE[i % len(PALETTE)]
    labels, values = chart.labels[: len(s.values)], s.values
    trace = go.Bar(
        x=values if horizontal else labels,
        y=labels if horizontal else values,
        orientation="h" if horizontal else "v",
        name=s.name,
        marker=dict(color=color, line=dict(color=SURFACE, width=2)),
        text=[f"{v:,.2f}".rstrip("0").rstrip(".") for v in values] if show_text else None,
        textposition="outside",
        textfont=dict(color=INK_2, size=11),
        cliponaxis=False,
        hovertemplate=f"<b>%{{{'y' if horizontal else 'x'}}}</b><br>{s.name}: %{{{'x' if horizontal else 'y'}:,.2f}}<extra></extra>",
    )
    if row:
        fig.add_trace(trace, row=row, col=col)
    else:
        fig.add_trace(trace)


def build_figure(chart: Chart, height: int = 340) -> go.Figure | None:
    if not chart or not chart.labels or not chart.series:
        return None
    kind = chart.type
    series = chart.series[:6]

    if kind in ("pie", "donut"):
        s = series[0]
        labels, values = chart.labels[:6], s.values[:6]
        fig = go.Figure(go.Pie(
            labels=labels, values=values, hole=0.62 if kind == "donut" else 0,
            marker=dict(colors=PALETTE[: len(labels)], line=dict(color=SURFACE, width=2)),
            textinfo="percent", textfont=dict(color="white", size=12), sort=False,
            hovertemplate="<b>%{label}</b><br>%{value:,.2f} (%{percent})<extra></extra>",
        ))
        fig.update_layout(title_text=chart.title)
        return _base_layout(fig, height, legend=True).update_layout(
            legend=dict(orientation="v", x=1.0, xanchor="left", y=0.5, yanchor="middle"))

    longest = max(len(l) for l in chart.labels)
    # Long category names read badly as rotated ticks — lay them out horizontally instead
    horizontal = kind == "horizontal_bar" or (kind in ("bar", "grouped_bar") and (longest > 20 or (longest > 12 and len(chart.labels) >= 3)))

    if kind in ("bar", "horizontal_bar", "grouped_bar") and len(series) > 1 and _mixed_scales(chart):
        # Small multiples: one panel per measure, shared categories, independent scales
        fig = make_subplots(rows=1, cols=len(series), subplot_titles=[s.name for s in series], horizontal_spacing=0.12,
                            shared_yaxes=True)
        for i, s in enumerate(series):
            _bar(fig, chart, s, i, horizontal=True, row=1, col=i + 1)
        fig.update_annotations(font=dict(size=12.5, color=INK_2))
        fig.update_layout(title_text=chart.title)
        fig.update_yaxes(autorange="reversed")
        fig = _base_layout(fig, max(height, 34 * len(chart.labels) + 90), legend=False)
        fig.update_xaxes(showgrid=True, gridcolor=GRID, showticklabels=False)
        fig.update_yaxes(showgrid=False)
        return fig

    fig = go.Figure()
    if kind == "line":
        for i, s in enumerate(series):
            color = PALETTE[i % len(PALETTE)]
            fig.add_trace(go.Scatter(
                x=chart.labels[: len(s.values)], y=s.values, name=s.name, mode="lines+markers",
                line=dict(color=color, width=2.5), marker=dict(size=9, color=color, line=dict(color=SURFACE, width=2)),
                hovertemplate=f"<b>%{{x}}</b><br>{s.name}: %{{y:,.2f}}<extra></extra>",
            ))
        fig.update_layout(hovermode="x unified")
    else:
        for i, s in enumerate(series):
            _bar(fig, chart, s, i, horizontal, show_text=len(series) <= 2)
        fig.update_layout(barmode="group")
        if horizontal:
            fig.update_yaxes(autorange="reversed", showgrid=False)
            fig.update_xaxes(showgrid=True, gridcolor=GRID)
            height = max(height, 30 * len(chart.labels) + 80)

    fig.update_layout(title_text=chart.title)
    if horizontal:  # value axis is x: label it with the measure, categories need no title
        fig.update_xaxes(title_text=chart.y_label or None)
    else:
        fig.update_xaxes(title_text=chart.x_label or None)
        fig.update_yaxes(title_text=chart.y_label or None)
    return _base_layout(fig, height, legend=len(series) > 1)
