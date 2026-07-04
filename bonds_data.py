"""
Fetches Polish retail government bond parameters from obligacjeskarbowe.pl
and calculates projected maturity value.

Bond types:
  OTS  3M  fixed simple interest
  ROR  1Y  fixed
  DOR  2Y  year1 fixed, year2 = NBP_ref + margin
  TOS  3Y  fixed compound
  COI  4Y  year1 fixed, years 2-4 = CPI + margin
  EDO 10Y  year1 fixed, years 2-10 = CPI + margin
  ROS  6Y  year1 fixed, years 2-6  = CPI + margin
  ROD 12Y  year1 fixed, years 2-12 = CPI + margin
"""

import re
from typing import Optional
import streamlit as st
import requests

BASE = "https://www.obligacjeskarbowe.pl/oferta-obligacji"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Slug for each bond type on the website
_SLUGS = {
    "OTS": "obligacje-3-miesieczne-ots",
    "ROR": "obligacje-roczne-ror",
    "DOR": "obligacje-2-letnie-dor",
    "TOS": "obligacje-3-letnie-tos",
    "COI": "obligacje-4-letnie-coi",
    "EDO": "obligacje-10-letnie-edo",
    "ROS": "obligacje-6-letnie-ros",
    "ROD": "obligacje-12-letnie-rod",
}

# Bond structure: (years, is_inflation_linked, is_nbp_linked)
_STRUCTURE = {
    "OTS": (0.25, False, False),
    "ROR": (1,    False, False),
    "DOR": (2,    False, True),
    "TOS": (3,    False, False),
    "COI": (4,    True,  False),
    "EDO": (10,   True,  False),
    "ROS": (6,    True,  False),
    "ROD": (12,   True,  False),
}


def parse_symbol(symbol: str):
    """Return (bond_type, maturity_str) from e.g. 'EDO0636' → ('EDO', '0636')."""
    m = re.match(r"([A-Za-z]+)(\d+)", symbol.strip().upper())
    return (m.group(1), m.group(2)) if m else (None, None)


def _pct(text: str) -> Optional[float]:
    """Parse '4,75' or '4.75' to 0.0475."""
    m = re.search(r"(\d+[,.]?\d*)", text)
    if not m:
        return None
    return float(m.group(1).replace(",", ".")) / 100


@st.cache_data(ttl=3600)
def fetch_bond_params(bond_type: str) -> Optional[dict]:
    """
    Fetch current offering parameters for given bond type.
    Returns dict with keys: rate1, margin, years, is_inflation, is_nbp
    """
    slug = _SLUGS.get(bond_type.upper())
    if not slug:
        return None

    # Find the current offering page (there may be multiple series)
    try:
        r = requests.get(f"https://www.obligacjeskarbowe.pl/oferta-obligacji/", headers=HEADERS, timeout=8)
        links = re.findall(rf'href="(/{re.escape(f"oferta-obligacji/{slug}")}[^"]*)"', r.text)
        if not links:
            return None
        url = "https://www.obligacjeskarbowe.pl" + links[0]

        r2 = requests.get(url, headers=HEADERS, timeout=8)
        html = r2.text
    except Exception:
        return None

    percents = re.findall(r"([\d]+[,.][\d]+)\s*%", html)
    marza = re.findall(r"marż[aą]\s*([\d,]+)\s*%", html, re.IGNORECASE)
    nbp_margin = re.findall(r"stopa\s+referencyjna\s+NBP\s*\+\s*([\d,]+)\s*%", html, re.IGNORECASE)

    years, is_inflation, is_nbp = _STRUCTURE.get(bond_type.upper(), (1, False, False))

    rate1 = _pct(percents[0]) if percents else None
    margin = _pct(marza[0]) if marza else (_pct(nbp_margin[0]) if nbp_margin else None)

    return {
        "bond_type": bond_type.upper(),
        "rate1": rate1,
        "margin": margin,
        "years": years,
        "is_inflation": is_inflation,
        "is_nbp": is_nbp,
    }


@st.cache_data(ttl=3600)
def fetch_nbp_rate() -> Optional[float]:
    """Fetch current NBP reference rate from api.nbp.pl."""
    try:
        r = requests.get("https://api.nbp.pl/api/stopy/", headers={"Accept": "application/json"}, timeout=5)
        data = r.json()
        for item in data:
            if "referencyjna" in item.get("nazwa", "").lower():
                return float(item["oprocentowanie"]) / 100
    except Exception:
        pass
    # Fallback: scrape NBP page
    try:
        r = requests.get("https://www.nbp.pl/home.aspx?f=/dzienne/stopy_archiwum.htm", headers=HEADERS, timeout=5)
        m = re.search(r"referencyjna.*?(\d+[,.]\d+)", r.text, re.IGNORECASE | re.DOTALL)
        if m:
            return float(m.group(1).replace(",", ".")) / 100
    except Exception:
        pass
    return None


def project_maturity_value(
    face_value: float,
    params: dict,
    assumed_inflation: float = 0.04,
    nbp_rate: Optional[float] = None,
) -> dict:
    """
    Calculate projected value at maturity.

    Returns dict with:
      value         — projected total value
      breakdown     — list of (year_label, rate, value_after) per period
      assumptions   — human-readable assumptions used
    """
    from math import floor

    fv = face_value
    r1 = params.get("rate1") or 0.0
    margin = params.get("margin") or 0.0
    years = params.get("years", 1)
    is_inflation = params.get("is_inflation", False)
    is_nbp = params.get("is_nbp", False)
    bond_type = params.get("bond_type", "")

    breakdown = []
    value = fv
    assumptions = []

    if bond_type == "OTS":
        # 3-month simple interest
        rate = r1
        value = round(fv * (1 + rate * 92 / 365), 2)
        breakdown.append(("3 miesiące", rate, value))
        assumptions.append(f"Stałe oprocentowanie {rate*100:.2f}%")

    elif not is_inflation and not is_nbp:
        # Fixed rate, compound annually (ROR, TOS)
        rate = r1
        for y in range(1, int(years) + 1):
            value = round(value * (1 + rate), 2)
            breakdown.append((f"Rok {y}", rate, value))
        assumptions.append(f"Stałe oprocentowanie {rate*100:.2f}% rocznie")

    elif is_nbp:
        # DOR: year1 fixed, year2 = NBP + margin
        nbp = nbp_rate or 0.055
        for y in range(1, int(years) + 1):
            rate = r1 if y == 1 else (nbp + margin)
            value = round(value * (1 + rate), 2)
            breakdown.append((f"Rok {y}", rate, value))
        if nbp_rate:
            assumptions.append(f"Rok 1: {r1*100:.2f}%, Rok 2: stopa NBP ({nbp*100:.2f}%) + marża {margin*100:.2f}%")
        else:
            assumptions.append(f"Rok 1: {r1*100:.2f}%, Rok 2: zakładana stopa NBP 5.50% + marża {margin*100:.2f}%")

    else:
        # Inflation-linked: COI, EDO, ROS, ROD
        cpi = assumed_inflation
        for y in range(1, int(years) + 1):
            rate = r1 if y == 1 else (cpi + margin)
            value = round(value * (1 + rate), 2)
            breakdown.append((f"Rok {y}", rate, value))
        assumptions.append(
            f"Rok 1: {r1*100:.2f}%, lata 2-{int(years)}: inflacja {cpi*100:.1f}% + marża {margin*100:.2f}%"
        )

    gain = round(value - fv, 2)
    gain_pct = round(gain / fv * 100, 2) if fv else 0

    return {
        "value": value,
        "gain": gain,
        "gain_pct": gain_pct,
        "breakdown": breakdown,
        "assumptions": " · ".join(assumptions),
    }


# Early redemption fee per 100 PLN of face value (PLN)
_REDEMPTION_FEE = {
    "OTS": 0.0,
    "ROR": 0.50,
    "DOR": 0.70,
    "TOS": 1.00,
    "COI": 2.00,
    "EDO": 3.00,
    "ROS": 1.00,
    "ROD": 2.00,
}


def calculate_bond_at_date(
    bond_type: str,
    face_value: float,
    buy_date,          # date object — today for new purchase
    target_date,       # date object — when user wants the money
    params: dict,
    assumed_inflation: float = 0.04,
    nbp_rate: Optional[float] = None,
) -> Optional[dict]:
    """
    Calculate what face_value PLN invested in bond_type today will be worth
    on target_date, accounting for early redemption penalty if needed.

    Returns dict with:
      bond_type, years, maturity_date, redeemed_early,
      value_at_target, gain, gain_pct, net_annual_return,
      penalty_applied, scenario, assumptions
    """
    from datetime import date as date_cls
    import math

    if not params:
        return None

    years = params.get("years", 1)
    r1 = params.get("rate1") or 0.0
    margin = params.get("margin") or 0.0
    is_inflation = params.get("is_inflation", False)
    is_nbp = params.get("is_nbp", False)

    # Maturity date of bond bought today
    if years == 0.25:
        from datetime import timedelta
        maturity = buy_date + timedelta(days=92)
    else:
        y_int = int(years)
        try:
            maturity = date_cls(buy_date.year + y_int, buy_date.month, buy_date.day)
        except ValueError:
            maturity = date_cls(buy_date.year + y_int, buy_date.month, 28)

    redeemed_early = target_date < maturity
    redemption_date = target_date if redeemed_early else maturity

    # Build year-by-year schedule up to redemption_date
    days_held = (redemption_date - buy_date).days
    value = face_value
    breakdown = []

    if bond_type == "OTS":
        rate = r1
        days = min(days_held, 92)
        value = round(face_value * (1 + rate * days / 365), 2)
        breakdown.append(("3 miesiące", rate, value))
    else:
        full_years = days_held // 365
        remaining_days = days_held % 365

        for y in range(1, int(years) + 1):
            if y <= full_years:
                if is_inflation:
                    rate = r1 if y == 1 else (assumed_inflation + margin)
                elif is_nbp:
                    rate = r1 if y == 1 else ((nbp_rate or 0.055) + margin)
                else:
                    rate = r1
                value = round(value * (1 + rate), 2)
                breakdown.append((f"Rok {y} (pełny)", rate, value))
            elif remaining_days > 0 and y == full_years + 1:
                # Partial year — pro-rata interest
                if is_inflation:
                    rate = r1 if y == 1 else (assumed_inflation + margin)
                elif is_nbp:
                    rate = r1 if y == 1 else ((nbp_rate or 0.055) + margin)
                else:
                    rate = r1
                value = round(value * (1 + rate * remaining_days / 365), 2)
                breakdown.append((f"Rok {y} ({remaining_days} dni)", rate, value))
                break
            else:
                break

    # Apply early redemption penalty if needed
    penalty = 0.0
    if redeemed_early:
        fee_per_100 = _REDEMPTION_FEE.get(bond_type, 0.0)
        penalty = round(fee_per_100 * face_value / 100, 2)
        # Penalty deducted from interest, not principal — value can't drop below face_value
        interest = value - face_value
        actual_penalty = min(penalty, interest)
        value = round(value - actual_penalty, 2)
        penalty = actual_penalty

    gain = round(value - face_value, 2)
    gain_pct = round(gain / face_value * 100, 2) if face_value else 0
    years_held = days_held / 365
    net_annual = round((math.pow(value / face_value, 1 / years_held) - 1) * 100, 2) if years_held > 0 else 0

    scenario = "do terminu" if not redeemed_early else "przedterminowy wykup"

    return {
        "bond_type": bond_type,
        "years_total": years,
        "maturity_date": maturity.strftime("%Y-%m-%d"),
        "redemption_date": redemption_date.strftime("%Y-%m-%d"),
        "redeemed_early": redeemed_early,
        "days_held": days_held,
        "value_at_target": value,
        "gain": gain,
        "gain_pct": gain_pct,
        "net_annual_return": net_annual,
        "penalty": penalty,
        "scenario": scenario,
        "breakdown": breakdown,
    }
