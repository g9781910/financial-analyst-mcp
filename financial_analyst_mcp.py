"""
Financial Analyst AI — MCP Server
==================================
Wraps https://financial-analyst.ai into Model Context Protocol tools.

Requires:
    pip install fastmcp httpx

Configuration (environment variables):
    FINANCIAL_ANALYST_API_KEY   Your API key from /keys/create
    FINANCIAL_ANALYST_BASE_URL  Optional override (default: https://financial-analyst.ai)

Usage (stdio — Claude Desktop):
    python financial_analyst_mcp.py

Claude Desktop config (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "financial-analyst": {
          "command": "python",
          "args": ["/path/to/financial_analyst_mcp.py"],
          "env": { "FINANCIAL_ANALYST_API_KEY": "your-key-here" }
        }
      }
    }

VERIFICATION STATUS
    ✓ LBO          — verified against full LBORequest schema
    ✓ Waterfall    — verified against WaterfallRequest in router.py
    ✓ Multifamily  — verified against full MultifamilyRequest schema
    ✓ SFR          — verified against SFRRequest in router.py + engine.py
    ✓ Fix & Flip   — verified against full FixFlipRequest schema
    ✓ XIRR         — verified (CashFlowInput list)
    ✓ Amortization — verified against full AmortizationRequest schema
    ✓ Monte Carlo  — verified against full MonteCarloRequest schema
    ✓ FX P&L       — verified against full FXPnLRequest schema
    ✓ STR          — verified against STRRequest in router.py (q1-q4 objects, itemized expenses)
    ✓ DCF          — verified against DCFRequest schema + engine.py (exit multiple / Gordon Growth)
    ✓ Debt Sizing  — verified against DebtSizingRequest schema + engine.py (CRE / PE / project finance)
    ✓ Hotel Acq    — verified against HotelAcqRequest (bridge-to-perm, quarterly RevPAR)
    ✓ Hotel Dev    — verified against HotelDevRequest (ground-up, construction loan, ramp)
    ✓ Industrial Acq — verified against IndustrialAcqRequest (per-tenant rent roll)
    ✓ Industrial Dev — verified against IndustrialDevRequest (ground-up, s-curve draw)
    ✓ MF Dev       — verified against MfDevRequest (ground-up multifamily, lease-up)
"""

import os
import httpx
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

BASE_URL = os.getenv("FINANCIAL_ANALYST_BASE_URL", "https://financial-analyst.ai")
API_KEY  = os.getenv("FINANCIAL_ANALYST_API_KEY", "")

# All 17 tools are stateless, deterministic calculations — no side effects,
# no external calls beyond the financial-analyst.ai API itself.
_CALC_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

mcp = FastMCP(
    name="Financial Analyst AI",
    instructions=(
        "Institutional-grade financial analysis tools. Covers LBO modeling, "
        "LP/GP waterfall distributions, multifamily/SFR/STR/fix-and-flip underwriting, "
        "hotel and industrial acquisition and ground-up development underwriting, "
        "multifamily development underwriting, "
        "DCF valuation (exit multiple or Gordon Growth), debt sizing (CRE, private equity, "
        "or project finance), XIRR on irregular cash flows, "
        "amortization schedules, Monte Carlo simulation with correlated variables, "
        "and FX-adjusted P&L decomposition. "
        "All calculations are deterministic, formula-traceable, Excel-convention compliant. "
        "Costs $0.25–$5.00 per call billed against API key credits."
    ),
)


def _headers() -> dict:
    if not API_KEY:
        raise ValueError(
            "FINANCIAL_ANALYST_API_KEY not set. "
            "Get a key at https://financial-analyst.ai/keys/create"
        )
    return {"x-api-key": API_KEY, "Content-Type": "application/json"}


async def _post(path: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{BASE_URL}{path}", headers=_headers(), json=payload)
        r.raise_for_status()
        return r.json()


# ─────────────────────────────────────────────────────────────────────────────
# 1. LBO MODEL  (3-statement; reconciled to Excel)
# Required: entry_ebitda, entry_multiple, entry_revenue, revenue_growth, ebitda_margin, da_pct_revenue
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(name="lbo.model", annotations=_CALC_ANNOTATIONS)
async def lbo_model(
    entry_ebitda: float,
    entry_multiple: float,
    entry_revenue: float,
    revenue_growth: list[float],
    ebitda_margin: list[float],
    da_pct_revenue: list[float],
    transaction_fees: float = 0.03,
    ownership: float = 1.0,
    hold_years: int = 5,
    senior_leverage: float = 3.5,
    total_leverage: float = 4.0,
    min_dscr: float = 1.2,
    min_interest_cov: float = 2.0,
    existing_debt: float = 0.0,
    excess_cash: float = 0.0,
    base_rate: float = 0.0364,
    senior_spread_bps: float = 500,
    mezz_spread_bps: float = 700,
    revolver_spread_bps: float = 200,
    senior_amort_pct: float = 0.05,
    senior_sweep_pct: float = 0.50,
    senior_orig_pct: float = 0.005,
    mezz_amort_pct: float = 0.05,
    mezz_sweep_pct: float = 0.0,
    mezz_orig_pct: float = 0.01,
    mezz_pik: bool = False,
    revolver_commitment: float = 5.0,
    revolver_orig_pct: float = 0.01,
    min_cash_pct: float = 0.02,
    capex_growth_pct: float = 0.03,
    wc_pct_revenue: float = 0.02,
    mgmt_fee_pct: float = 0.0,
    ebitda_adj_pct: float = 0.0,
    tax_rate: float = 0.25,
    exit_multiple: float = 12.0,
    exit_years: list[int] | None = None,
    mgmt_incentive_pct: float = 0.05,
    attest: bool = False,
) -> dict:
    """
    Model a leveraged buyout (LBO) on a full 3-statement basis, from sources &
    uses through exit. Reconciled to Excel — see the /lbo/reconciliation attestation.

    Senior debt is sized by the minimum of the leverage, interest-coverage, and
    fixed-charge-coverage (DSCR) tests; mezzanine plugs senior up to the total
    leverage multiple. The annual model runs four facilities (senior, mezz, capex,
    revolver) with scheduled amortisation, cash sweep, origination fees and interest;
    taxes are levered (on EBIT - interest, with NOL carryforward); un-swept cash
    accumulates and the exit uses NET debt. Returns are computed for each exit year,
    and the equity gain is decomposed into value-creation drivers.

    All monetary inputs are in consistent currency units (e.g. GBP or USD millions).

    WHEN TO USE:
    - PE deal screening and IC-grade returns analysis
    - Independent sponsor assessment; DCM leverage/debt-capacity sizing
    - Comparing entry/exit multiples, leverage, and hold-period assumptions
    - Value-creation attribution for an IC memo (growth vs multiple vs deleveraging)

    OUTPUTS:
    - Sources & uses (senior sized by the binding test, mezz plug, equity check)
    - Returns for each exit year: IRR, MOIC, equity value
    - Value-creation attribution: EBITDA growth, multiple expansion, debt paydown,
      cash generation, transaction costs, management incentive
    - Full annual model: revenue, EBITDA, EBIT, interest, taxes, debt balances, cash

    COST: $5.00 per call (5 API key credits).

    Args:
        entry_ebitda: LTM EBITDA at entry (currency units, e.g. 4.7 for GBP 4.7m).
        entry_multiple: Entry EV/EBITDA multiple, e.g. 11.0.
        entry_revenue: Revenue at entry (same units as EBITDA).
        revenue_growth: Revenue growth per year, last value repeats. E.g. [0.15, 0.12, 0.10, 0.08, 0.08].
        ebitda_margin: EBITDA margin per year, last repeats. E.g. [0.34, 0.35, 0.35, 0.36, 0.36].
        da_pct_revenue: D&A as % of revenue per year. Maintenance capex is set equal to D&A.
        transaction_fees: Fees as % of EV, applied at entry and exit. Default 3%.
        ownership: Sponsor share of equity. Default 1.0.
        hold_years: Hold period in years. Default 5.
        senior_leverage: Senior sizing leverage multiple (x EBITDA). Default 3.5.
        total_leverage: Total leverage multiple (x EBITDA); mezz plugs to this. Default 4.0.
        min_dscr: Minimum DSCR for the fixed-charge-coverage sizing test. Default 1.2.
        min_interest_cov: Minimum interest coverage for the sizing test. Default 2.0.
        existing_debt: Existing debt repaid at close (added to uses). Default 0.
        excess_cash: Excess cash reducing the equity check. Default 0.
        base_rate: Base / index rate (e.g. SONIA/SOFR). Default 3.64%.
        senior_spread_bps: Senior spread over base, bps. Default 500.
        mezz_spread_bps: Mezzanine spread over base, bps. Default 700.
        revolver_spread_bps: Revolver spread over base, bps. Default 200.
        senior_amort_pct: Senior scheduled amort, % of original per year. Default 5%.
        senior_sweep_pct: Senior cash-sweep % of cash available for debt repayment. Default 50%.
        senior_orig_pct: Senior origination fee, % (year 1). Default 0.5%.
        mezz_amort_pct: Mezzanine scheduled amort, % of original per year. Default 5%.
        mezz_sweep_pct: Mezzanine cash-sweep % (after senior). Default 0%.
        mezz_orig_pct: Mezzanine origination fee, % (year 1). Default 1%.
        mezz_pik: If True, mezzanine interest accrues (PIK). Default False.
        revolver_commitment: Revolver commitment. Default 5.0.
        revolver_orig_pct: Revolver origination fee, % of commitment. Default 1%.
        min_cash_pct: Minimum cash floor as % of revenue; revolver draws to hold it. Default 2%.
        capex_growth_pct: Growth capex as % of revenue. Default 3%.
        wc_pct_revenue: Working-capital investment as % of revenue. Default 2%.
        mgmt_fee_pct: Management fee as % of EBITDA. Default 0%.
        ebitda_adj_pct: EBITDA adjustments as % of EBITDA. Default 0%.
        tax_rate: Corporate tax rate (levered basis). Default 25%.
        exit_multiple: EV/EBITDA exit multiple. Default 12.0.
        exit_years: Exit years to report. Default [2, 3, 4, 5].
        mgmt_incentive_pct: Management incentive / promote, % of equity upside. Default 5%.
        attest: If True, include an attestation block binding the result to the
                engine version and Excel-reconciliation pack.
    """
    payload: dict = {
        "entry_ebitda": entry_ebitda,
        "entry_multiple": entry_multiple,
        "entry_revenue": entry_revenue,
        "revenue_growth": revenue_growth,
        "ebitda_margin": ebitda_margin,
        "da_pct_revenue": da_pct_revenue,
        "transaction_fees": transaction_fees,
        "ownership": ownership,
        "hold_years": hold_years,
        "senior_leverage": senior_leverage,
        "total_leverage": total_leverage,
        "min_dscr": min_dscr,
        "min_interest_cov": min_interest_cov,
        "existing_debt": existing_debt,
        "excess_cash": excess_cash,
        "base_rate": base_rate,
        "senior_spread_bps": senior_spread_bps,
        "mezz_spread_bps": mezz_spread_bps,
        "revolver_spread_bps": revolver_spread_bps,
        "senior_amort_pct": senior_amort_pct,
        "senior_sweep_pct": senior_sweep_pct,
        "senior_orig_pct": senior_orig_pct,
        "mezz_amort_pct": mezz_amort_pct,
        "mezz_sweep_pct": mezz_sweep_pct,
        "mezz_orig_pct": mezz_orig_pct,
        "mezz_pik": mezz_pik,
        "revolver_commitment": revolver_commitment,
        "revolver_orig_pct": revolver_orig_pct,
        "min_cash_pct": min_cash_pct,
        "capex_growth_pct": capex_growth_pct,
        "wc_pct_revenue": wc_pct_revenue,
        "mgmt_fee_pct": mgmt_fee_pct,
        "ebitda_adj_pct": ebitda_adj_pct,
        "tax_rate": tax_rate,
        "exit_multiple": exit_multiple,
        "mgmt_incentive_pct": mgmt_incentive_pct,
        "attest": attest,
    }
    if exit_years:
        payload["exit_years"] = exit_years
    return await _post("/lbo/analyze", payload)


# ─────────────────────────────────────────────────────────────────────────────
# 2. LP/GP WATERFALL  ✓ verified
# Required: lp_contribution, closing_date, preferred_pct, hurdle_type, tiers, periods
# gp_contribution defaults to 0.0
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(name="waterfall.distribute", annotations=_CALC_ANNOTATIONS)
async def waterfall_distribute(
    lp_contribution: float,
    closing_date: str,
    preferred_pct: float,
    hurdle_type: str,
    tiers: list[dict],
    periods: list[dict],
    gp_contribution: float = 0.0,
    catchup_pct: float = 0.10,
) -> dict:
    """
    LP/GP waterfall distribution across multiple periods — penny-accurate.

    Distributes cash in strict order:
    1. Return of capital (pro-rata LP/GP by contribution)
    2. Preferred return (cumulative, non-compounding, ACT/365 on unreturned LP capital)
    3. GP catch-up (100% to GP until GP = catchup_pct × LP preferred paid)
    4. Promote tiers (1–5 tiers with IRR or MOIC hurdles)

    Uses Python Decimal throughout. ACT/365 day count matches Excel.

    TIERS STRUCTURE: hurdle_type applies to ALL tiers. Set the last tier's hurdle
    to 99.0 to capture all remaining distributions above the prior tier.
    Example: [{"hurdle": 0.15, "lp_pct": 0.80, "gp_pct": 0.20},
               {"hurdle": 0.18, "lp_pct": 0.75, "gp_pct": 0.25},
               {"hurdle": 99.0, "lp_pct": 0.70, "gp_pct": 0.30}]

    WHEN TO USE:
    - PE fund waterfall modeling and LP reporting
    - Real estate promote / carried interest calculations
    - Fund admin tools and carry verification
    - Checking GP catch-up mechanics against fund documents

    OUTPUTS: LP/GP summary (contributed, distributed, profit, IRR, MOIC),
             preferred return detail (accrued, paid, outstanding),
             GP catch-up received, per-tier breakdown with hurdle status,
             period-by-period waterfall detail.

    COST: $3.00 per call (3 API key credits).

    Args:
        lp_contribution: Total LP capital contributed ($).
        closing_date: Date capital is contributed (YYYY-MM-DD). Used for
                      preferred return day-count accrual.
        preferred_pct: Annual preferred return rate. E.g. 0.08 for 8%.
                       Cumulative, non-compounding, ACT/365.
        hurdle_type: "IRR" or "MOIC" — applies to ALL promote tiers.
        tiers: Promote tiers ordered by hurdle ascending. 1–5 tiers required.
               Each dict: {"hurdle": float, "lp_pct": float, "gp_pct": float}
               lp_pct + gp_pct must equal 1.0.
               Last tier hurdle should be 99.0 to catch all remaining.
        periods: Distribution periods. Each dict:
                 {"period": int, "date": "YYYY-MM-DD", "amount_available": float}
        gp_contribution: GP co-invest ($). Default 0 (no GP co-invest).
        catchup_pct: GP catch-up as % of LP preferred paid. Default 10%.
                     E.g. 0.10 = GP receives 10% of LP preferred as catch-up.
    """
    return await _post("/waterfall/distribute", {
        "lp_contribution": lp_contribution,
        "gp_contribution": gp_contribution,
        "closing_date": closing_date,
        "preferred_pct": preferred_pct,
        "hurdle_type": hurdle_type,
        "catchup_pct": catchup_pct,
        "tiers": tiers,
        "periods": periods,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 3. MULTIFAMILY ACQUISITION  ✓ verified
# Required: address, purchase_price, unit_types
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(name="re.multifamily.underwrite", annotations=_CALC_ANNOTATIONS)
async def multifamily_underwrite(
    address: str,
    purchase_price: float,
    unit_types: list[dict],
    vacancy_rate: float = 0.05,
    expense_ratio: float = 0.38,
    other_income_pct: float = 0.04,
    ltv: float = 0.75,
    annual_loan_rate: float = 0.065,
    loan_term_years: int = 30,
    interest_only_years: int = 0,
    hold_years: int = 7,
    exit_cap_rate: float = 0.055,
    avg_annual_growth: float = 0.03,
    avg_annual_appreciation: float = 0.03,
    sell_closing_pct: float = 0.03,
    buy_closing_pct: float = 0.015,
) -> dict:
    """
    Multifamily acquisition underwriting proforma.

    Builds a year-by-year model: GPR → vacancy → EGI → OpEx → NOI →
    debt service → cash flow → exit. Tracks DSCR, CoC, LTV, cap rate annually.

    NOTE: expense_ratio is applied to GPR (not EGI), consistent with how
    fixed costs like taxes, insurance, and reserves behave in practice.

    WHEN TO USE:
    - Underwriting a multifamily acquisition for a lender or equity sponsor
    - Screening deals against CoC/DSCR/IRR thresholds
    - Sizing debt on a multifamily asset
    - Comparing entry vs exit cap rate assumptions

    OUTPUTS: Annual proforma (GPR, EGI, NOI, debt service, CoC, DSCR, LTV),
             exit value and net proceeds, IRR and MOIC on equity,
             per-unit metrics (price/unit, NOI/unit).

    COST: $1.00 per call (1 API key credit).

    Args:
        address: Property address.
        purchase_price: Acquisition price ($).
        unit_types: Unit mix — up to 5 types. Each dict:
                    {"label": str, "count": int, "monthly_rent": float}
                    E.g. [{"label": "1BR", "count": 20, "monthly_rent": 1800},
                           {"label": "2BR", "count": 10, "monthly_rent": 2400}]
        vacancy_rate: Portfolio physical vacancy as % of GPR. Default 5%.
        expense_ratio: OpEx as % of GPR (mgmt, maintenance, insurance, taxes,
                       reserves). Typical range 30–45%. Default 38%.
        other_income_pct: Ancillary income as % of EGI (parking, laundry,
                          pet fees, storage). Default 4%.
        ltv: Loan-to-value at origination. Default 75%.
        annual_loan_rate: Mortgage interest rate. Default 6.5%.
        loan_term_years: Amortization term in years. Default 30.
        interest_only_years: IO period before amortization begins. Default 0.
        hold_years: Investment hold period in years. Default 7.
        exit_cap_rate: Applied to exit year NOI for exit value. Default 5.5%.
        avg_annual_growth: Annual rent and expense growth. Default 3%.
        avg_annual_appreciation: Annual property appreciation. Default 3%.
        sell_closing_pct: Exit transaction costs as % of exit value. Default 3%.
        buy_closing_pct: Acquisition costs as % of purchase price. Default 1.5%.
    """
    return await _post("/mf-acq/underwrite", {
        "address": address,
        "purchase_price": purchase_price,
        "unit_types": unit_types,
        "vacancy_rate": vacancy_rate,
        "expense_ratio": expense_ratio,
        "other_income_pct": other_income_pct,
        "ltv": ltv,
        "annual_loan_rate": annual_loan_rate,
        "loan_term_years": loan_term_years,
        "interest_only_years": interest_only_years,
        "hold_years": hold_years,
        "exit_cap_rate": exit_cap_rate,
        "avg_annual_growth": avg_annual_growth,
        "avg_annual_appreciation": avg_annual_appreciation,
        "sell_closing_pct": sell_closing_pct,
        "buy_closing_pct": buy_closing_pct,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 4. SFR UNDERWRITING  ✓ verified
# Required: address, purchase_price, monthly_rent
# Uses down_payment_pct (not LTV). monthly_expenses is MONTHLY not annual.
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(name="re.sfr.underwrite", annotations=_CALC_ANNOTATIONS)
async def sfr_underwrite(
    address: str,
    purchase_price: float,
    monthly_rent: float,
    monthly_expenses: float = 0.0,
    down_payment_pct: float = 0.30,
    annual_loan_rate: float = 0.07,
    loan_term_years: int = 30,
    interest_only_years: int = 0,
    vacancy_rate: float = 0.05,
    avg_annual_growth: float = 0.03,
    avg_annual_appreciation: float = 0.03,
    hold_years: int = 5,
    exit_cap_rate: float = 0.06,
    sell_closing_pct: float = 0.08,
) -> dict:
    """
    Single-family rental (SFR/DSCR) investment underwriting proforma.

    Monthly cash flow model — debt service, rent, and expenses all computed
    monthly then aggregated annually for exact IRR reconciliation.
    Tracks CoC, DSCR, LTV, and cap rate annually as debt amortizes.
    Supports DSCR loans and bridge-to-perm via interest-only periods.

    IMPORTANT: monthly_expenses is a MONTHLY figure (taxes + insurance +
    maintenance + property management combined per month), not annual.

    WHEN TO USE:
    - Underwriting an SFR buy-and-hold investment
    - DSCR loan qualification analysis (tracks DSCR year-by-year)
    - Comparing SFR to multifamily or STR economics
    - Screening single-family rental portfolios

    OUTPUTS: Financing breakdown (loan, down payment, monthly P&I/IO payment),
             Year 1 metrics (NOI, CoC, cap rate, LTV, DSCR),
             annual projection with LTV and DSCR tracked each year,
             exit analysis (exit value, net proceeds), IRR and MOIC.

    COST: $0.50 per call (1 API key credit).

    Args:
        address: Property address.
        purchase_price: Acquisition price ($).
        monthly_rent: Gross monthly rent at full occupancy ($).
        monthly_expenses: Combined monthly operating expenses ($) — property
                          taxes, insurance, maintenance, property management.
                          MONTHLY figure, not annual. Default $0.
        down_payment_pct: Down payment as % of purchase price. Default 30%.
                          E.g. 0.25 for 25% down. (Loan = purchase × (1 - down_pct))
        annual_loan_rate: Mortgage interest rate. Default 7%.
        loan_term_years: Amortization term in years. Default 30.
        interest_only_years: IO period before amortization begins. Default 0.
                             Use for bridge loans or DSCR IO structures.
        vacancy_rate: Physical vacancy rate as % of gross rent. Default 5%.
        avg_annual_growth: Annual rent and expense growth rate. Default 3%.
        avg_annual_appreciation: Annual property appreciation rate. Default 3%.
        hold_years: Investment hold period in years. Default 5.
        exit_cap_rate: Applied to exit year NOI to derive exit value. Default 6%.
        sell_closing_pct: Seller closing costs as % of exit value. Default 8%.
    """
    return await _post("/sfr/underwrite", {
        "address": address,
        "purchase_price": purchase_price,
        "monthly_rent": monthly_rent,
        "monthly_expenses": monthly_expenses,
        "down_payment_pct": down_payment_pct,
        "annual_loan_rate": annual_loan_rate,
        "loan_term_years": loan_term_years,
        "interest_only_years": interest_only_years,
        "vacancy_rate": vacancy_rate,
        "avg_annual_growth": avg_annual_growth,
        "avg_annual_appreciation": avg_annual_appreciation,
        "hold_years": hold_years,
        "exit_cap_rate": exit_cap_rate,
        "sell_closing_pct": sell_closing_pct,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 5. STR UNDERWRITING  ✓ verified
# Required: address, bedrooms, bathrooms, purchase_price, loan_rate, q1-q4
# Quarterly inputs are structured objects, not flat lists.
# Expenses are itemized (10 fields), not a single annual_expenses.
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(name="re.str.underwrite", annotations=_CALC_ANNOTATIONS)
async def str_underwrite(
    address: str,
    bedrooms: int,
    bathrooms: float,
    purchase_price: float,
    loan_rate: float,
    q1: dict,
    q2: dict,
    q3: dict,
    q4: dict,
    down_payment_pct: float = 0.25,
    closing_costs: float = 0.0,
    renovation_capex: float = 0.0,
    loan_term_years: int = 30,
    revenue_growth_rate: float = 0.03,
    expense_growth_rate: float = 0.02,
    mgmt_fee_pct: float = 0.10,
    platform_fee_pct: float = 0.05,
    cleaning_cost_annual: float = 0.0,
    supplies_pct: float = 0.02,
    insurance_annual: float = 0.0,
    property_tax_annual: float = 0.0,
    hoa_annual: float = 0.0,
    utilities_annual: float = 0.0,
    repairs_pct: float = 0.01,
    other_expenses_annual: float = 0.0,
    hold_years: int = 10,
    exit_cap_rate: float = 0.065,
    annual_appreciation: float = 0.03,
    coc_threshold: float = 0.06,
    irr_threshold: float = 0.07,
    moic_threshold: float = 2.0,
) -> dict:
    """
    Short-term rental (STR/Airbnb) investment underwriting with GO/NO-GO verdict.

    Revenue is modeled from quarterly ADR and occupancy assumptions per quarter.
    Each quarter is a structured object with adr, occupancy, and days.
    Operating expenses are itemized — mgmt fee, platform fee, cleaning, supplies,
    insurance, property tax, HOA, utilities, repairs, and other.

    VERDICT LOGIC:
    - GO if Year 1 CoC >= coc_threshold (primary signal)
    - GO if IRR >= irr_threshold AND MOIC >= moic_threshold (override)
    - NO-GO otherwise

    WHEN TO USE:
    - Evaluating a vacation rental or Airbnb investment
    - Screening STR opportunities against CoC/IRR thresholds
    - Comparing STR vs long-term rental (SFR) economics
    - Underwriting a short-term rental portfolio acquisition

    OUTPUTS: GO/NO-GO verdict with primary signal, Year 1 CoC and cap rate,
             IRR and MOIC over hold period, annual cash flow projection,
             itemized expense breakdown, warning flags.

    COST: $1.00 per call (1 API key credit).

    Args:
        address: Property address.
        bedrooms: Number of bedrooms. Required for property classification.
        bathrooms: Number of bathrooms. E.g. 2.0 or 2.5.
        purchase_price: Acquisition price ($).
        loan_rate: Annual mortgage interest rate. E.g. 0.0725 for 7.25%.
        q1: Q1 revenue assumptions. Dict with keys:
            "adr": float (avg daily rate $),
            "occupancy": float (0–1),
            "days": int (days in quarter, default 91)
            E.g. {"adr": 220, "occupancy": 0.58, "days": 90}
        q2: Q2 revenue assumptions. Same structure as q1.
        q3: Q3 revenue assumptions. Same structure as q1.
        q4: Q4 revenue assumptions. Same structure as q1.
        down_payment_pct: Down payment as % of purchase price. Default 25%.
        closing_costs: Acquisition closing costs ($). Default $0.
        renovation_capex: Pre-operations renovation or capex ($). Default $0.
        loan_term_years: Loan amortization term in years. Default 30.
        revenue_growth_rate: Annual revenue growth rate. Default 3%.
        expense_growth_rate: Annual expense growth rate. Default 2%.
        mgmt_fee_pct: Property management fee as % of gross revenue. Default 10%.
        platform_fee_pct: Airbnb/VRBO platform fee as % of revenue. Default 5%.
        cleaning_cost_annual: Annual cleaning costs ($). Default $0.
        supplies_pct: Supplies/consumables as % of revenue. Default 2%.
        insurance_annual: Annual insurance premium ($). Default $0.
        property_tax_annual: Annual property taxes ($). Default $0.
        hoa_annual: Annual HOA fees ($). Default $0.
        utilities_annual: Annual utilities ($). Default $0.
        repairs_pct: Repairs and maintenance as % of revenue. Default 1%.
        other_expenses_annual: Other miscellaneous annual expenses ($). Default $0.
        hold_years: Investment hold period in years. Default 10.
        exit_cap_rate: Applied to exit year NOI for terminal value. Default 6.5%.
        annual_appreciation: Annual property appreciation rate. Default 3%.
        coc_threshold: Minimum Year 1 CoC for GO verdict. Default 6%.
        irr_threshold: Minimum IRR for override GO condition. Default 7%.
        moic_threshold: Minimum MOIC for override GO condition. Default 2.0x.
    """
    return await _post("/str/underwrite", {
        "address": address,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "purchase_price": purchase_price,
        "down_payment_pct": down_payment_pct,
        "closing_costs": closing_costs,
        "renovation_capex": renovation_capex,
        "loan_rate": loan_rate,
        "loan_term_years": loan_term_years,
        "q1": q1,
        "q2": q2,
        "q3": q3,
        "q4": q4,
        "revenue_growth_rate": revenue_growth_rate,
        "expense_growth_rate": expense_growth_rate,
        "mgmt_fee_pct": mgmt_fee_pct,
        "platform_fee_pct": platform_fee_pct,
        "cleaning_cost_annual": cleaning_cost_annual,
        "supplies_pct": supplies_pct,
        "insurance_annual": insurance_annual,
        "property_tax_annual": property_tax_annual,
        "hoa_annual": hoa_annual,
        "utilities_annual": utilities_annual,
        "repairs_pct": repairs_pct,
        "other_expenses_annual": other_expenses_annual,
        "hold_years": hold_years,
        "exit_cap_rate": exit_cap_rate,
        "annual_appreciation": annual_appreciation,
        "coc_threshold": coc_threshold,
        "irr_threshold": irr_threshold,
        "moic_threshold": moic_threshold,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 6. FIX & FLIP  ✓ verified
# Required: address, comps, repair_cost
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(name="re.fixflip.underwrite", annotations=_CALC_ANNOTATIONS)
async def fix_flip_underwrite(
    address: str,
    comps: list[dict],
    repair_cost: float,
    hold_months: int = 6,
    monthly_expenses: float = 0.0,
    contingency_pct: float = 0.10,
    lender_points: float = 0.02,
    annual_interest: float = 0.12,
    buy_closing_pct: float = 0.015,
    sell_closing_pct: float = 0.08,
    desired_profit: float = 20000.0,
    arv_cap_pct: float | None = 0.75,
    ltc_cap_pct: float | None = 0.90,
) -> dict:
    """
    Fix & flip underwriting — solves backwards from desired profit to max purchase price.

    ARV = equal-weighted average of 2–5 comparable sales.
    Loan = min(arv_cap_pct × ARV, ltc_cap_pct × (purchase + repairs)).
    Output identifies which constraint is binding.

    WHEN TO USE:
    - Evaluating a flip before making an offer
    - Hard money lender underwriting a rehab loan
    - Solving for max purchase price given a profit target
    - Comparing repair cost scenarios

    OUTPUTS: ARV from comps, max purchase price, loan amount and binding
             constraint, required equity, full cost waterfall (repairs,
             contingency, financing, carry, closing costs), net profit,
             IRR, MOIC, plain-English summary statement.

    COST: $0.50 per call (1 API key credit).

    Args:
        address: Subject property address.
        comps: 2–5 comparable sales. Each dict:
               {"address": str, "sale_price": float}
               ARV = simple equal-weighted average of all comp prices.
        repair_cost: Estimated rehab cost — materials and labor ($).
        hold_months: Project duration in months. Default 6.
        monthly_expenses: Monthly carrying costs — taxes, insurance,
                          utilities ($). Default $0.
        contingency_pct: Contingency buffer on repairs. Default 10%.
        lender_points: Hard money origination points as % of loan. Default 2%.
        annual_interest: Hard money annual interest rate. Default 12%.
        buy_closing_pct: Buyer closing costs as % of purchase. Default 1.5%.
        sell_closing_pct: Seller closing costs as % of ARV (commissions,
                          title, transfer taxes). Default 8%.
        desired_profit: Minimum net profit target ($). Default $20,000.
        arv_cap_pct: Max loan as % of ARV. Pass None to disable. Default 75%.
        ltc_cap_pct: Max loan as % of (purchase + repairs). None to disable.
                     Default 90%.
    """
    return await _post("/fix-flip/underwrite", {
        "address": address,
        "comps": comps,
        "repair_cost": repair_cost,
        "hold_months": hold_months,
        "monthly_expenses": monthly_expenses,
        "contingency_pct": contingency_pct,
        "lender_points": lender_points,
        "annual_interest": annual_interest,
        "buy_closing_pct": buy_closing_pct,
        "sell_closing_pct": sell_closing_pct,
        "desired_profit": desired_profit,
        "arv_cap_pct": arv_cap_pct,
        "ltc_cap_pct": ltc_cap_pct,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 7. XIRR  ✓ verified
# Required: cash_flows (list of CashFlowInput)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(name="xirr.compute", annotations=_CALC_ANNOTATIONS)
async def xirr_compute(cash_flows: list[dict]) -> dict:
    """
    Compute annualized IRR (XIRR) over irregular cash flow periods.

    Handles any mix of daily, monthly, quarterly, or annual intervals.
    No assumption of regular periods — uses actual dates.

    WHEN TO USE:
    - PE fund IRR on actual distribution dates
    - Real estate returns with irregular cash flows
    - Project finance draw-down and distribution schedules
    - Venture investment IRR from funding rounds to exit
    - Any return calculation where Excel XIRR would apply

    OUTPUTS: Annualized IRR, MOIC, net profit, hold period, cash flow summary.

    COST: $0.25 per call (1 API key credit).

    Args:
        cash_flows: Dated cash flows. Each dict:
                    {"date": "YYYY-MM-DD", "amount": float}
                    Negative = outflows (investments, capital calls, fees).
                    Positive = inflows (distributions, dividends, exit proceeds).
                    Must include at least one negative and one positive.
                    E.g. [{"date": "2020-01-15", "amount": -5000000},
                           {"date": "2021-06-30", "amount": -2000000},
                           {"date": "2023-12-31", "amount": 1500000},
                           {"date": "2025-03-15", "amount": 9800000}]
    """
    return await _post("/xirr/compute", {"cash_flows": cash_flows})


# ─────────────────────────────────────────────────────────────────────────────
# 8. AMORTIZATION SCHEDULE  ✓ verified
# Required: loan_amount, annual_rate, term_months, start_date
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(name="amortization.schedule", annotations=_CALC_ANNOTATIONS)
async def amortization_schedule(
    loan_amount: float,
    annual_rate: float,
    term_months: int,
    start_date: str,
    interest_only_months: int = 0,
    extra_monthly: float = 0.0,
) -> dict:
    """
    Full amortization schedule with summary statistics and milestones.

    Matches Excel PMT exactly: monthly rate = annual rate / 12,
    payment rounded to nearest cent. Interest at full precision,
    balance rounded to cents each period.

    WHEN TO USE:
    - Debt service modeling on any fixed-rate loan
    - Bridge or construction loan with IO period before amortization
    - Comparing loan structures (rate, term, prepayment scenarios)
    - Calculating total interest cost and payoff dates

    OUTPUTS: Monthly payment, total interest paid, payoff date,
             milestones at 25/50/75% principal paid,
             complete payment-by-payment schedule (principal, interest, balance).

    COST: $0.25 per call (1 API key credit).

    Args:
        loan_amount: Principal ($). E.g. 487500.
        annual_rate: Annual interest rate. E.g. 0.0725 for 7.25%.
        term_months: Total amortization term in months. E.g. 360 for 30yr.
        start_date: First payment date (YYYY-MM-DD).
        interest_only_months: IO period before amortization begins. Default 0.
        extra_monthly: Additional principal payment per month ($). Default $0.
    """
    return await _post("/amortization/schedule", {
        "loan_amount": loan_amount,
        "annual_rate": annual_rate,
        "term_months": term_months,
        "start_date": start_date,
        "interest_only_months": interest_only_months,
        "extra_monthly": extra_monthly,
    })


# ─────────────────────────────────────────────────────────────────────────────
# 9. MONTE CARLO  ✓ verified
# Required: variables, formula
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(name="montecarlo.simulate", annotations=_CALC_ANNOTATIONS)
async def monte_carlo_simulate(
    variables: list[dict],
    formula: str,
    trials: int = 10000,
    correlations: list[dict] | None = None,
    threshold: float | None = None,
    seed: int | None = None,
) -> dict:
    """
    Monte Carlo simulation with correlated variables. Up to 100,000 trials.

    Define uncertain inputs with probability distributions, write a formula,
    receive a full statistical distribution of outcomes. Supports correlated
    normal/lognormal variables via Cholesky decomposition — captures real-world
    relationships like cost/revenue correlation or demand/price elasticity.

    DISTRIBUTIONS: normal (mean, std), lognormal (mean, std in real space),
                   uniform (min, max), triangular (low, mode, high).

    WHEN TO USE:
    - Project finance feasibility under cost and revenue uncertainty
    - Real estate return distributions under market assumption ranges
    - Business plan stress testing with correlated variables
    - Probability of meeting a return threshold (VaR-style)

    OUTPUTS: P10/P25/P50/P75/P90 percentiles, mean, std, min, max,
             P(result > threshold) if threshold provided,
             histogram data, per-variable summary statistics.

    COST: $1.00 per call (1 API key credit). Up to 100,000 trials.

    Args:
        variables: Uncertain inputs. Each dict requires "name" and "distribution"
                   plus distribution-specific params:
                   {"name": "revenue", "distribution": "normal",
                    "mean": 5000000, "std": 500000}
                   {"name": "occupancy", "distribution": "triangular",
                    "low": 0.60, "mode": 0.75, "high": 0.90}
                   {"name": "exit_cap", "distribution": "uniform",
                    "min": 0.055, "max": 0.075}
        formula: Expression combining variable names into the output metric.
                 Supports arithmetic and math functions (sqrt, log, exp, abs).
                 E.g. "(revenue - fixed_cost) / investment" for ROI
                 E.g. "revenue - variable_cost * units - fixed_cost" for profit
        trials: Simulation trials. Default 10,000. Max 100,000.
        correlations: Pairwise correlations for normal/lognormal variables.
                      Each dict: {"var_a": str, "var_b": str, "rho": float}
                      rho between -1 and 1.
        threshold: If provided, returns P(output > threshold).
        seed: Random seed for reproducible results.
    """
    payload: dict = {"variables": variables, "formula": formula, "trials": trials}
    if correlations:
        payload["correlations"] = correlations
    if threshold is not None:
        payload["threshold"] = threshold
    if seed is not None:
        payload["seed"] = seed
    return await _post("/monte-carlo/simulate", payload)


# ─────────────────────────────────────────────────────────────────────────────
# 10. FX P&L  ✓ verified
# Required: purchase_price, purchase_currency, purchase_date, purchase_fx_to_usd,
#           sale_price, sale_currency, sale_date, sale_fx_to_usd
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(name="fx.pnl", annotations=_CALC_ANNOTATIONS)
async def fx_pnl(
    purchase_price: float,
    purchase_currency: str,
    purchase_date: str,
    purchase_fx_to_usd: float,
    sale_price: float,
    sale_currency: str,
    sale_date: str,
    sale_fx_to_usd: float,
    costs: list[dict] | None = None,
) -> dict:
    """
    FX-adjusted P&L — decomposes total return into asset vs currency components.

    Answers: how much of my return came from the asset itself vs. exchange rate
    movement? All FX rates are caller-supplied — fully deterministic arithmetic,
    fully auditable. No market data dependency.

    WHEN TO USE:
    - International real estate (buy GBP, carry in GBP and USD, sell GBP)
    - Cross-border PE investments (invest EUR, exit USD)
    - Any investment where currency movement is material to total return
    - Attributing performance between asset manager (local) and FX (currency)

    OUTPUTS: Total USD P&L and return %, local return (asset performance
             ex-FX), currency contribution (USD gain/loss from FX movement),
             annualized return, full cost/income breakdown with timing
             classification (purchase/carry/sale phase).

    COST: $0.25 per call (1 API key credit).

    Args:
        purchase_price: Purchase price in purchase_currency.
        purchase_currency: Currency code at purchase. E.g. "GBP", "EUR", "JPY".
        purchase_date: Purchase date (YYYY-MM-DD).
        purchase_fx_to_usd: Rate at purchase: 1 unit = X USD. E.g. 1.37 means
                            1 GBP = $1.37 at time of purchase.
        sale_price: Sale price in sale_currency.
        sale_currency: Currency code at sale.
        sale_date: Sale date (YYYY-MM-DD).
        sale_fx_to_usd: Rate at sale: 1 unit of sale_currency = X USD.
        costs: Optional dated cash flows (carrying costs, rental income, fees).
               Each dict: {"amount": float, "date": "YYYY-MM-DD"}
               Optional: {"currency": str, "fx_to_usd": float, "label": str}
               Negative = outflows (stamp duty, legal fees, maintenance).
               Positive = inflows (rental income, insurance payouts, refunds).
               Defaults to USD at 1.0 if currency/fx omitted.
    """
    payload: dict = {
        "purchase_price": purchase_price,
        "purchase_currency": purchase_currency,
        "purchase_date": purchase_date,
        "purchase_fx_to_usd": purchase_fx_to_usd,
        "sale_price": sale_price,
        "sale_currency": sale_currency,
        "sale_date": sale_date,
        "sale_fx_to_usd": sale_fx_to_usd,
    }
    if costs:
        payload["costs"] = costs
    return await _post("/fx/pnl", payload)


# ─────────────────────────────────────────────────────────────────────────────
# 11. DCF VALUATION  ✓ verified
# Required: free_cash_flows, wacc
# terminal_method: "exit_multiple" (default) or "gordon_growth"
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(name="dcf.value", annotations=_CALC_ANNOTATIONS)
async def dcf_value(
    free_cash_flows: list[float],
    wacc: float,
    company: str | None = None,
    terminal_method: str = "exit_multiple",
    terminal_growth_rate: float = 0.025,
    exit_multiple: float = 10.0,
    terminal_ebitda: float = 0.0,
    net_debt: float = 0.0,
    shares_outstanding: float | None = None,
) -> dict:
    """
    DCF (Discounted Cash Flow) valuation with Exit Multiple or Gordon Growth
    terminal value. End-of-year cash flow convention.

    Two terminal value methods:
    - "exit_multiple" (default): terminal EBITDA × EV/EBITDA multiple. Standard
      in PE and M&A. Requires terminal_ebitda and exit_multiple.
    - "gordon_growth": FCF_n × (1+g) / (WACC - g). Standard in equity research.
      Requires terminal_growth_rate; WACC must exceed terminal_growth_rate.

    WHEN TO USE:
    - Equity research intrinsic value
    - M&A target valuation
    - PE portfolio company valuation
    - Capital budgeting / project NPV

    OUTPUTS: Per-year FCF, discount factor, and PV; terminal value (undiscounted
    and PV) and its % of enterprise value (sanity check — typically 60-80%);
    enterprise value, equity value, implied share price; 9×9 sensitivity matrix
    (EV across WACC ± 200bps vs exit multiple ± 2x or terminal growth ± 100bps).

    COST: $1.00 per call (1 API key credit).

    Args:
        free_cash_flows: Projected FCF for each forecast year (up to 10 years,
                         end-of-year convention). Negative values = outflows.
                         E.g. [45000000, 52000000, 58000000, 65000000, 72000000]
        wacc: Weighted Average Cost of Capital. E.g. 0.10 for 10%.
        company: Company or asset name — used in summary statement.
        terminal_method: "exit_multiple" or "gordon_growth". Default "exit_multiple".
        terminal_growth_rate: Perpetuity growth rate — gordon_growth only.
                             Default 2.5%. Must be less than wacc.
        exit_multiple: EV/EBITDA exit multiple — exit_multiple only. Default 10.0x.
        terminal_ebitda: EBITDA in terminal year ($) — exit_multiple only,
                        required (must be > 0) when using that method.
        net_debt: Total debt minus cash ($). Negative if net cash position.
        shares_outstanding: Shares outstanding, for implied share price.
    """
    payload: dict = {
        "free_cash_flows": free_cash_flows,
        "wacc": wacc,
        "terminal_method": terminal_method,
        "terminal_growth_rate": terminal_growth_rate,
        "exit_multiple": exit_multiple,
        "terminal_ebitda": terminal_ebitda,
        "net_debt": net_debt,
    }
    if company is not None:
        payload["company"] = company
    if shares_outstanding is not None:
        payload["shares_outstanding"] = shares_outstanding
    return await _post("/dcf/value", payload)


# ─────────────────────────────────────────────────────────────────────────────
# 12. DEBT SIZING  ✓ verified
# asset_class: "cre", "private_equity", or "project_finance" — each has its
# own required field subset (see docstring below).
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(name="debtsizing.size", annotations=_CALC_ANNOTATIONS)
async def debt_sizing_size(
    asset_class: str,
    currency: str = "USD",
    noi: float | None = None,
    cap_rate: float | None = None,
    debt_yield: float | None = None,
    ebitda: float | None = None,
    leverage_multiple: float | None = None,
    min_interest_coverage: float | None = None,
    construction_cost: float | None = None,
    min_llcr: float | None = None,
    debt_term_years: float | None = None,
    cfads: float | None = None,
    interest_rate: float | None = None,
    amortization_months: int | None = None,
    dscr: float | None = None,
    ltv: float | None = None,
) -> dict:
    """
    Debt sizing across three asset-class methodologies. Sizes to the binding
    (minimum) of each class's applicable constraints — runs every leverage/
    coverage/collateral test and lends to the tightest.

    Set asset_class to "cre", "private_equity", or "project_finance" and
    supply that class's required fields (others can be omitted).

    CRE — requires: noi, interest_rate, amortization_months, dscr, ltv, cap_rate, debt_yield
      - DSCR Constraint — annuity-based sizing off target DSCR (Excel PV() convention)
      - LTV Constraint — (NOI / Cap Rate) x LTV
      - Debt Yield Constraint — NOI / Debt Yield

    Private Equity — requires: ebitda, cfads, interest_rate, amortization_months,
    leverage_multiple, min_interest_coverage, dscr
      - Leverage Constraint — EBITDA x Leverage Multiple
      - Interest Coverage Constraint — (EBITDA / Min Interest Coverage) / Rate
      - DSCR Constraint — CFADS-based annuity sizing off minimum DSCR

    Project Finance — requires: construction_cost, cfads, interest_rate,
    debt_term_years, min_llcr, dscr, ltv
      - Loan-to-Cost Constraint — Construction Cost x Max LTV
      - DSCR Constraint — CFADS-based annuity sizing off minimum DSCR
      - LLCR Constraint — PV of CFADS stream off minimum LLCR

    OUTPUTS: binding constraint and loan amount, all three constraint values,
    and implied metrics at the sized loan (e.g. implied DSCR/LTV/leverage/LLCR
    actually achieved at that loan amount).

    COST: $0.25 per call (1 API key credit).

    Args:
        asset_class: "cre", "private_equity", or "project_finance".
        currency: "USD" or "GBP" — echoed, not converted. Default "USD".
        noi: [CRE] Net Operating Income, annual ($).
        cap_rate: [CRE] Capitalization rate, e.g. 0.06 for 6%.
        debt_yield: [CRE] Minimum debt yield, e.g. 0.09 for 9%.
        ebitda: [PE] EBITDA ($).
        leverage_multiple: [PE] Target leverage multiple, e.g. 4.0.
        min_interest_coverage: [PE] Minimum interest coverage, e.g. 2.0.
        construction_cost: [Project Finance] Total construction/project cost ($).
        min_llcr: [Project Finance] Minimum Loan Life Coverage Ratio, e.g. 1.5.
        debt_term_years: [Project Finance] Debt term in years.
        cfads: [PE, Project Finance] Cash Flow Available for Debt Service, annual ($).
        interest_rate: Annual interest rate, e.g. 0.065. Required for all classes.
        amortization_months: [CRE, PE] Amortization period in months, e.g. 360.
        dscr: Target/minimum DSCR, e.g. 1.25. Required for all classes.
        ltv: [CRE] target LTV, or [Project Finance] max LTV, e.g. 0.70.
    """
    payload: dict = {"asset_class": asset_class, "currency": currency}
    optional_fields = {
        "noi": noi, "cap_rate": cap_rate, "debt_yield": debt_yield,
        "ebitda": ebitda, "leverage_multiple": leverage_multiple,
        "min_interest_coverage": min_interest_coverage,
        "construction_cost": construction_cost, "min_llcr": min_llcr,
        "debt_term_years": debt_term_years, "cfads": cfads,
        "interest_rate": interest_rate, "amortization_months": amortization_months,
        "dscr": dscr, "ltv": ltv,
    }
    for k, v in optional_fields.items():
        if v is not None:
            payload[k] = v
    return await _post("/debt-sizing/size", payload)


# ─────────────────────────────────────────────────────────────────────────────
# 13. HOTEL ACQUISITION UNDERWRITING  ✓ verified against HotelAcqRequest
# Required: start_date, purchase_price
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(name="re.hotel.underwrite", annotations=_CALC_ANNOTATIONS)
async def hotel_acquisition_underwrite(
    start_date: str,
    purchase_price: float,
    hold_years: float = 5.0,
    cl_term_months: int = 1,
    num_keys: int = 100,
    closing_costs_pct: float = 0.02,
    pip_budget: float = 0.0,
    pip_spend_months: int = 12,
    soft_costs: float = 0.0,
    q1_occupancy: float = 0.55,
    q2_occupancy: float = 0.69,
    q3_occupancy: float = 0.85,
    q4_occupancy: float = 0.59,
    q1_adr: float = 195.0,
    q2_adr: float = 260.0,
    q3_adr: float = 450.0,
    q4_adr: float = 310.0,
    revenue_escalator_pct: float = 0.03,
    other_revenue_pct: float = 0.20,
    opex_pct: float = 0.35,
    cl_advance_rate: float = 0.65,
    cl_rate: float = 0.085,
    cl_origination_pct: float = 0.005,
    stabilized_cap_rate: float = 0.075,
    perm_ltv: float = 0.60,
    perm_dscr_min: float = 1.25,
    perm_rate: float = 0.075,
    perm_term_years: int = 25,
    perm_io_months: int = 0,
    perm_origination_pct: float = 0.005,
    exit_cap_rate: float = 0.075,
    exit_costs_pct: float = 0.03,
    pip_draw_overrides: list[float] | None = None,
) -> dict:
    """
    Hotel acquisition underwriting — stabilized or light value-add / PIP repositioning.

    Bridge-to-perm structure: acquisition + optional PIP funded by a construction/bridge
    loan, refinanced into a permanent loan sized on stabilized NOI at month cl_term_months.
    RevPAR built from quarterly ADR × occupancy, plus other operated revenue and USALI OpEx.

    WHEN TO USE:
    - Underwriting a hotel acquisition (full- or select-service)
    - Modeling a PIP / brand-conversion reposition with a bridge loan
    - Sizing perm debt off a stabilized cap rate with a DSCR floor
    - Screening on DSCR / cap rate / IRR / MOIC

    OUTPUTS: Annual projection (RevPAR, NOI margin, DSCR, cap rate), bridge and perm
             financing, exit value and net proceeds, IRR and MOIC on equity.

    COST: $1.00 per call (1 API key credit).

    Args:
        start_date: Acquisition closing date, "YYYY-MM-DD".
        purchase_price: Acquisition price ($).
        hold_years: Hold period from acquisition. Default 5.
        cl_term_months: Bridge loan term in months (controls CL payoff / perm sizing).
                        Typically pip_spend_months + 1. Default 1.
        num_keys: Number of rooms. Default 100.
        closing_costs_pct: Acquisition closing costs as % of price. Default 2%.
        pip_budget: Property Improvement Plan total budget ($). Default 0.
        pip_spend_months: PIP drawn straight-line over this many months. Default 12.
        soft_costs: Soft costs ($). Default 0.
        q1_occupancy: Q1 (Jan-Mar) occupancy rate (0-1). Default 0.55.
        q2_occupancy: Q2 (Apr-Jun) occupancy rate (0-1). Default 0.69.
        q3_occupancy: Q3 (Jul-Sep) occupancy rate (0-1). Default 0.85.
        q4_occupancy: Q4 (Oct-Dec) occupancy rate (0-1). Default 0.59.
        q1_adr: Q1 (Jan-Mar) average daily rate ($/night). Default 195.
        q2_adr: Q2 (Apr-Jun) average daily rate ($/night). Default 260.
        q3_adr: Q3 (Jul-Sep) average daily rate ($/night). Default 450.
        q4_adr: Q4 (Oct-Dec) average daily rate ($/night). Default 310.
        revenue_escalator_pct: Annual ADR / revenue escalator. Default 3%.
        other_revenue_pct: Other operated revenue as % of net rooms revenue
                           (F&B, parking, spa, fees). Default 20%.
        opex_pct: OpEx as % of total revenue (all USALI departments). NOI = revenue × (1 − opex_pct).
                  Default 35%.
        cl_advance_rate: LTC on (price + closing + PIP) for the bridge loan. Default 65%.
        cl_rate: Bridge loan annual rate. Default 8.5%.
        cl_origination_pct: Bridge origination fee %. Default 0.5%.
        stabilized_cap_rate: Lender going-in cap rate for perm sizing. Default 7.5%.
        perm_ltv: Max permanent LTV. Default 60%.
        perm_dscr_min: Min DSCR for perm sizing. Default 1.25.
        perm_rate: Permanent loan annual rate. Default 7.5%.
        perm_term_years: Permanent amortization term. Default 25.
        perm_io_months: Interest-only months on the perm loan. Default 0.
        perm_origination_pct: Perm origination fee %. Default 0.5%.
        exit_cap_rate: Exit cap rate. Default 7.5%.
        exit_costs_pct: Sale transaction costs as % of exit value. Default 3%.
        pip_draw_overrides: Optional monthly PIP draw amounts (length = pip_spend_months).
                            Overrides straight-line.
    """
    payload = {
        "start_date": start_date, "purchase_price": purchase_price,
        "hold_years": hold_years, "cl_term_months": cl_term_months, "num_keys": num_keys,
        "closing_costs_pct": closing_costs_pct, "pip_budget": pip_budget,
        "pip_spend_months": pip_spend_months, "soft_costs": soft_costs,
        "q1_occupancy": q1_occupancy, "q2_occupancy": q2_occupancy,
        "q3_occupancy": q3_occupancy, "q4_occupancy": q4_occupancy,
        "q1_adr": q1_adr, "q2_adr": q2_adr, "q3_adr": q3_adr, "q4_adr": q4_adr,
        "revenue_escalator_pct": revenue_escalator_pct,
        "other_revenue_pct": other_revenue_pct, "opex_pct": opex_pct,
        "cl_advance_rate": cl_advance_rate, "cl_rate": cl_rate,
        "cl_origination_pct": cl_origination_pct,
        "stabilized_cap_rate": stabilized_cap_rate, "perm_ltv": perm_ltv,
        "perm_dscr_min": perm_dscr_min, "perm_rate": perm_rate,
        "perm_term_years": perm_term_years, "perm_io_months": perm_io_months,
        "perm_origination_pct": perm_origination_pct,
        "exit_cap_rate": exit_cap_rate, "exit_costs_pct": exit_costs_pct,
    }
    if pip_draw_overrides is not None:
        payload["pip_draw_overrides"] = pip_draw_overrides
    return await _post("/hotel-acq/underwrite", payload)


# ─────────────────────────────────────────────────────────────────────────────
# 14. HOTEL DEVELOPMENT UNDERWRITING  ✓ verified against HotelDevRequest
# Required: start_date, land_cost, hard_and_preopening_costs, soft_costs
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(name="re.hotel.develop", annotations=_CALC_ANNOTATIONS)
async def hotel_development_underwrite(
    start_date: str,
    land_cost: float,
    hard_and_preopening_costs: float,
    soft_costs: float,
    construction_months: int = 18,
    hold_years: float = 5.0,
    cl_term_months: int = 19,
    num_keys: int = 100,
    hard_cost_contingency_pct: float = 0.05,
    soft_cost_contingency_pct: float = 0.05,
    developer_fee_pct: float = 0.02,
    q1_occupancy: float = 0.58,
    q2_occupancy: float = 0.72,
    q3_occupancy: float = 0.88,
    q4_occupancy: float = 0.62,
    q1_adr: float = 295.0,
    q2_adr: float = 360.0,
    q3_adr: float = 550.0,
    q4_adr: float = 410.0,
    revenue_escalator_pct: float = 0.03,
    other_revenue_pct: float = 0.38,
    opex_pct: float = 0.35,
    cl_advance_rate: float = 0.65,
    cl_rate: float = 0.085,
    cl_origination_pct: float = 0.005,
    stabilized_cap_rate: float = 0.075,
    perm_ltv: float = 0.65,
    perm_dscr_min: float = 1.25,
    perm_rate: float = 0.065,
    perm_term_years: int = 25,
    perm_io_months: int = 0,
    perm_origination_pct: float = 0.005,
    exit_cap_rate: float = 0.075,
    exit_costs_pct: float = 0.03,
    hard_cost_draw_pcts: list[float] | None = None,
) -> dict:
    """
    Hotel ground-up development underwriting.

    Full construction budget (land, hard + pre-opening, contingencies, capitalized
    interest, developer fee) funded by a construction loan, refinanced into a permanent
    loan at month cl_term_months. Quarterly ADR × occupancy ramp with a stabilized exit.

    WHEN TO USE:
    - Underwriting ground-up hotel development
    - Sizing a construction loan on blended LTC and capitalized interest
    - Testing yield-on-cost vs exit cap rate spread
    - Screening development returns (IRR / MOIC) with a stabilization ramp

    OUTPUTS: Development budget, construction/perm financing, quarterly ramp,
             stabilized RevPAR / NOI margin / yield-on-cost / DSCR, exit, IRR and MOIC.

    COST: $1.00 per call (1 API key credit).

    Args:
        start_date: Project start date, "YYYY-MM-DD".
        land_cost: Land cost ($).
        hard_and_preopening_costs: All hard costs incl. building, FF&E, kitchen/F&B
                                   equipment, pre-opening/OS&E ($). Contingency applied
                                   separately via hard_cost_contingency_pct.
        soft_costs: Soft costs ($) — architecture, design, permits, etc.
        construction_months: Construction period in months. Default 18.
        hold_years: Hold period. Default 5.
        cl_term_months: CL term (controls payoff, dev-fee payment, perm sizing).
                        Typically construction_months + 1. Default 19.
        num_keys: Number of rooms. Default 100.
        hard_cost_contingency_pct: Contingency as % of hard_and_preopening_costs. Default 5%.
        soft_cost_contingency_pct: Contingency as % of soft_costs. Default 5%.
        developer_fee_pct: Developer fee as % of (land + total hard + total soft). Default 2%.
        q1_occupancy: Q1 (Jan-Mar) occupancy rate (0-1). Default 0.58.
        q2_occupancy: Q2 (Apr-Jun) occupancy rate (0-1). Default 0.72.
        q3_occupancy: Q3 (Jul-Sep) occupancy rate (0-1). Default 0.88.
        q4_occupancy: Q4 (Oct-Dec) occupancy rate (0-1). Default 0.62.
        q1_adr: Q1 (Jan-Mar) average daily rate ($/night). Default 295.
        q2_adr: Q2 (Apr-Jun) average daily rate ($/night). Default 360.
        q3_adr: Q3 (Jul-Sep) average daily rate ($/night). Default 550.
        q4_adr: Q4 (Oct-Dec) average daily rate ($/night). Default 410.
        revenue_escalator_pct: Annual ADR / revenue escalator from first operating year. Default 3%.
        other_revenue_pct: Other operated revenue as % of net rooms revenue. Default 38%.
        opex_pct: OpEx as % of total revenue (all USALI departments). Default 35%.
        cl_advance_rate: Blended construction-loan LTC. Default 65%.
        cl_rate: Construction loan annual rate. Default 8.5%.
        cl_origination_pct: Construction origination fee %. Default 0.5%.
        stabilized_cap_rate: Lender going-in cap rate for perm sizing. Default 7.5%.
        perm_ltv: Max permanent LTV. Default 65%.
        perm_dscr_min: Min DSCR for perm sizing. Default 1.25.
        perm_rate: Permanent loan annual rate. Default 6.5%.
        perm_term_years: Permanent amortization term. Default 25.
        perm_io_months: Interest-only months on the perm loan. Default 0.
        perm_origination_pct: Perm origination fee %. Default 0.5%.
        exit_cap_rate: Exit cap rate. Default 7.5%.
        exit_costs_pct: Sale transaction costs as % of exit value. Default 3%.
        hard_cost_draw_pcts: Optional monthly hard-cost draw amounts (length =
                             construction_months). Overrides NORMDIST S-curve; pass exact
                             Excel values for reconciliation.
    """
    payload = {
        "start_date": start_date, "land_cost": land_cost,
        "hard_and_preopening_costs": hard_and_preopening_costs, "soft_costs": soft_costs,
        "construction_months": construction_months, "hold_years": hold_years,
        "cl_term_months": cl_term_months, "num_keys": num_keys,
        "hard_cost_contingency_pct": hard_cost_contingency_pct,
        "soft_cost_contingency_pct": soft_cost_contingency_pct,
        "developer_fee_pct": developer_fee_pct,
        "q1_occupancy": q1_occupancy, "q2_occupancy": q2_occupancy,
        "q3_occupancy": q3_occupancy, "q4_occupancy": q4_occupancy,
        "q1_adr": q1_adr, "q2_adr": q2_adr, "q3_adr": q3_adr, "q4_adr": q4_adr,
        "revenue_escalator_pct": revenue_escalator_pct,
        "other_revenue_pct": other_revenue_pct, "opex_pct": opex_pct,
        "cl_advance_rate": cl_advance_rate, "cl_rate": cl_rate,
        "cl_origination_pct": cl_origination_pct,
        "stabilized_cap_rate": stabilized_cap_rate, "perm_ltv": perm_ltv,
        "perm_dscr_min": perm_dscr_min, "perm_rate": perm_rate,
        "perm_term_years": perm_term_years, "perm_io_months": perm_io_months,
        "perm_origination_pct": perm_origination_pct,
        "exit_cap_rate": exit_cap_rate, "exit_costs_pct": exit_costs_pct,
    }
    if hard_cost_draw_pcts is not None:
        payload["hard_cost_draw_pcts"] = hard_cost_draw_pcts
    return await _post("/hotel-dev/underwrite", payload)


# ─────────────────────────────────────────────────────────────────────────────
# 15. INDUSTRIAL ACQUISITION UNDERWRITING  ✓ verified against IndustrialAcqRequest
# Required: start_date, hold_years, total_sf, purchase_price, tenants,
#           opex_per_sf_yr, stabilized_cap_rate, perm_rate, exit_cap_rate
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(name="re.industrial.underwrite", annotations=_CALC_ANNOTATIONS)
async def industrial_acquisition_underwrite(
    start_date: str,
    hold_years: float,
    total_sf: float,
    purchase_price: float,
    tenants: list[dict],
    opex_per_sf_yr: float,
    stabilized_cap_rate: float,
    perm_rate: float,
    exit_cap_rate: float,
    closing_costs_pct: float = 0.02,
    capex_budget: float = 0.0,
    capex_spend_months: int = 12,
    soft_costs: float = 0.0,
    other_income_annual: float = 0.0,
    vacancy_credit_loss_pct: float = 0.05,
    opex_growth_pct: float = 0.03,
    mgmt_fee_pct: float = 0.03,
    ti_per_sf: float = 7.0,
    lc_pct_of_lease_value: float = 0.04,
    cl_advance_rate: float = 0.65,
    cl_rate: float = 0.085,
    cl_origination_pct: float = 0.005,
    cl_term_months: int = 13,
    perm_ltv: float = 0.65,
    perm_dscr_min: float = 1.25,
    perm_term_years: int = 30,
    perm_io_months: int = 0,
    perm_origination_pct: float = 0.005,
    exit_costs_pct: float = 0.03,
    capex_draw_overrides: list[float] | None = None,
) -> dict:
    """
    Industrial / warehouse acquisition underwriting with a per-tenant rent roll.

    Bridge-to-perm structure: acquisition + optional capex funded by a bridge/construction
    loan, refinanced into a permanent loan sized on stabilized NOI at month cl_term_months.
    Tracks lease-level rent, escalators, TI/LC rollover reserves and NNN OpEx.

    WHEN TO USE:
    - Underwriting a stabilized or light value-add industrial acquisition
    - Modeling staggered lease commencements / rollover
    - Sizing perm debt off a stabilized cap rate with a DSCR floor
    - Screening on DSCR / cap rate / IRR / MOIC and $/SF metrics

    OUTPUTS: Annual proforma (NOI, DSCR, cap rate), per-tenant rent roll, bridge/perm
             financing, exit value and net proceeds, IRR and MOIC, $/SF metrics.

    COST: $1.00 per call (1 API key credit).

    Args:
        start_date: Acquisition / closing date, "YYYY-MM-DD".
        hold_years: Hold period from acquisition (1–15).
        total_sf: Net rentable square feet.
        purchase_price: Acquisition price ($).
        tenants: Rent roll — list of dicts, each:
                 {"label": str, "rentable_sf": float, "rent_per_sf_yr": float,
                  "lease_start_month": int, "term_months": int, "escalator_pct": float}.
                 lease_start_month=1 for tenants in place at acquisition.
        opex_per_sf_yr: All-in OpEx $/SF/yr in year 1 (excl. management fee).
        stabilized_cap_rate: Lender going-in cap rate for perm sizing.
        perm_rate: Permanent loan annual rate.
        exit_cap_rate: Exit cap rate.
        closing_costs_pct: Acquisition closing costs %. Default 2%.
        capex_budget: Planned improvement budget ($). Default 0.
        capex_spend_months: Months over which capex is drawn straight-line. Default 12.
        soft_costs: Soft costs ($). Default 0.
        other_income_annual: Ancillary annual income ($). Default 0.
        vacancy_credit_loss_pct: Vacancy + credit loss as % of GPR. Default 5%.
        opex_growth_pct: Annual OpEx growth (calendar-year step-up). Default 3%.
        mgmt_fee_pct: Management fee as % of revenue. Default 3%.
        ti_per_sf: Tenant improvement allowance on rollover ($/SF). Default 7.
        lc_pct_of_lease_value: Leasing commission as % of new lease value. Default 4%.
        cl_advance_rate: LTV on (price + capex) for the bridge loan. Default 65%.
        cl_rate: Bridge loan annual rate. Default 8.5%.
        cl_origination_pct: Bridge origination fee %. Default 0.5%.
        cl_term_months: Bridge term in months; perm closes at end of this month. Default 13.
        perm_ltv: Max permanent LTV. Default 65%.
        perm_dscr_min: Min DSCR for perm sizing. Default 1.25.
        perm_term_years: Permanent amortization term. Default 30.
        perm_io_months: Interest-only months on the perm loan. Default 0.
        perm_origination_pct: Perm origination fee %. Default 0.5%.
        exit_costs_pct: Sale transaction costs as % of exit value. Default 3%.
        capex_draw_overrides: Optional monthly capex draw amounts ($) (length =
                              capex_spend_months). Overrides straight-line.
    """
    payload = {
        "start_date": start_date, "hold_years": hold_years, "total_sf": total_sf,
        "purchase_price": purchase_price, "tenants": tenants,
        "opex_per_sf_yr": opex_per_sf_yr, "stabilized_cap_rate": stabilized_cap_rate,
        "perm_rate": perm_rate, "exit_cap_rate": exit_cap_rate,
        "closing_costs_pct": closing_costs_pct, "capex_budget": capex_budget,
        "capex_spend_months": capex_spend_months, "soft_costs": soft_costs,
        "other_income_annual": other_income_annual,
        "vacancy_credit_loss_pct": vacancy_credit_loss_pct,
        "opex_growth_pct": opex_growth_pct, "mgmt_fee_pct": mgmt_fee_pct,
        "ti_per_sf": ti_per_sf, "lc_pct_of_lease_value": lc_pct_of_lease_value,
        "cl_advance_rate": cl_advance_rate, "cl_rate": cl_rate,
        "cl_origination_pct": cl_origination_pct, "cl_term_months": cl_term_months,
        "perm_ltv": perm_ltv, "perm_dscr_min": perm_dscr_min,
        "perm_term_years": perm_term_years, "perm_io_months": perm_io_months,
        "perm_origination_pct": perm_origination_pct, "exit_costs_pct": exit_costs_pct,
    }
    if capex_draw_overrides is not None:
        payload["capex_draw_overrides"] = capex_draw_overrides
    return await _post("/industrial-acq/underwrite", payload)


# ─────────────────────────────────────────────────────────────────────────────
# 16. INDUSTRIAL DEVELOPMENT UNDERWRITING  ✓ verified against IndustrialDevRequest
# Required: start_date, construction_months, hold_years, total_sf, land_cost,
#           hard_costs, soft_costs, tenants, opex_per_sf_yr, stabilized_cap_rate,
#           perm_rate, exit_cap_rate
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(name="re.industrial.develop", annotations=_CALC_ANNOTATIONS)
async def industrial_development_underwrite(
    start_date: str,
    construction_months: int,
    hold_years: float,
    total_sf: float,
    land_cost: float,
    hard_costs: float,
    soft_costs: float,
    tenants: list[dict],
    opex_per_sf_yr: float,
    stabilized_cap_rate: float,
    perm_rate: float,
    exit_cap_rate: float,
    stabilization_months: int = 6,
    developer_fee_pct: float = 0.02,
    construction_fee_pct: float = 0.0,
    draw_schedule: str = "s_curve",
    other_income_annual: float = 0.0,
    vacancy_credit_loss_pct: float = 0.05,
    opex_growth_pct: float = 0.03,
    mgmt_fee_pct: float = 0.03,
    ti_per_sf: float = 7.0,
    lc_pct_of_lease_value: float = 0.04,
    cl_advance_rate: float = 0.65,
    cl_rate: float = 0.085,
    cl_origination_pct: float = 0.005,
    cl_term_months: int = 36,
    perm_ltv: float = 0.65,
    perm_dscr_min: float = 1.25,
    perm_term_years: int = 30,
    perm_io_months: int = 0,
    perm_origination_pct: float = 0.005,
    exit_costs_pct: float = 0.03,
    hard_cost_draw_pcts: list[float] | None = None,
) -> dict:
    """
    Industrial / warehouse ground-up development underwriting with a per-tenant rent roll.

    Construction loan on blended LTC (land + hard + soft + dev fee + capitalized interest),
    refinanced into a permanent loan at month cl_term_months. Lease-up from first occupancy
    with TI/LC reserves, NNN OpEx, and a stabilized exit.

    WHEN TO USE:
    - Underwriting ground-up industrial/logistics development
    - Sizing a construction loan on blended LTC and an s-curve draw
    - Modeling pre-leasing with staggered commencements
    - Testing yield-on-cost vs exit cap spread; screening IRR / MOIC

    OUTPUTS: Development budget, construction/perm financing, lease-up proforma,
             stabilized NOI / yield-on-cost / DSCR, exit, IRR and MOIC, $/SF metrics.

    COST: $1.00 per call (1 API key credit).

    Args:
        start_date: Project start date "YYYY-MM-DD" (land close / construction begin).
        construction_months: Construction period in months (6–60).
        hold_years: Hold from first occupancy (construction_months + 1), in years.
        total_sf: Net rentable square feet.
        land_cost: Land cost ($).
        hard_costs: Total hard construction costs ($).
        soft_costs: Total soft costs ($) — drawn evenly months 1-3.
        tenants: Rent roll — list of dicts, each:
                 {"label": str, "rentable_sf": float, "rent_per_sf_yr": float,
                  "lease_start_month": int, "term_months": int, "escalator_pct": float}.
                 lease_start_month is from project start.
        opex_per_sf_yr: All-in OpEx $/SF/yr in year 1 (excl. management fee).
        stabilized_cap_rate: Going-in cap rate for perm loan sizing.
        perm_rate: Permanent loan annual rate.
        exit_cap_rate: Exit cap rate — sale = LTM NOI / exit_cap_rate.
        stabilization_months: Lease-up period; sets developer-fee payment month. Default 6.
        developer_fee_pct: Developer fee as % of (land + hard + soft). Default 2%.
        construction_fee_pct: GC/CM fee as % of hard costs, if separate. Default 0.
        draw_schedule: "s_curve" or "straight_line". Default "s_curve".
        other_income_annual: Ancillary annual income ($). Default 0.
        vacancy_credit_loss_pct: Vacancy + credit loss as % of GPR. Default 5%.
        opex_growth_pct: Annual OpEx growth (calendar-year step-up). Default 3%.
        mgmt_fee_pct: Management fee as % of net rental revenue. Default 3%.
        ti_per_sf: Tenant improvement allowance on rollover ($/SF). Default 7.
        lc_pct_of_lease_value: Leasing commission as % of new lease value. Default 4%.
        cl_advance_rate: Blended construction-loan LTC. Default 65%.
        cl_rate: Construction loan annual rate. Default 8.5%.
        cl_origination_pct: Construction origination fee %. Default 0.5%.
        cl_term_months: CL term; perm closes at end of this month. Set to
                        first_occupancy_month + stabilization_months. Default 36.
        perm_ltv: Max permanent LTV. Default 65%.
        perm_dscr_min: Min DSCR for perm sizing. Default 1.25.
        perm_term_years: Permanent amortization term. Default 30.
        perm_io_months: Interest-only months on the perm loan. Default 0.
        perm_origination_pct: Perm origination fee %. Default 0.5%.
        exit_costs_pct: Sale transaction costs as % of exit value. Default 3%.
        hard_cost_draw_pcts: Optional monthly hard-cost draw % (length =
                             construction_months). Overrides draw_schedule; normalized to 100%.
    """
    payload = {
        "start_date": start_date, "construction_months": construction_months,
        "hold_years": hold_years, "total_sf": total_sf, "land_cost": land_cost,
        "hard_costs": hard_costs, "soft_costs": soft_costs, "tenants": tenants,
        "opex_per_sf_yr": opex_per_sf_yr, "stabilized_cap_rate": stabilized_cap_rate,
        "perm_rate": perm_rate, "exit_cap_rate": exit_cap_rate,
        "stabilization_months": stabilization_months,
        "developer_fee_pct": developer_fee_pct, "construction_fee_pct": construction_fee_pct,
        "draw_schedule": draw_schedule, "other_income_annual": other_income_annual,
        "vacancy_credit_loss_pct": vacancy_credit_loss_pct,
        "opex_growth_pct": opex_growth_pct, "mgmt_fee_pct": mgmt_fee_pct,
        "ti_per_sf": ti_per_sf, "lc_pct_of_lease_value": lc_pct_of_lease_value,
        "cl_advance_rate": cl_advance_rate, "cl_rate": cl_rate,
        "cl_origination_pct": cl_origination_pct, "cl_term_months": cl_term_months,
        "perm_ltv": perm_ltv, "perm_dscr_min": perm_dscr_min,
        "perm_term_years": perm_term_years, "perm_io_months": perm_io_months,
        "perm_origination_pct": perm_origination_pct, "exit_costs_pct": exit_costs_pct,
    }
    if hard_cost_draw_pcts is not None:
        payload["hard_cost_draw_pcts"] = hard_cost_draw_pcts
    return await _post("/industrial-dev/underwrite", payload)


# ─────────────────────────────────────────────────────────────────────────────
# 17. MULTIFAMILY DEVELOPMENT UNDERWRITING  ✓ verified against MfDevRequest
# Required: start_date, construction_months, stabilization_months, hold_years,
#           units, land_cost, hard_costs, soft_costs, construction_ltc,
#           construction_rate, stabilized_cap_rate, perm_rate, exit_cap_rate
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(name="re.multifamily.develop", annotations=_CALC_ANNOTATIONS)
async def multifamily_development_underwrite(
    start_date: str,
    construction_months: int,
    stabilization_months: int,
    hold_years: float,
    units: list[dict],
    land_cost: float,
    hard_costs: float,
    soft_costs: float,
    construction_ltc: float,
    construction_rate: float,
    stabilized_cap_rate: float,
    perm_rate: float,
    exit_cap_rate: float,
    rent_growth_pct: float = 0.03,
    stabilized_vacancy_pct: float = 0.05,
    other_income_pct: float = 0.04,
    opex_pct: float = 0.38,
    developer_fee: float = 0.0,
    construction_origination_pct: float = 0.005,
    draw_schedule: str = "s_curve",
    perm_ltv: float = 0.65,
    perm_dscr_min: float = 1.25,
    perm_term_years: int = 30,
    perm_origination_pct: float = 0.005,
    exit_costs_pct: float = 0.03,
    hard_cost_draw_pcts: list[float] | None = None,
) -> dict:
    """
    Multifamily ground-up development underwriting.

    Construction loan on blended LTC (land + hard + soft + capitalized interest),
    refinanced into a permanent loan sized as min(LTV, DSCR) on stabilized NOI /
    stabilized_cap_rate. Lease-up from C/O with a stabilized exit.

    WHEN TO USE:
    - Underwriting ground-up multifamily development
    - Sizing a construction loan on blended LTC and an s-curve draw
    - Testing yield-on-cost vs exit cap spread
    - Screening development IRR / MOIC with a lease-up ramp

    OUTPUTS: Development budget, construction/perm financing, lease-up proforma,
             stabilized NOI / yield-on-cost / DSCR, exit value and net proceeds,
             IRR and MOIC, per-unit metrics.

    COST: $1.00 per call (1 API key credit).

    Args:
        start_date: Project start date "YYYY-MM-DD" (land purchase / month 1).
        construction_months: Construction period in months (6–60).
        stabilization_months: Lease-up / stabilization period in months (1–24).
        hold_years: Hold from stabilization, in years.
        units: Unit mix — list of dicts, each:
               {"type": str, "count": int, "monthly_rent": float}.
        land_cost: Land cost ($) — paid month 1, in blended LTC basis.
        hard_costs: Total hard construction costs ($).
        soft_costs: Total soft costs ($) — drawn equally months 1-3.
        construction_ltc: Blended LTC on all-in monthly uses (e.g. 0.65).
        construction_rate: Construction loan annual rate.
        stabilized_cap_rate: Going-in cap rate for perm value sizing.
        perm_rate: Permanent loan annual rate.
        exit_cap_rate: Exit cap rate — sale = trailing-12-month NOI / exit_cap_rate.
        rent_growth_pct: Annual rent growth. Default 3%.
        stabilized_vacancy_pct: Stabilized vacancy rate. Default 5%.
        other_income_pct: Other income as % of net rental revenue. Default 4%.
        opex_pct: OpEx as % of GPR (applied to GPR, not EGI). Default 38%.
        developer_fee: Developer fee ($) — drawn in CL, paid at C/O. Default 0.
        construction_origination_pct: Construction origination fee %. Default 0.5%.
        draw_schedule: "s_curve" or "straight_line". Default "s_curve".
        perm_ltv: Max perm LTV. Default 65%.
        perm_dscr_min: Min DSCR for perm sizing. Default 1.25.
        perm_term_years: Permanent amortization term. Default 30.
        perm_origination_pct: Perm origination fee %. Default 0.5%.
        exit_costs_pct: Sale transaction costs as % of gross sale price. Default 3%.
        hard_cost_draw_pcts: Optional monthly hard-cost draw % (length =
                             construction_months). Overrides draw_schedule; normalized to 100%.
    """
    payload = {
        "start_date": start_date, "construction_months": construction_months,
        "stabilization_months": stabilization_months, "hold_years": hold_years,
        "units": units, "land_cost": land_cost, "hard_costs": hard_costs,
        "soft_costs": soft_costs, "construction_ltc": construction_ltc,
        "construction_rate": construction_rate, "stabilized_cap_rate": stabilized_cap_rate,
        "perm_rate": perm_rate, "exit_cap_rate": exit_cap_rate,
        "rent_growth_pct": rent_growth_pct,
        "stabilized_vacancy_pct": stabilized_vacancy_pct,
        "other_income_pct": other_income_pct, "opex_pct": opex_pct,
        "developer_fee": developer_fee,
        "construction_origination_pct": construction_origination_pct,
        "draw_schedule": draw_schedule, "perm_ltv": perm_ltv,
        "perm_dscr_min": perm_dscr_min, "perm_term_years": perm_term_years,
        "perm_origination_pct": perm_origination_pct, "exit_costs_pct": exit_costs_pct,
    }
    if hard_cost_draw_pcts is not None:
        payload["hard_cost_draw_pcts"] = hard_cost_draw_pcts
    return await _post("/mf-dev/underwrite", payload)


if __name__ == "__main__":
    mcp.run()
