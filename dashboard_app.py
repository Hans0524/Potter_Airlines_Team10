"""Potter Airlines interactive pricing dashboard (optional extension).

Run from the project folder:
    uv run streamlit run dashboard_app.py

Every fare on this page is recomputed live by pricing_batch.price_flights(),
the same function the CLI uses. The database is opened read-only, so the
dashboard can never change flights_2.db. Book a seat in main.py, then refresh
this page, and the new fare shows up.
"""
import math
import sqlite3
from pathlib import Path

import sys
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit import runtime
from streamlit.web import cli

import pricing
import pricing_batch

if __name__ == "__main__" and not runtime.exists():
    sys.argv = ["streamlit", "run", __file__]
    sys.exit(cli.main())

DB_PATH = Path(__file__).resolve().parent / "flights_2.db"

# ---------------------------------------------------------------------------
# Part 1: theme
# One colour per class, fixed by name so a filter never repaints a class.
# These three were checked for colour-blind separation on the navy surface.
# ---------------------------------------------------------------------------
CLASS_ORDER = ["Economy", "Premium", "Business"]
CLASS_COLORS = {"Economy": "#3987e5", "Premium": "#d55181", "Business": "#c98500"}

SURFACE = "#16233a"      # card / chart background
GRID = "#243452"         # hairline grid, one step off the surface
TEXT = "#ffffff"
TEXT_2 = "#c3c2b7"
MUTED = "#8b96a8"
GOLD = "#c98500"
BACKGROUND_DARK = "#0f1a2b"  # page background, also used for text on light fills
BAR_NEUTRAL = "#5d7093"  # waterfall factor steps
INDEX_BAR = "#7f93b5"    # fare-index bars (one series, so one colour)

# Single-hue blue ramp for magnitude on the 3D surface (dark = cheap, light = expensive)
SURFACE_SCALE = [[0.0, "#104281"], [0.35, "#2a78d6"], [0.7, "#86b6ef"], [1.0, "#e6f0fd"]]

st.set_page_config(page_title="Potter Airlines Dashboard", page_icon="✈️", layout="wide")

st.markdown(
    f"""
    <style>
    .block-container {{ padding-top: 2rem; max-width: 1400px; }}
    div[data-testid="stMetric"] {{
        background: {SURFACE};
        border: 1px solid rgba(255,255,255,0.08);
        border-top: 2px solid {GOLD};
        border-radius: 12px;
        padding: 16px 20px;
    }}
    div[data-testid="stMetricLabel"] p {{ color: {TEXT_2}; font-size: 0.85rem; }}
    div[data-testid="stPlotlyChart"] {{ border-radius: 12px; overflow: hidden; }}
    h1, h2, h3 {{ letter-spacing: -0.01em; }}
    .subtle {{ color: {TEXT_2}; font-size: 1rem; margin-top: -0.6rem; }}
    </style>
    """,
    unsafe_allow_html=True,
)


def style(fig, height=380, title=None):
    """Apply the dashboard look to any Plotly figure."""
    fig.update_layout(
        height=height,
        title=dict(text=title, font=dict(size=15, color=TEXT), x=0.02, y=0.96) if title else None,
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(color=TEXT_2, size=12),
        margin=dict(l=56, r=24, t=56 if title else 24, b=48),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_2)),
        hoverlabel=dict(bgcolor="#0f1a2b", bordercolor=GRID, font=dict(color=TEXT)),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(color=MUTED))
    return fig


def show(fig):
    st.plotly_chart(fig, theme=None, config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# Part 2: data - read the stored inputs, then price them live
# ---------------------------------------------------------------------------
def load_priced_flights():
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)   # read-only
    try:
        flights = pd.read_sql_query("SELECT * FROM flights", conn)
    finally:
        conn.close()
    priced = pricing_batch.price_flights(flights)
    priced["departure"] = pd.to_datetime(priced["departure_date"])
    # Fare index: how many times its own base fare a flight costs, with the
    # route (base_fare) and class (class_factor) taken out. Without this, the
    # 10x spread in base fares between routes hides every other factor.
    priced["fare_index"] = priced["final_price"] / (priced["base_fare"] * priced["class_factor"])
    return priced


priced = load_priced_flights()

# ---------------------------------------------------------------------------
# Part 3: header and filters (one row above all charts)
# ---------------------------------------------------------------------------
st.title("✈️ Potter Airlines · Pricing Dashboard")
st.markdown(
    '<p class="subtle">Every fare below is recomputed live from <code>flights_2.db</code> '
    "by <code>pricing_batch.price_flights()</code> — the same engine the CLI uses.</p>",
    unsafe_allow_html=True,
)

f1, f2, f3 = st.columns([2, 1.3, 2])
routes = f1.multiselect("Route", sorted(priced["route"].unique()), placeholder="All routes")
classes = f2.multiselect("Class", CLASS_ORDER, placeholder="All classes")
first_day = priced["departure"].min().date()
last_day = priced["departure"].max().date()
date_range = f3.slider("Departure date", first_day, last_day, (first_day, last_day), format="MMM D, YYYY")

view = priced
if routes:
    view = view[view["route"].isin(routes)]
if classes:
    view = view[view["fare_class"].isin(classes)]
view = view[view["departure"].dt.date.between(date_range[0], date_range[1])]

if view.empty:
    st.warning("No flights match these filters.")
    st.stop()

visible_classes = [c for c in CLASS_ORDER if c in set(view["fare_class"])]

# ---------------------------------------------------------------------------
# Part 4: headline numbers
# ---------------------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Flights", f"{len(view):,}")
k2.metric("Median fare", f"${view['final_price'].median():,.2f}")
k3.metric("Highest fare", f"${view['final_price'].max():,.2f}")
at_cap = int((view["raw_price"] > pricing.FARE_CAP).sum())
k4.metric(f"Held at ${pricing.FARE_CAP:,.0f} cap", f"{at_cap:,}",
          help="Flights whose formula price exceeded the cap and was clipped to it.")

st.write("")

# ---------------------------------------------------------------------------
# Part 5: 3D pricing surface
# A grid of hypothetical flights (days x load factor) priced in ONE vectorized
# call, so the shape is exactly what pricing_batch produces.
# ---------------------------------------------------------------------------
st.subheader("The pricing surface")
st.markdown('<p class="subtle">Drag to rotate, scroll to zoom. The two cliffs are the 7-day and '
            "21-day time bands; the slope across is the capacity factor.</p>", unsafe_allow_html=True)

# One typical flight: median base fare and median popularity of all flights,
# Economy, March (seasonal factor 1.00). Only the four inputs below change.
t1, t2, _ = st.columns([1, 1, 4])
ref_weekend = t1.toggle("Weekend")
ref_holiday = t2.toggle("Holiday")

base_fare = float(priced["base_fare"].median())
popularity = float(priced["route_popularity"].median())
ref_class = "Economy"

days_axis = list(range(1, 46))
load_axis = [round(x * 0.05, 2) for x in range(0, 21)]
grid = pd.DataFrame([(d, lf) for lf in load_axis for d in days_axis],
                    columns=["days_to_departure", "current_load_factor"])
grid["flight_id"] = [f"GRID{i}" for i in range(len(grid))]
grid["base_fare"] = base_fare
grid["route_popularity"] = popularity
grid["is_weekend"] = int(ref_weekend)
grid["is_holiday"] = int(ref_holiday)
grid["departure_date"] = "2026-03-10"      # March: seasonal factor 1.00
grid["fare_class"] = ref_class
grid_priced = pricing_batch.price_flights(grid)

z = grid_priced.pivot(index="current_load_factor", columns="days_to_departure",
                      values="final_price").values

surface = go.Figure(go.Surface(
    x=days_axis, y=load_axis, z=z,
    colorscale=SURFACE_SCALE, cmin=z.min(), cmax=max(z.max(), z.min() + 1),
    showscale=False,
    lighting=dict(ambient=0.55, diffuse=0.8, specular=0.25, roughness=0.6, fresnel=0.2),
    lightposition=dict(x=-1000, y=-2000, z=3000),
    contours=dict(z=dict(show=True, usecolormap=True, project_z=True, width=1)),
    hovertemplate="%{x} days out<br>%{y:.0%} sold<br><b>$%{z:,.2f}</b><extra></extra>",
))
axis_style = dict(backgroundcolor=SURFACE, gridcolor=GRID, zerolinecolor=GRID,
                  showbackground=True, tickfont=dict(color=MUTED), title_font=dict(color=TEXT_2))
surface.update_layout(
    height=520, paper_bgcolor=SURFACE, margin=dict(l=0, r=0, t=10, b=0),
    font=dict(color=TEXT_2),
    scene=dict(
        xaxis=dict(title="Days to departure", autorange="reversed", **axis_style),
        yaxis=dict(title="Load factor", tickformat=".0%", **axis_style),
        zaxis=dict(title="Fare ($)", tickprefix="$", **axis_style),
        camera=dict(eye=dict(x=1.35, y=-1.3, z=0.75)),
        aspectratio=dict(x=1.5, y=1, z=0.7),
    ),
    hoverlabel=dict(bgcolor="#0f1a2b", bordercolor=GRID, font=dict(color=TEXT)),
)
show(surface)
# "\\$" stops Streamlit from reading a pair of dollar signs as a maths formula
st.caption(f"A typical flight: median base fare \\${base_fare:,.0f} · median route popularity "
           f"{popularity:.2f} · Economy · March departure.")

st.write("")

# ---------------------------------------------------------------------------
# Part 6: how each input moves the fare, on the real flights
# Real fares are dominated by the route's base fare, so these charts use the
# fare index (final price / (base fare x class factor)) and take the median
# per group.
# ---------------------------------------------------------------------------
st.subheader("How inputs move the fare")
st.markdown('<p class="subtle">Fare index = final fare ÷ (base fare × class factor): how many times '
            "its own base fare a flight costs, with route and class taken out.</p>",
            unsafe_allow_html=True)


def index_bars(groups, x_title, title):
    """One bar per group: the median fare index, labelled on the bar."""
    summary = view.groupby(groups, observed=True).agg(
        index=("fare_index", "median"), flights=("fare_index", "size"),
        fare=("final_price", "median")).reset_index()
    fig = go.Figure(go.Bar(
        x=summary[groups.name].astype(str), y=summary["index"], marker_color=INDEX_BAR,
        text=[f"{v:.2f}×" for v in summary["index"]], textposition="outside",
        textfont=dict(color=TEXT),
        customdata=summary[["flights", "fare"]],
        hovertemplate="%{x}<br>Median index %{y:.2f}×<br>%{customdata[0]} flights"
                      "<br>Median fare $%{customdata[1]:,.2f}<extra></extra>",
    ))
    style(fig, title=title)
    fig.update_layout(barcornerradius=4, bargap=0.35)
    fig.update_xaxes(title=x_title)
    fig.update_yaxes(title="Median fare index", ticksuffix="×", rangemode="tozero",
                     range=[0, summary["index"].max() * 1.2])
    return fig


days_group = pd.cut(view["days_to_departure"], [0, 7, 21, 60, 180, 366],
                    labels=["1–7", "8–21", "22–60", "61–180", "181–365"]).rename("days")
load_group = pd.cut(view["current_load_factor"], [0, 0.2, 0.4, 0.6, 0.8, 1.0], include_lowest=True,
                    labels=["0–20%", "20–40%", "40–60%", "60–80%", "80–100%"]).rename("load")

left, right = st.columns(2)
with left:
    show(index_bars(days_group, "Days to departure", "Fare index by days to departure"))
with right:
    show(index_bars(load_group, "Load factor", "Fare index by load factor"))

left, right = st.columns(2)
with left:
    box = go.Figure()
    for fare_class in visible_classes:
        rows = view[view["fare_class"] == fare_class]
        box.add_trace(go.Box(y=rows["final_price"], name=fare_class, marker_color=CLASS_COLORS[fare_class],
                             line=dict(width=2), boxmean=True, showlegend=False,
                             hovertemplate="$%{y:,.2f}<extra>" + fare_class + "</extra>"))
    style(box, title="Fare by class")
    box.add_hline(y=pricing.FARE_CAP, line=dict(color=GOLD, width=1))
    box.add_annotation(x=1, xref="paper", y=pricing.FARE_CAP, text=f"Cap ${pricing.FARE_CAP:,.0f}",
                       showarrow=False, xanchor="right", yanchor="bottom", font=dict(color=GOLD, size=11))
    box.update_yaxes(title="Fare", tickprefix="$")
    show(box)
with right:
    # all classes pooled into one line: the index already removes the class factor
    monthly = (view.assign(month=view["departure"].dt.to_period("M").dt.to_timestamp())
               .groupby("month", as_index=False)
               .agg(index=("fare_index", "median"), flights=("fare_index", "size")))
    trend = go.Figure(go.Scatter(
        x=monthly["month"], y=monthly["index"], mode="lines+markers",
        line=dict(width=2, color=GOLD),
        marker=dict(size=8, color=GOLD, line=dict(width=2, color=SURFACE)),
        customdata=monthly[["flights"]],
        hovertemplate="%{x|%b %Y}<br>Median index %{y:.2f}×<br>%{customdata[0]} flights<extra></extra>",
    ))
    style(trend, title="Fare index by departure month")
    trend.update_xaxes(rangeslider=dict(visible=True, bgcolor="#0f1a2b", bordercolor=GRID, thickness=0.08),
                       tickformat="%b %Y")
    trend.update_yaxes(title="Median fare index", ticksuffix="×")
    show(trend)

st.write("")

# ---------------------------------------------------------------------------
# Part 7: explain one fare, factor by factor
# Same order as pricing.calculate_fare, so the steps multiply out exactly.
# ---------------------------------------------------------------------------
st.subheader("Explain one fare")

ranked = view.sort_values("final_price", ascending=False).set_index("flight_id")


def describe(fid):
    r = ranked.loc[fid]
    return f"{fid} · {r.route} · {r.fare_class} · {r.departure_date} · ${r.final_price:,.2f}"


choice = st.selectbox("Flight (most expensive first)", ranked.index, format_func=describe)
flight = ranked.loc[choice]

steps = [
    ("Time", "time_factor", f"{flight.days_to_departure} days to departure"),
    ("Capacity", "capacity_factor", f"{flight.current_load_factor:.0%} of seats sold"),
    ("Weekend", "weekend_factor", "weekend departure" if flight.is_weekend else "weekday departure"),
    ("Holiday", "holiday_factor", "holiday period" if flight.is_holiday else "not a holiday"),
    ("Seasonal", "seasonal_factor", f"departing {pd.Timestamp(flight.departure_date):%B}"),
    ("Demand", "demand_factor", f"route popularity {flight.route_popularity:.2f}"),
    ("Class", "class_factor", f"{flight.fare_class} class"),
]

labels, measures, amounts, texts = ["Base fare"], ["absolute"], [flight.base_fare], [f"${flight.base_fare:,.2f}"]
running = flight.base_fare
for name, column, _ in steps:
    factor = flight[column]
    change = running * factor - running
    running *= factor
    labels.append(name)
    measures.append("relative")
    amounts.append(change)
    texts.append(f"×{factor:.3f}".rstrip("0").rstrip(".") if factor != 1 else "×1")
if abs(running - flight.final_price) > 0.005:
    labels.append("Fare limit")
    measures.append("relative")
    amounts.append(flight.final_price - running)
    texts.append("capped" if running > pricing.FARE_CAP else "floored")
labels.append("Final fare")
measures.append("total")
amounts.append(0)
texts.append(f"${flight.final_price:,.2f}")

water = go.Figure(go.Waterfall(
    x=labels, measure=measures, y=amounts, text=texts, textposition="outside",
    textfont=dict(color=TEXT),
    increasing=dict(marker=dict(color=BAR_NEUTRAL)),
    decreasing=dict(marker=dict(color=BAR_NEUTRAL)),
    totals=dict(marker=dict(color=GOLD)),
    connector=dict(line=dict(color=GRID, width=1)),
    hovertemplate="%{x}: %{delta:+$,.2f}<extra></extra>",
))
style(water, height=420)
water.update_yaxes(title="Fare", tickprefix="$", range=[0, max(running, flight.final_price) * 1.15])

left, right = st.columns([3, 2])
with left:
    show(water)
with right:
    table = pd.DataFrame({
        "Factor": [name for name, _, _ in steps],
        "Value": [round(float(flight[col]), 3) for _, col, _ in steps],
        "Why": [why for _, _, why in steps],
    })
    st.dataframe(table, hide_index=True, height=300)
    st.markdown(
        f"**Formula price** \\${flight.raw_price:,.2f} → **charged** \\${flight.final_price:,.2f}"
        + (f"  \nThe formula exceeded the \\${pricing.FARE_CAP:,.0f} cap, so the fare is held at the cap."
           if flight.raw_price > pricing.FARE_CAP else "")
    )

st.write("")

# ---------------------------------------------------------------------------
# Part 8: what is stored in the flights table (hub-and-spoke map)
# Positions are worked out with cos/sin: four group hubs on an inner ring,
# each group's columns fanned out on an outer ring.
# ---------------------------------------------------------------------------
st.subheader("What the flights table stores")
st.markdown('<p class="subtle">19 columns in <code>flights_2.db</code>, grouped by what the system does '
            "with them. The 8 gold columns are the only ones pricing.py reads.</p>", unsafe_allow_html=True)

TABLE_GROUPS = {   # group: (colour, columns) - pricing on the right, the rest around it
    "Pricing inputs": ("#c98500", ["base_fare", "days_to_departure", "current_load_factor",
                                   "route_popularity", "is_weekend", "is_holiday",
                                   "departure_date", "fare_class"]),
    "Seat inventory": ("#d55181", ["seats_remaining", "class_capacity", "capacity"]),
    "Identity": ("#3987e5", ["flight_id", "route", "origin", "destination"]),
    "Stored, for future analysis": ("#8b96a8", ["day_of_week", "season", "departure_hour",
                                       "historical_avg_route_demand"]),
}
X_STRETCH = 1.7            # the chart is wide, so spread the rings sideways


def ring_point(angle, radius):
    # minus sign: angles increase clockwise, so the groups go right -> bottom -> left -> top
    return X_STRETCH * radius * math.cos(angle), -radius * math.sin(angle)


def label_side(angle):
    """Put each column label on the outside of its ball."""
    if math.cos(angle) > 0.4:
        return "middle right"
    if math.cos(angle) < -0.4:
        return "middle left"
    return "bottom center" if math.sin(angle) > 0 else "top center"


table_map = go.Figure()
slots = sum(len(cols) + 1 for _, cols in TABLE_GROUPS.values())   # +1 leaves a gap between groups
start = -2 * math.pi * (len(TABLE_GROUPS["Pricing inputs"][1]) + 1) / slots / 2   # centre pricing at 0°

for group, (color, columns) in TABLE_GROUPS.items():
    span = 2 * math.pi * (len(columns) + 1) / slots
    hub_x, hub_y = ring_point(start + span / 2, 0.5)
    angles = [start + span * (i + 1) / (len(columns) + 1) for i in range(len(columns))]
    start += span

    # lines: centre -> hub -> each column
    table_map.add_trace(go.Scatter(x=[0, hub_x], y=[0, hub_y], mode="lines",
                                   line=dict(color=color, width=4), hoverinfo="skip"))
    # above and below the centre, labels run sideways and would touch:
    # push every second ball further out so neighbouring labels sit at different heights
    radii = [1.0 + (0.2 if i % 2 and label_side(a).endswith("center") else 0) for i, a in enumerate(angles)]
    for a, r in zip(angles, radii):
        x, y = ring_point(a, r)
        table_map.add_trace(go.Scatter(x=[hub_x, x], y=[hub_y, y], mode="lines",
                                       line=dict(color=color, width=2), hoverinfo="skip"))

    # column balls with their names
    points = [ring_point(a, r) for a, r in zip(angles, radii)]
    table_map.add_trace(go.Scatter(
        x=[p[0] for p in points], y=[p[1] for p in points], mode="markers+text",
        text=columns, textposition=[label_side(a) for a in angles],
        textfont=dict(size=17, color=TEXT),
        marker=dict(size=22, color=color, line=dict(width=2, color=SURFACE)),
        hovertemplate="%{text}<extra>" + group + "</extra>",
    ))

    # group hub, labelled in a box so the text stays readable over the lines
    table_map.add_trace(go.Scatter(x=[hub_x], y=[hub_y], mode="markers", hoverinfo="skip",
                                   marker=dict(size=44, color=color, line=dict(width=3, color=SURFACE))))
    table_map.add_annotation(x=hub_x, y=hub_y, yshift=-38, text=f"<b>{group}</b> ({len(columns)})",
                             showarrow=False, font=dict(size=19, color=TEXT),
                             bgcolor=SURFACE, bordercolor=color, borderwidth=2, borderpad=5)

# the table itself, in the middle
table_map.add_trace(go.Scatter(x=[0], y=[0], mode="markers+text", text=["<b>flights</b>"],
                               textfont=dict(size=20, color=BACKGROUND_DARK), hoverinfo="skip",
                               marker=dict(size=90, color="#e6f0fd", line=dict(width=4, color=GOLD))))

style(table_map, height=720)
table_map.update_layout(showlegend=False, margin=dict(l=20, r=20, t=20, b=20), dragmode=False)
table_map.update_xaxes(visible=False, range=[-X_STRETCH * 1.75, X_STRETCH * 1.75], fixedrange=True)
table_map.update_yaxes(visible=False, range=[-1.45, 1.45], fixedrange=True)
show(table_map)


