"""Strategies Dashboard — public view, display-only.

All strategy logic lives in a separate private repo. This app only reads
pre-computed JSON in ./public_data/ and renders it.
"""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DATA = ROOT / "public_data"

st.set_page_config(page_title="Strategies", page_icon="📈", layout="wide")


def load_json(path: Path):
    with open(path) as f:
        return json.load(f)


def fmt_pct(x, decimals: int = 1, color: bool = False) -> str:
    if x is None:
        return "—"
    s = f"{x:+.{decimals}f}%"
    if color:
        c = "#2e7d32" if x >= 0 else "#c62828"
        return f"<span style='color:{c}'>{s}</span>"
    return s


def region_flag(region: str) -> str:
    return {"US": "🇺🇸", "India": "🇮🇳"}.get(region, "🏳️")


def render_landing():
    st.title("📈 Strategies")
    st.caption("Live-tracked long-only momentum strategies. "
               "Click a row to view holdings, equity curve, and rebalance history.")

    idx = load_json(PUBLIC_DATA / "strategies.json")
    strategies = idx["strategies"]

    # Region filter
    regions = sorted({s["region"] for s in strategies})
    region_pick = st.radio(
        "Region", ["All"] + regions,
        horizontal=True, label_visibility="collapsed",
    )
    filtered = strategies if region_pick == "All" else [s for s in strategies if s["region"] == region_pick]

    if not filtered:
        st.info("No strategies in this region.")
        return

    rows = []
    for s in filtered:
        sm = s["summary"]
        rbp = {r["period"]: r["excess_pp"] for r in sm.get("returns_by_period") or []}
        rows.append({
            "": region_flag(s["region"]),
            "Strategy": s["name"],
            "Benchmark": s["benchmark_label"],
            "CAGR": sm["cagr_pct"],
            "Sharpe": sm["sharpe"],
            "MaxDD": sm["max_dd_pct"],
            "YTD": sm["ytd_return_pct"] if sm["ytd_return_pct"] is not None else None,
            "1Y excess vs bench": rbp.get("1Y"),
            f"Today ({filtered[0].get('last_data_date', '')})": sm["today_return_pct"],
            "_id": s["id"],
        })
    df = pd.DataFrame(rows)

    event = st.dataframe(
        df.drop(columns=["_id"]),
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "": st.column_config.TextColumn(width="small"),
            "Strategy": st.column_config.TextColumn(width="large"),
            "Benchmark": st.column_config.TextColumn(width="small"),
            "CAGR": st.column_config.NumberColumn(format="%.2f%%", width="small"),
            "Sharpe": st.column_config.NumberColumn(format="%.2f", width="small"),
            "MaxDD": st.column_config.NumberColumn(format="%.1f%%", width="small"),
            "YTD": st.column_config.NumberColumn(format="%+.2f%%", width="small"),
            "1Y excess vs bench": st.column_config.NumberColumn(format="%+.2f pp", width="small"),
        },
    )

    # Row selection → open the detail view
    if event.selection and event.selection["rows"]:
        sid = rows[event.selection["rows"][0]]["_id"]
        st.query_params["strategy"] = sid
        st.rerun()

    # Quick highlights ribbon
    by_cagr = max(filtered, key=lambda s: s["summary"]["cagr_pct"])
    by_sharpe = max(filtered, key=lambda s: s["summary"]["sharpe"])
    by_mdd = max(filtered, key=lambda s: s["summary"]["max_dd_pct"])  # least negative = best
    by_1y = max(
        filtered,
        key=lambda s: (next((r["excess_pp"] for r in s["summary"].get("returns_by_period") or [] if r["period"] == "1Y"), -1e9)),
    )
    cols = st.columns(4)
    cols[0].caption(f"🏆 Best CAGR · **{by_cagr['name']}** · {by_cagr['summary']['cagr_pct']:.1f}%")
    cols[1].caption(f"⚖️ Best Sharpe · **{by_sharpe['name']}** · {by_sharpe['summary']['sharpe']:.2f}")
    cols[2].caption(f"🛡️ Best MaxDD · **{by_mdd['name']}** · {by_mdd['summary']['max_dd_pct']:.1f}%")
    rbp_1y = next((r["excess_pp"] for r in by_1y["summary"].get("returns_by_period") or [] if r["period"] == "1Y"), None)
    cols[3].caption(f"📈 Best 1Y excess · **{by_1y['name']}** · {rbp_1y:+.2f}pp" if rbp_1y is not None else "")

    st.caption(f"Last updated: {strategies[0]['last_updated']} · {len(filtered)} strategies shown")


def render_strategy_detail(strategy_id: str):
    meta = load_json(PUBLIC_DATA / strategy_id / "meta.json")
    nav = load_json(PUBLIC_DATA / strategy_id / "nav.json")
    holdings = load_json(PUBLIC_DATA / strategy_id / "holdings.json")

    if st.button("← Back to all strategies"):
        st.query_params.clear()
        st.rerun()

    st.title(f"{region_flag(meta['region'])} {meta['name']}")
    st.caption(meta["description"])

    sm = meta["summary"]
    cols = st.columns(6)
    cols[0].metric("Total return", f"{sm['total_return_pct']:+.1f}%",
                   delta=f"vs bench: {(sm['total_return_pct'] - (sm['benchmark_total_return_pct'] or 0)):+.1f}pp" if sm['benchmark_total_return_pct'] is not None else None)
    cols[1].metric("CAGR", f"{sm['cagr_pct']:.1f}%",
                   delta=f"{sm['vs_benchmark_cagr_pct']:+.1f}pp vs bench" if sm['vs_benchmark_cagr_pct'] is not None else None)
    cols[2].metric("Sharpe", f"{sm['sharpe']:.2f}")
    cols[3].metric("Max DD", f"{sm['max_dd_pct']:.1f}%")
    cols[4].metric("YTD", f"{sm['ytd_return_pct']:+.1f}%" if sm['ytd_return_pct'] is not None else "—")
    cols[5].metric(f"Last close ({meta.get('last_data_date', '')})",
                   f"{sm['today_return_pct']:+.2f}%" if sm['today_return_pct'] is not None else "—",
                   delta=f"bench {sm['today_benchmark_pct']:+.2f}%" if sm['today_benchmark_pct'] is not None else None,
                   delta_color="off")

    # Returns by period
    rbp = sm.get("returns_by_period") or []
    if rbp:
        st.subheader("Returns by period")
        df_rbp = pd.DataFrame(rbp).rename(columns={
            "period": "Period",
            "strategy_pct": "Strategy",
            "benchmark_pct": meta["benchmark_label"],
            "excess_pp": "Excess (pp)",
        })
        for col in ("Strategy", meta["benchmark_label"], "Excess (pp)"):
            df_rbp[col] = df_rbp[col].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "—")
        st.dataframe(df_rbp, hide_index=True, use_container_width=True)

    # Equity curve with period selector
    st.subheader("Equity curve")
    periods = {"1W": 5, "1M": 21, "3M": 63, "6M": 126, "1Y": 252, "All": None}
    selected = st.radio(
        "Period", list(periods.keys()),
        index=len(periods) - 1, horizontal=True,
        key=f"ec_period_{strategy_id}",
        label_visibility="collapsed",
    )
    df_nav = pd.DataFrame({
        "date": pd.to_datetime(nav["dates"]),
        meta["name"]: nav["strategy_nav"],
        meta["benchmark_label"]: nav["benchmark_nav"],
    }).set_index("date")

    n_days = periods[selected]
    if n_days is not None and len(df_nav) > n_days + 1:
        df_nav = df_nav.iloc[-(n_days + 1):]
        # Rebase to window start and convert to cumulative % return so the y-axis
        # is in percentage points (e.g. -10% vs -5% is visually clear).
        first_row = df_nav.iloc[0]
        df_nav = (df_nav.div(first_row.where(first_row != 0)) - 1) * 100

    st.line_chart(df_nav, height=320,
                  y_label="% return" if n_days is not None else "NAV (1.0 = inception)")

    if n_days is not None:
        last_row = df_nav.iloc[-1]
        s_ret = float(last_row[meta["name"]])
        b_ret = float(last_row[meta["benchmark_label"]]) if pd.notna(last_row[meta["benchmark_label"]]) else None
        caption = f"{selected} window: strategy {s_ret:+.2f}%"
        if b_ret is not None:
            caption += f"  ·  benchmark {b_ret:+.2f}%  ·  excess {(s_ret - b_ret):+.2f}pp"
        st.caption(caption)

    # Holdings
    st.subheader(f"Current holdings — as of {holdings['as_of']}")
    rows = holdings["holdings"]
    if rows:
        df_h = pd.DataFrame(rows)
        df_h = df_h.rename(columns={
            "ticker": "Ticker", "weight": "Weight",
            "entry_date": "Entry date", "entry_price": "Entry",
            "current_price": "Current", "gain_since_entry_pct": "Gain since entry",
            "today_change_pct": "Today",
        })
        df_h["Weight"] = df_h["Weight"].apply(lambda w: f"{w * 100:.1f}%")
        # format pct columns
        for col in ("Gain since entry", "Today"):
            df_h[col] = df_h[col].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "—")
        for col in ("Entry", "Current"):
            df_h[col] = df_h[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "—")
        st.dataframe(df_h, hide_index=True, use_container_width=True)
    else:
        st.info("No current holdings.")

    st.caption(f"Inception: {meta['inception']} · Last data: {meta['last_data_date']} · Updated: {meta['last_updated']}")


def main():
    strategy_id = st.query_params.get("strategy")
    if strategy_id and (PUBLIC_DATA / strategy_id).exists():
        render_strategy_detail(strategy_id)
    else:
        render_landing()


if __name__ == "__main__":
    main()
