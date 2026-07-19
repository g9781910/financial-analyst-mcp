# Financial Analyst AI — MCP Server

[![Smithery Badge](https://smithery.ai/badge/g9781910/financial-analyst-mcp)](https://smithery.ai/servers/g9781910/financial-analyst-mcp)

Institutional-grade financial analysis tools for Claude Desktop and any MCP-compatible AI client. Pay per call — no subscriptions, no setup beyond an API key.

Built on [financial-analyst.ai](https://financial-analyst.ai) — a live API with x402 (USDC on Base) and API key credit payment rails.

> **GitHub:** [github.com/g9781910/financial-analyst-mcp](https://github.com/g9781910/financial-analyst-mcp)

---

## Tools

| Tool | What it does | Cost |
|------|-------------|------|
| `lbo.model` | Full LBO from sources & uses through exit. IRR, MOIC, debt schedule, sensitivity tables across exit multiple × leverage. | $5.00 |
| `waterfall.distribute` | LP/GP waterfall, up to 5 promote tiers (IRR or MOIC hurdles), GP pari-passu pref, full or hard catch-up, selectable day count (ACT/365, ACT/360, 30/360, 30E/360, ACT/ACT). Penny-accurate via Python Decimal; reconciled to Excel. | $3.00 |
| `re.multifamily.underwrite` | Multifamily acquisition proforma — unit mix, stub acquisition month, monthly NOI, trailing-NOI exit. Unlevered + levered project returns (IRR via XIRR). Excel-reconciled, SHA-pinned. | $1.00 |
| `re.str.underwrite` | STR/Airbnb underwriting — quarterly ADR + occupancy (whole-night revenue), itemized opex, monthly proforma. Unlevered + levered returns (IRR via XIRR). Excel-reconciled, SHA-pinned. | $1.00 |
| `montecarlo.simulate` | Monte Carlo with correlated variables (Cholesky). P10/P50/P90. Up to 100,000 trials. | $1.00 |
| `dcf.value` | DCF valuation — exit multiple or Gordon Growth terminal value. Enterprise value, equity value, implied share price, 9×9 WACC sensitivity matrix. | $1.00 |
| `re.sfr.underwrite` | SFR rental proforma — monthly cash flow, loan-to-cost financing, optional interest-only, appreciation-floored exit. Unlevered + levered returns (IRR via XIRR). Excel-reconciled, SHA-pinned. | $0.50 |
| `re.fixflip.underwrite` | Fix & flip — backward-solves max purchase price from a profit target; sizes the hard-money loan (min of LTC/ARV caps) and reports the binding constraint. IRR via XIRR. Excel-reconciled, SHA-pinned. | $0.50 |
| `xirr.compute` | XIRR on irregular cash flows. PE distributions, RE waterfalls, project finance. | $0.25 |
| `amortization.schedule` | Full amortization schedule. Milestones, IO period support, extra payment scenarios. | $0.25 |
| `fx.pnl` | FX-adjusted P&L. Decomposes return into asset performance vs currency movement. | $0.25 |
| `debtsizing.size` | Debt sizing across CRE, private equity, and project finance — min of LTV, DSCR, and (where relevant) LLCR/coverage constraints. | $0.25 |
| `re.hotel.underwrite` | Hotel acquisition underwriting (stabilized or PIP reposition). Bridge-to-perm, quarterly RevPAR, DSCR/cap-rate sizing, IRR/MOIC. | $2.00 |
| `re.hotel.develop` | Hotel ground-up development. Construction budget, capitalized interest, developer fee, ADR/occupancy ramp, stabilized exit. | $2.00 |
| `re.industrial.underwrite` | Industrial/warehouse acquisition with per-tenant rent roll. Staggered leases, TI/LC reserves, NNN OpEx, bridge-to-perm. | $2.00 |
| `re.industrial.develop` | Industrial ground-up development. Blended-LTC construction loan, s-curve draw, pre-leasing, stabilized exit. | $2.00 |
| `re.multifamily.develop` | Multifamily ground-up development. Construction loan, lease-up ramp, perm sized on min(LTV, DSCR), stabilized exit. | $2.00 |

All calculations are deterministic, formula-traceable, and Excel-convention compliant. No LLM inside the engine. The deterministic engines are independently reconciled to a SHA-pinned Excel model — **served, not just asserted** — see [Reconciliation & attestation](#reconciliation--attestation).

---

## Quickstart

### 1. Get an API key

Go to [financial-analyst.ai/keys/create](https://financial-analyst.ai/keys/create) and create a free key. Top up with USDC credits via the dashboard.

### 2. Clone the repo

```bash
git clone https://github.com/g9781910/financial-analyst-mcp.git
cd financial-analyst-mcp
pip install fastmcp httpx
```

### 3. Add to Claude Desktop

Edit `~/.claude/claude_desktop_config.json` (create it if it doesn't exist):

```json
{
  "mcpServers": {
    "financial-analyst": {
      "command": "python",
      "args": ["/full/path/to/financial-analyst-mcp/financial_analyst_mcp.py"],
      "env": {
        "FINANCIAL_ANALYST_API_KEY": "your-key-here"
      }
    }
  }
}
```

Restart Claude Desktop. You'll see "financial-analyst" in the tools list.

### Cursor / VS Code

Same JSON structure — paste into your IDE's MCP settings file.

### Test from the command line

```bash
FINANCIAL_ANALYST_API_KEY=your-key python financial_analyst_mcp.py
```

---

## Example prompts once installed

**LBO:**
```
Run an LBO on a $50M EBITDA business: 8x entry, 4x leverage, 5-year hold,
exit at 9x. Revenue growing 7% in year 1 declining to 5%, margins 25-27%.
```

**Waterfall:**
```
Calculate the LP/GP waterfall: $9M LP, $1M GP, close Jan 1 2020.
8% pref, full GP catch-up, IRR hurdles. Tiers: 80/20 to 15%, 75/25 to 18%,
70/30 for all remaining. Five annual distributions of $2M, $4M, $4M, $5M, $5M.
```

**Multifamily:**
```
Underwrite a 32-unit Charlotte multifamily at $4.2M: 8 studios at $1,200,
16 one-beds at $1,550, 8 two-beds at $1,950. 5% vacancy, 38% expense ratio,
75% LTV at 6.5%, 7-year hold, exit at 5.5% cap.
```

**STR:**
```
Underwrite a Folly Beach vacation rental at $650K.
Q1: $220 ADR, 58% occupancy. Q2: $290, 72%. Q3: $380, 88%. Q4: $240, 62%.
Insurance $3,200/yr, property tax $5,800/yr, utilities $3,600/yr.
75% loan-to-cost at 7.25%.
```

**SFR:**
```
Underwrite 142 Oak St Greenville SC at $285K: $2,600/month rent,
$850/month expenses, 70% loan-to-cost at 7% rate, 7-year hold, 6.5% exit cap.
```

**XIRR:**
```
What's the XIRR on this PE investment:
- Jan 15 2020: invested $5M
- Jun 30 2021: invested $2M more  
- Dec 31 2022: received $1.5M distribution
- Mar 15 2025: received $9.8M at exit
```

**Monte Carlo:**
```
Run a Monte Carlo on a real estate project. Revenue is normally distributed
mean $2M std $200K. Cost is triangular low $1.2M mode $1.5M high $2M.
Revenue and cost are correlated 0.4. Formula: revenue - cost. 
50,000 trials. What's P(profit > $400K)?
```

**DCF:**
```
Value Acme Corp using a DCF. FCF projections: $45M, $52M, $58M, $65M, $72M.
WACC 10%. Exit at 10x EV/EBITDA on $95M terminal EBITDA.
Net debt $150M, 25M shares outstanding. What's the implied share price?
```

---

## Schema endpoints

Every tool has a companion schema endpoint for agent auto-configuration:

```
GET /lbo/schema
GET /waterfall/schema
GET /mf-acq/schema
GET /mf-dev/schema
GET /hotel-acq/schema
GET /hotel-dev/schema
GET /industrial-acq/schema
GET /industrial-dev/schema
GET /str/schema
GET /sfr/schema
GET /fix-flip/schema
GET /xirr/schema
GET /amortization/schema
GET /monte-carlo/schema
GET /fx/schema
GET /dcf/schema
GET /debt-sizing/schema
```

---

## Reconciliation & attestation

Engine outputs are reconciled to an independent, SHA-pinned Excel model, and the
proof is **served, not just asserted** — query it, or have an agent verify it
before trusting a number.

```
GET /reconciliation             Cross-engine index: per-engine passed / failed / pending
GET /{engine}/reconciliation    Per-engine attestation: cases, conventions, tolerances,
                                source-workbook SHA-256, last-checked
```

Expecteds are sourced from Excel (the oracle), never from the engine. `passed`
means the engine matches the workbook to the stated tolerance; `pending` is an
honest coverage gap, not a silent pass. Each real-estate acquisition and
development pack covers multiple binding-constraint branches (LTV, DSCR,
purchase-price LTV) and financing paths (refi surplus and shortfall), so a base
case can't mask a convention bug. Monte Carlo is stochastic and excluded by
design; industrial reconciliation is in progress.

Add `"attest": true` to a supporting request to bind the result to the proof set —
a consuming agent can follow the pointer to confirm the engine is passing and see
exactly which conventions were applied.

---

## Payment options

**API key credits (recommended for MCP):** Pre-purchase USDC credits. Each call debits the cost from your balance. Check balance at `/keys/balance`.

**x402 (USDC on Base):** Per-call stablecoin payment directly over HTTP. No API key needed. Used by autonomous agents via [Agentic.market](https://agentic.market).

---

## Direct API access

The underlying REST API is documented at [financial-analyst.ai/docs](https://financial-analyst.ai/docs). All endpoints accept both x402 payment headers and `x-api-key` headers directly — you don't need the MCP server to call the API.

---

## License

MIT
