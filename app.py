import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime
from database import (
    init_db,
    ping,
    add_asset, update_asset, delete_asset, get_assets,
    add_transaction, update_transaction, delete_transaction, get_transactions,
    add_bond, update_bond, delete_bond, get_bonds,
)
from prices import fetch_prices, fetch_fx_rates, to_pln
from bonds_data import parse_symbol, fetch_bond_params, fetch_nbp_rate, project_maturity_value, calculate_bond_at_date

ping()
init_db()

st.set_page_config(page_title="Portfolio Tracker", layout="wide")
st.title("Portfolio Tracker")

CATEGORIES = ["stock", "etf", "bond", "crypto"]
CURRENCIES = ["USD", "EUR", "PLN", "GBP"]

tab_portfolio, tab_assets, tab_bonds = st.tabs(["Portfel", "Pozycje", "Obligacje"])

# ── TAB: Portfel ──────────────────────────────────────────────────────────────
with tab_portfolio:
    assets = get_assets()
    transactions = get_transactions()
    bonds = get_bonds()

    # Build API symbols and fetch prices
    api_symbols = []
    for asset in assets:
        buy_cur = asset["currency"]
        price_cur = asset["price_currency"] or buy_cur
        sym = f"{asset['ticker']}/{price_cur}" if asset["category"] == "crypto" else asset["ticker"]
        txns = [t for t in transactions if t["asset_id"] == asset["id"]]
        if sum(t["quantity"] for t in txns) > 0:
            api_symbols.append(sym)

    prices = fetch_prices(tuple(api_symbols)) if api_symbols else {}
    fx_rates = fetch_fx_rates()

    rows = []
    for asset in assets:
        buy_cur = asset["currency"]
        price_cur = asset["price_currency"] or buy_cur
        sym = f"{asset['ticker']}/{price_cur}" if asset["category"] == "crypto" else asset["ticker"]

        txns = [t for t in transactions if t["asset_id"] == asset["id"]]
        qty = sum(t["quantity"] for t in txns)
        invested_buy = sum(t["quantity"] * t["buy_price"] for t in txns)
        if qty == 0:
            continue

        invested_pln = to_pln(invested_buy, buy_cur, fx_rates)
        current_price = prices.get(sym)

        if current_price is not None:
            current_value_pln = to_pln(current_price * qty, price_cur, fx_rates)
        else:
            current_value_pln = None

        gain_pln = round(current_value_pln - invested_pln, 2) if (current_value_pln and invested_pln) else None
        gain_pct = round(gain_pln / invested_pln * 100, 2) if (gain_pln is not None and invested_pln) else None

        rows.append({
            "Nazwa": asset["name"],
            "Ticker": asset["ticker"],
            "Kategoria": asset["category"],
            "Waluta": buy_cur,
            "Wpłacono": round(invested_buy, 2),
            "Wpłacono (PLN)": round(invested_pln, 2) if invested_pln else None,
            "Wartość akt. (PLN)": round(current_value_pln, 2) if current_value_pln else None,
            "Zmiana (PLN)": gain_pln,
            "Zmiana (%)": gain_pct,
            "_invested_pln": invested_pln or 0,
            "_current_value_pln": current_value_pln or 0,
        })

    # Bonds — accrued interest
    today = date.today()
    for b in bonds:
        face = float(b["face_value"])
        coupon_rate = float(b["coupon_rate"])
        buy_date = datetime.strptime(b["buy_date"], "%Y-%m-%d").date()
        maturity_date = datetime.strptime(b["maturity_date"], "%Y-%m-%d").date()
        days_held = (today - buy_date).days
        days_total = (maturity_date - buy_date).days
        fraction = min(days_held / days_total, 1.0) if days_total > 0 else 0
        accrued = round(face * coupon_rate * fraction, 2)
        current_val = round(face + accrued, 2)
        rows.append({
            "Nazwa": b["name"],
            "Ticker": "—",
            "Kategoria": "bond",
            "Waluta": "PLN",
            "Wpłacono": face,
            "Wpłacono (PLN)": face,
            "Wartość akt. (PLN)": current_val,
            "Zmiana (PLN)": accrued,
            "Zmiana (%)": round(accrued / face * 100, 2) if face else 0,
            "_invested_pln": face,
            "_current_value_pln": current_val,
        })

    if not rows:
        st.info("Brak pozycji. Dodaj pierwszą w zakładce Pozycje lub Obligacje.")
    else:
        total_invested_pln = sum(r["_invested_pln"] for r in rows)
        total_current_pln = sum(r["_current_value_pln"] for r in rows)
        rows_priced = [r for r in rows if r["_current_value_pln"]]
        invested_priced_pln = sum(r["_invested_pln"] for r in rows_priced)
        total_gain_pln = total_current_pln - invested_priced_pln if rows_priced else 0

        st.subheader("Podsumowanie (PLN)")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Liczba pozycji", len(rows))
        col2.metric("Zainwestowano", f"{total_invested_pln:,.2f} PLN")
        col3.metric("Wartość aktualna", f"{total_current_pln:,.2f} PLN" if rows_priced else "—")
        col4.metric(
            "Zysk/strata",
            f"{total_gain_pln:+,.2f} PLN" if rows_priced else "—",
            delta=f"{total_gain_pln/invested_priced_pln*100:+.2f}%" if rows_priced and invested_priced_pln else None,
        )

        if fx_rates:
            rate_info = "  ·  ".join(f"1 {cur} = {rate:.4f} PLN" for cur, rate in fx_rates.items() if cur != "PLN")
            st.caption(f"Kursy: {rate_info}")

        display_cols = ["Nazwa", "Ticker", "Kategoria", "Waluta", "Wpłacono", "Wpłacono (PLN)", "Wartość akt. (PLN)", "Zmiana (PLN)", "Zmiana (%)"]
        df = pd.DataFrame(rows)[display_cols]

        def color_change(val):
            if not isinstance(val, (int, float)):
                return ""
            if val > 0:
                return "color: #2e7d32; font-weight: bold"
            if val < 0:
                return "color: #c62828; font-weight: bold"
            return ""

        styled = df.style.map(color_change, subset=["Zmiana (PLN)", "Zmiana (%)"])
        st.subheader("Wszystkie pozycje")
        st.dataframe(styled, use_container_width=True, hide_index=True)

        st.subheader("Podział portfela (wartość aktualna)")
        col_pie1, col_pie2 = st.columns(2)

        # By category
        cat_data = {}
        for r in rows:
            cat_data[r["Kategoria"]] = cat_data.get(r["Kategoria"], 0) + r["_current_value_pln"]
        df_cat = pd.DataFrame(list(cat_data.items()), columns=["Kategoria", "Wartość (PLN)"])
        fig_cat = px.pie(df_cat, values="Wartość (PLN)", names="Kategoria",
                         title="Wg kategorii", hole=0.4)
        fig_cat.update_traces(textposition="outside", textinfo="percent+label",
                              outsidetextfont=dict(size=13))
        fig_cat.update_layout(showlegend=False, height=420,
                              margin=dict(t=40, b=60, l=60, r=60))
        col_pie1.plotly_chart(fig_cat, use_container_width=True)

        asset_data = {r["Nazwa"]: r["_current_value_pln"] for r in rows}
        df_asset = pd.DataFrame(list(asset_data.items()), columns=["Nazwa", "Wartość (PLN)"])
        fig_asset = px.pie(df_asset, values="Wartość (PLN)", names="Nazwa",
                           title="Wg pozycji", hole=0.4)
        fig_asset.update_traces(textposition="outside", textinfo="percent+label",
                                outsidetextfont=dict(size=13))
        fig_asset.update_layout(showlegend=False, height=420,
                                margin=dict(t=40, b=60, l=60, r=60))
        col_pie2.plotly_chart(fig_asset, use_container_width=True)

        st.caption("Ceny i kursy walut odświeżane co 15 min · yfinance")

# ── TAB: Pozycje ──────────────────────────────────────────────────────────────
with tab_assets:
    st.subheader("Dodaj nową pozycję")
    with st.form("add_asset_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            a_name = st.text_input("Nazwa", placeholder="np. Apple Inc.")
            a_ticker = st.text_input("Ticker", placeholder="np. AAPL")
        with col2:
            a_category = st.selectbox("Kategoria", CATEGORIES)
            a_currency = st.selectbox("Waluta zakupu", CURRENCIES, help="W jakiej walucie wpisujesz ceny zakupu")
        a_price_currency = st.selectbox(
            "Waluta notowań (opcjonalne)",
            ["— (tak samo jak zakupu)"] + CURRENCIES,
            help="Wypełnij tylko gdy waluta zakupu ≠ waluta giełdowa. Np. kupujesz ETF w PLN na XTB, ale ETF notowany jest w EUR → waluta zakupu: PLN, waluta notowań: EUR",
        )
        if st.form_submit_button("Dodaj pozycję"):
            if a_name and a_ticker:
                pc = None if a_price_currency.startswith("—") else a_price_currency
                add_asset(a_name, a_category, a_ticker, a_currency, pc)
                st.success(f"Dodano: {a_name} ({a_ticker.upper()})")
                st.rerun()
            else:
                st.error("Podaj nazwę i ticker.")

    st.subheader("Lista pozycji")
    assets = get_assets()
    if not assets:
        st.info("Brak pozycji.")
    else:
        for row in assets:
            txns = [t for t in get_transactions(row["id"])]
            txn_count = len(txns)
            price_cur_label = f" · notowania: {row['price_currency']}" if row["price_currency"] else ""
            with st.expander(f"**{row['name']}** ({row['ticker']}) — {row['category']} · zakup: {row['currency']}{price_cur_label} · {txn_count} zakup{'y' if 1 < txn_count < 5 else 'ów' if txn_count != 1 else ''}"):
                st.markdown("#### Edytuj pozycję")
                with st.form(f"edit_asset_{row['id']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        e_name = st.text_input("Nazwa", value=row["name"])
                        e_ticker = st.text_input("Ticker", value=row["ticker"])
                    with col2:
                        e_cat = st.selectbox("Kategoria", CATEGORIES, index=CATEGORIES.index(row["category"]))
                        e_cur = st.selectbox("Waluta zakupu", CURRENCIES, index=CURRENCIES.index(row["currency"]) if row["currency"] in CURRENCIES else 0)
                    price_cur_options = ["— (tak samo jak zakupu)"] + CURRENCIES
                    cur_pc_index = CURRENCIES.index(row["price_currency"]) + 1 if row["price_currency"] and row["price_currency"] in CURRENCIES else 0
                    e_price_cur = st.selectbox("Waluta notowań (opcjonalne)", price_cur_options, index=cur_pc_index)
                    col_save, col_del = st.columns([1, 1])
                    with col_save:
                        if st.form_submit_button("Zapisz zmiany"):
                            pc = None if e_price_cur.startswith("—") else e_price_cur
                            update_asset(row["id"], e_name, e_cat, e_ticker, e_cur, pc)
                            st.success("Zaktualizowano.")
                            st.rerun()
                    with col_del:
                        if st.form_submit_button("Usuń pozycję", type="secondary"):
                            delete_asset(row["id"])
                            st.warning("Usunięto pozycję i jej zakupy.")
                            st.rerun()

                st.markdown("#### Dodaj zakup")
                with st.form(f"add_txn_{row['id']}", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        t_date = st.date_input("Data zakupu", value=date.today(), key=f"td_{row['id']}")
                        t_qty = st.number_input("Ilość", min_value=0.0001, step=0.0001, format="%.4f", key=f"tq_{row['id']}")
                    with col2:
                        t_price = st.number_input("Cena zakupu", min_value=0.0001, step=0.01, format="%.4f", key=f"tp_{row['id']}")
                    if st.form_submit_button("Dodaj zakup"):
                        add_transaction(row["id"], str(t_date), t_qty, t_price)
                        st.success(f"Dodano zakup: {t_qty} szt. @ {t_price}")
                        st.rerun()

                if txns:
                    st.markdown("#### Historia zakupów")
                    for t in txns:
                        with st.form(f"edit_txn_{t['id']}"):
                            col1, col2, col3 = st.columns([2, 2, 2])
                            with col1:
                                e_date = st.date_input("Data", value=datetime.strptime(t["date"], "%Y-%m-%d").date(), key=f"td2_{t['id']}")
                            with col2:
                                e_qty = st.number_input("Ilość", min_value=0.0001, value=float(t["quantity"]), step=0.0001, format="%.4f", key=f"tq2_{t['id']}")
                            with col3:
                                e_price = st.number_input(f"Cena ({row['currency']})", min_value=0.0001, value=float(t["buy_price"]), step=0.01, format="%.4f", key=f"tp2_{t['id']}")
                            col_save, col_del = st.columns([1, 1])
                            with col_save:
                                if st.form_submit_button("Zapisz", key=f"save_t_{t['id']}"):
                                    update_transaction(t["id"], str(e_date), e_qty, e_price)
                                    st.success("Zaktualizowano.")
                                    st.rerun()
                            with col_del:
                                if st.form_submit_button("Usuń", type="secondary", key=f"del_t_{t['id']}"):
                                    delete_transaction(t["id"])
                                    st.rerun()

# ── TAB: Obligacje ────────────────────────────────────────────────────────────
with tab_bonds:
    st.subheader("Dodaj obligację")
    with st.form("add_bond_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            b_name = st.text_input("Nazwa obligacji", placeholder="np. OTS0326")
            b_face = st.number_input("Wartość nominalna", min_value=0.01, value=1000.0, step=100.0)
            b_coupon = st.number_input("Oprocentowanie (%)", min_value=0.0, max_value=100.0, value=5.0, step=0.01)
        with col2:
            b_buy_date = st.date_input("Data zakupu", value=date.today(), key="bond_buy")
            b_maturity = st.date_input("Data zapadalności", key="bond_mat")
            b_ytm = st.number_input("YTM (%) — opcjonalne", min_value=0.0, max_value=100.0, value=0.0, step=0.01)
        if st.form_submit_button("Dodaj obligację"):
            if b_name:
                add_bond(b_name, b_face, b_coupon / 100, str(b_buy_date), str(b_maturity), b_ytm / 100 if b_ytm else None)
                st.success(f"Dodano obligację: {b_name}")
                st.rerun()
            else:
                st.error("Podaj nazwę obligacji.")

    st.subheader("Lista obligacji")
    bonds = get_bonds()
    if not bonds:
        st.info("Brak obligacji.")
    else:
        nbp_rate = fetch_nbp_rate()

        # Global inflation assumption slider (shared across all inflation-linked bonds)
        infl_linked = any(parse_symbol(b["name"])[0] in ("COI","EDO","ROS","ROD") for b in bonds)
        if infl_linked:
            assumed_inflation = st.slider(
                "Zakładana inflacja dla obligacji indeksowanych (%)",
                min_value=1.0, max_value=15.0, value=4.0, step=0.5,
                help="Używana do projekcji wartości w dniu zapadalności COI/EDO/ROS/ROD"
            ) / 100
        else:
            assumed_inflation = 0.04

        for b in bonds:
            bond_type, _ = parse_symbol(b["name"])
            params = fetch_bond_params(bond_type) if bond_type else None
            proj = project_maturity_value(float(b["face_value"]), params, assumed_inflation, nbp_rate) if params else None

            proj_label = f"  ·  wartość w terminie: **{proj['value']:,.2f} PLN** (+{proj['gain_pct']}%)" if proj else ""
            with st.expander(f"**{b['name']}**  ·  nominał: {b['face_value']:.0f} PLN  ·  zapadalność: {b['maturity_date']}{proj_label}"):

                if proj:
                    st.markdown("#### Projekcja wartości w dniu zapadalności")
                    col_m1, col_m2, col_m3 = st.columns(3)
                    col_m1.metric("Nominał", f"{b['face_value']:,.2f} PLN")
                    col_m2.metric("Wartość w terminie", f"{proj['value']:,.2f} PLN", delta=f"+{proj['gain']:,.2f} PLN")
                    col_m3.metric("Zysk %", f"{proj['gain_pct']:.2f}%")
                    st.caption(f"Założenia: {proj['assumptions']}")

                    with st.expander("Rozbicie rok po roku"):
                        df_proj = pd.DataFrame(proj["breakdown"], columns=["Okres", "Oprocentowanie", "Wartość (PLN)"])
                        df_proj["Oprocentowanie"] = df_proj["Oprocentowanie"].apply(lambda x: f"{x*100:.2f}%")
                        df_proj["Wartość (PLN)"] = df_proj["Wartość (PLN)"].apply(lambda x: f"{x:,.2f}")
                        st.dataframe(df_proj, use_container_width=True, hide_index=True)
                elif bond_type:
                    st.info(f"Nie udało się pobrać parametrów dla {bond_type} z obligacjeskarbowe.pl")

                st.markdown("#### Edytuj")
                with st.form(f"edit_bond_{b['id']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        eb_name = st.text_input("Nazwa", value=b["name"])
                        eb_face = st.number_input("Wartość nominalna", min_value=0.01, value=float(b["face_value"]), step=100.0)
                        eb_coupon = st.number_input("Oprocentowanie (%)", min_value=0.0, max_value=100.0, value=float(b["coupon_rate"]) * 100, step=0.01)
                    with col2:
                        eb_buy = st.date_input("Data zakupu", value=datetime.strptime(b["buy_date"], "%Y-%m-%d").date())
                        eb_mat = st.date_input("Data zapadalności", value=datetime.strptime(b["maturity_date"], "%Y-%m-%d").date())
                        eb_ytm = st.number_input("YTM (%)", min_value=0.0, max_value=100.0, value=float(b["yield_to_maturity"]) * 100 if b["yield_to_maturity"] else 0.0, step=0.01)
                    col_save, col_del = st.columns([1, 1])
                    with col_save:
                        if st.form_submit_button("Zapisz zmiany"):
                            update_bond(b["id"], eb_name, eb_face, eb_coupon / 100, str(eb_buy), str(eb_mat), eb_ytm / 100 if eb_ytm else None)
                            st.success("Zaktualizowano.")
                            st.rerun()
                    with col_del:
                        if st.form_submit_button("Usuń obligację", type="secondary"):
                            delete_bond(b["id"])
                            st.warning("Obligacja usunięta.")
                            st.rerun()

    # ── Kalkulator zakupu obligacji ─────────────────────────────────────────
    st.markdown("---")
    st.subheader("Kalkulator zakupu obligacji")
    st.caption("Sprawdź, który typ obligacji da najlepszy wynik do wybranej daty wypłaty.")

    with st.form("bond_calc_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            calc_amount = st.number_input("Kwota inwestycji (PLN)", min_value=100.0, value=10000.0, step=100.0)
        with col2:
            calc_target = st.date_input("Data wypłaty", value=date(2030, 2, 1), key="calc_target_date")
        with col3:
            calc_inflation = st.slider("Zakładana inflacja (%)", min_value=1.0, max_value=15.0, value=4.0, step=0.5) / 100
        calc_submit = st.form_submit_button("Oblicz", type="primary")

    if calc_submit:
        today = date.today()
        nbp_rate_calc = fetch_nbp_rate()
        BOND_TYPES = ["OTS", "ROR", "DOR", "TOS", "COI", "EDO", "ROS", "ROD"]
        BOND_LABELS = {
            "OTS": "OTS — 3-miesięczne",
            "ROR": "ROR — 1-roczne",
            "DOR": "DOR — 2-letnie",
            "TOS": "TOS — 3-letnie",
            "COI": "COI — 4-letnie",
            "EDO": "EDO — 10-letnie",
            "ROS": "ROS — 6-letnie",
            "ROD": "ROD — 12-letnie",
        }

        results = []
        with st.spinner("Pobieram dane z obligacjeskarbowe.pl…"):
            for bt in BOND_TYPES:
                params = fetch_bond_params(bt)
                if not params:
                    continue
                r = calculate_bond_at_date(
                    bond_type=bt,
                    face_value=calc_amount,
                    buy_date=today,
                    target_date=calc_target,
                    params=params,
                    assumed_inflation=calc_inflation,
                    nbp_rate=nbp_rate_calc,
                )
                if r:
                    results.append(r)

        if not results:
            st.warning("Nie udało się pobrać danych z obligacjeskarbowe.pl. Spróbuj ponownie.")
        else:
            results.sort(key=lambda x: x["net_annual_return"], reverse=True)

            rows_calc = []
            for r in results:
                rows_calc.append({
                    "Typ": BOND_LABELS.get(r["bond_type"], r["bond_type"]),
                    "Zapadalność": r["maturity_date"],
                    "Scenariusz": r["scenario"],
                    "Wartość (PLN)": r["value_at_target"],
                    "Zysk (PLN)": r["gain"],
                    "Zysk (%)": r["gain_pct"],
                    "Zwrot roczny (%)": r["net_annual_return"],
                    "Kara (PLN)": r["penalty"] if r["redeemed_early"] else 0,
                    "_early": r["redeemed_early"],
                })

            df_calc = pd.DataFrame(rows_calc)

            def color_scenario(val):
                if val == "przedterminowy wykup":
                    return "color: #e65100"
                return "color: #1b5e20"

            def color_gain(val):
                if isinstance(val, (int, float)):
                    return "color: #1b5e20; font-weight: bold" if val > 0 else ""
                return ""

            styled_calc = (
                df_calc.drop(columns=["_early"])
                .style
                .map(color_scenario, subset=["Scenariusz"])
                .map(color_gain, subset=["Zysk (PLN)", "Zysk (%)", "Zwrot roczny (%)"])
                .format({
                    "Wartość (PLN)": "{:,.2f}",
                    "Zysk (PLN)": "{:,.2f}",
                    "Zysk (%)": "{:.2f}%",
                    "Zwrot roczny (%)": "{:.2f}%",
                    "Kara (PLN)": "{:.2f}",
                })
            )

            days_to_target = (calc_target - today).days
            years_to_target = days_to_target / 365
            st.markdown(
                f"**{calc_amount:,.0f} PLN** zainwestowane dziś, wypłata **{calc_target.strftime('%d.%m.%Y')}** "
                f"(za {years_to_target:.1f} lat) — posortowane wg rocznego zwrotu:"
            )
            st.dataframe(styled_calc, use_container_width=True, hide_index=True)

            st.caption(
                "Scenariusz 'do terminu' = obligacja zapada przed lub w dniu wypłaty. "
                "'Przedterminowy wykup' = zerwanie przed terminem, kara potrącana z odsetek. "
                "Zwrot roczny = efektywna roczna stopa składana (CAGR)."
            )
