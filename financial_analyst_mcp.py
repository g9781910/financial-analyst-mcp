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
"""

import os
import httpx
from fastmcp import FastMCP
from mcp.types import ToolAnnotations

BASE_URL = os.getenv("FINANCIAL_ANALYST_BASE_URL", "https://financial-analyst.ai")
API_KEY  = os.getenv("FINANCIAL_ANALYST_API_KEY", "")

# All 10 tools are stateless, deterministic calculations — no side effects,
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
        "DCF valuation (exit multiple or Gordon Growth), XIRR on irregular cash flows, "
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
# 1. LBO MODEL  ✓ verified
# Required: entry_ebitda, entry_multiple, debt_multiple
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(annotations=_CALC_ANNOTATIONS)
async def lbo_model(
    entry_ebitda: float,
    entry_multiple: float,
    debt_multiple: float,
    entry_revenue: float | None = None,
    revenue_growth_rates: list[float] | None = None,
    ebitda_margins: list[float] | None = None,
    capex_pct_revenue: float = 0.03,
    nwc_pct_revenue: float = 0.10,
    da_pct_revenue: float = 0.03,
    tax_rate: float = 0.26,
    term_loan_rate: float = 0.085,
    term_loan_amort_pct: float = 0.01,
    cash_sweep_pct: float = 0.50,
    revolver_size: float = 0.0,
    additional_tranches: list[dict] | None = None,
    transaction_fees: float = 0.02,
    cash_on_hand: float = 0.0,
    existing_debt: float = 0.0,
    management_rollover: float = 0.0,
    min_cash_balance: float = 0.0,
    hold_years: int = 5,
    exit_multiple: float | None = None,
    exit_multiples: list[float] | None = None,
    leverage_scenarios: list[float] | None = None,
) -> dict:
    """
    Model a leveraged buyout (LBO) from sources & uses through exit.

    Sizes the Term Loan automatically from debt_multiple × entry_ebitda.
    Only three inputs are required — all others have institutional defaults.
    Supports multi-tranche capital structures (mezz, seller notes, PIK).

    WHEN TO USE:
    - PE deal screening: size returns on a potential acquisition quickly
    - Independent sponsor assessment before engaging lenders
    - DCM debt capacity and leverage sizing for a borrower
    - Comparing entry multiples, leverage, and hold-period assumptions

    OUTPUTS:
    - Sources & uses table (equity check, debt sizing, transaction fees)
    - Annual operating model: revenue, EBITDA, FCF, debt balance, net leverage
    - Debt paydown schedule (mandatory amort + cash sweep) by tranche
    - Base-case IRR and MOIC at exit
    - Sensitivity tables: IRR and MOIC across exit multiples × leverage scenarios

    COST: $5.00 per call (5 API key credits).

    Args:
        entry_ebitda: LTM EBITDA at entry ($). E.g. 50_000_000.
        entry_multiple: Entry EV/EBITDA multiple. E.g. 8.0.
        debt_multiple: Senior Term Loan / EBITDA. E.g. 4.0 = 4x leverage.
        entry_revenue: Entry revenue ($). Inferred from entry_ebitda / ebitda_margins[0]
                       if omitted.
        revenue_growth_rates: Per-year revenue growth rates, last value repeats.
                              E.g. [0.08, 0.07, 0.06, 0.05, 0.05]. Default 5% flat.
        ebitda_margins: Per-year EBITDA margin, last value repeats.
                        E.g. [0.25, 0.26, 0.27, 0.27, 0.27]. Default 30% flat.
        capex_pct_revenue: Maintenance capex as % of revenue. Default 3%.
        nwc_pct_revenue: Net working capital as % of revenue. Default 10%.
        da_pct_revenue: D&A as % of revenue (for EBIT/tax calc). Default 3%.
        tax_rate: Cash tax rate. Default 26%.
        term_loan_rate: Term Loan annual interest rate. Default 8.5%.
        term_loan_amort_pct: Annual mandatory amort as % of original TL principal. Default 1%.
        cash_sweep_pct: % of excess FCF applied to debt paydown after mandatory amort. Default 50%.
        revolver_size: Revolver commitment undrawn at close ($). Default $0.
        additional_tranches: Optional extra debt tranches (mezz, second lien, seller notes, PIK).
                             Each dict: {"name": str, "amount": float, "rate": float,
                             "amort_pct": float, "is_pik": bool, "maturity_years": int}
        transaction_fees: M&A and financing fees as % of EV. Default 2%.
        cash_on_hand: Target's cash at close — reduces equity check ($).
        existing_debt: Target's existing debt repaid at close — added to uses ($).
        management_rollover: Management equity rollover as % of total equity. Default 0%.
        min_cash_balance: Minimum cash to retain on the balance sheet ($).
        hold_years: Investment hold period in years. Default 5.
        exit_multiple: Base case exit EV/EBITDA. Defaults to entry_multiple if omitted.
        exit_multiples: Exit multiples for sensitivity table.
                        E.g. [7.0, 8.0, 9.0, 10.0, 11.0]
        leverage_scenarios: Leverage levels for sensitivity table.
                            E.g. [3.0, 3.5, 4.0, 4.5, 5.0]
    """
    payload: dict = {
        "entry_ebitda": entry_ebitda,
        "entry_multiple": entry_multiple,
        "debt_multiple": debt_multiple,
        "transaction_fees": transaction_fees,
        "cash_on_hand": cash_on_hand,
        "existing_debt": existing_debt,
        "management_rollover": management_rollover,
        "term_loan_rate": term_loan_rate,
        "term_loan_amort_pct": term_loan_amort_pct,
        "revolver_size": revolver_size,
        "hold_years": hold_years,
        "capex_pct_revenue": capex_pct_revenue,
        "nwc_pct_revenue": nwc_pct_revenue,
        "tax_rate": tax_rate,
        "da_pct_revenue": da_pct_revenue,
        "cash_sweep_pct": cash_sweep_pct,
        "min_cash_balance": min_cash_balance,
    }
    if entry_revenue is not None:
        payload["entry_revenue"] = entry_revenue
    if revenue_growth_rates:
        payload["revenue_growth_rates"] = revenue_growth_rates
    if ebitda_margins:
        payload["ebitda_margins"] = ebitda_margins
    if additional_tranches:
        payload["additional_tranches"] = additional_tranches
    if exit_multiple is not None:
        payload["exit_multiple"] = exit_multiple
    if exit_multiples:
        payload["exit_multiples"] = exit_multiples
    if leverage_scenarios:
        payload["leverage_scenarios"] = leverage_scenarios
    return await _post("/lbo/model", payload)


# ─────────────────────────────────────────────────────────────────────────────
# 2. LP/GP WATERFALL  ✓ verified
# Required: lp_contribution, closing_date, preferred_pct, hurdle_type, tiers, periods
# gp_contribution defaults to 0.0
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool(annotations=_CALC_ANNOTATIONS)
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

@mcp.tool(annotations=_CALC_ANNOTATIONS)
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

@mcp.tool(annotations=_CALC_ANNOTATIONS)
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

@mcp.tool(annotations=_CALC_ANNOTATIONS)
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

@mcp.tool(annotations=_CALC_ANNOTATIONS)
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

@mcp.tool(annotations=_CALC_ANNOTATIONS)
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

@mcp.tool(annotations=_CALC_ANNOTATIONS)
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

@mcp.tool(annotations=_CALC_ANNOTATIONS)
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

@mcp.tool(annotations=_CALC_ANNOTATIONS)
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

@mcp.tool(annotations=_CALC_ANNOTATIONS)
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


if __name__ == "__main__":
    mcp.run()
