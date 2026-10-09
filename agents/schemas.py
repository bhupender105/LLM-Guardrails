"""AnswerCard — the structured output both agents return and the UI renders.

Kept deliberately flat/typed (no free-form dicts) so Gemini's structured output
handles it reliably.
"""
from typing import Literal

from pydantic import BaseModel, Field


class KPI(BaseModel):
    label: str = Field(description="Short metric name, e.g. 'Placement rate'")
    value: str = Field(description="Formatted value, e.g. '82.4%' or '₹7.4 LPA'")
    icon: str = Field(default="📌", description="One emoji that fits the metric")


class Series(BaseModel):
    name: str = Field(description="Series name, e.g. 'Avg CTC (LPA)'")
    values: list[float] = Field(description="One numeric value per label, same order as chart.labels")


class Chart(BaseModel):
    type: Literal["bar", "horizontal_bar", "grouped_bar", "line", "pie", "donut"] = Field(
        description="bar/horizontal_bar for category comparisons, grouped_bar for 2+ series, "
        "line for trends over batch_year/time, pie/donut only for parts of a whole (<= 6 slices)"
    )
    title: str
    labels: list[str] = Field(description="Category labels (x axis / slices)")
    series: list[Series] = Field(description="1+ series; pie/donut use exactly one")
    x_label: str = ""
    y_label: str = ""


class Table(BaseModel):
    columns: list[str]
    rows: list[list[str]] = Field(description="Max 15 rows, values as display strings")


class AnswerCard(BaseModel):
    title: str = Field(description="Card heading, 3-8 words")
    emoji: str = Field(description="One emoji representing the answer topic")
    status: Literal["info", "success", "warning", "danger"] = Field(
        default="info", description="success for completed actions, warning/danger for risky or failed ones"
    )
    summary: str = Field(description="1-3 sentence direct answer in plain language (markdown allowed)")
    kpis: list[KPI] = Field(default_factory=list, description="0-4 headline numbers")
    chart: Chart | None = Field(default=None, description="Include when the answer compares numbers across categories or time")
    table: Table | None = Field(default=None, description="Include for record lists or detailed breakdowns")
    insights: list[str] = Field(default_factory=list, description="0-4 short takeaways, each starting with an emoji")
    sql_used: str = Field(default="", description="The final SQL statement(s) you ran, verbatim")
