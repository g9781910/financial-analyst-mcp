# Financial Analyst AI — MCP Server

[![Smithery Badge](https://smithery.ai/badge/g9781910/financial-analyst-mcp)](https://smithery.ai/servers/g9781910/financial-analyst-mcp)

Institutional-grade financial analysis tools for Claude Desktop and any MCP-compatible AI client. Pay per call — no subscriptions, no setup beyond an API key.

Built on [financial-analyst.ai](https://financial-analyst.ai) — a live API with x402 (USDC on Base) and API key credit payment rails.

> **GitHub:** [github.com/g9781910/financial-analyst-mcp](https://github.com/g9781910/financial-analyst-mcp)

---

## Tools

| Tool | What it does | Cost |
|------|-------------|------|
| `lbo_model` | Full LBO from sources & uses through exit. IRR, MOIC, debt schedule, sensitivity tables across exit multiple × leverage. | $5.00 |
| `waterfall_distribute` | LP/GP waterfall with up to 5 promote tiers (IRR or MOIC hurdles). Penny-accurate via Python Decimal. ACT/365. | $3.00 |
| `multifamily_underwrite` | MF acquisition proforma. GPR → NOI → DSCR → exit. Tracks LTV and CoC annually. | $1.00 |
| `str_underwrite` | STR/Airbnb underwriting with GO/NO-GO verdict. Quarterly ADR + occupancy, itemized expenses, 10-year projection. | $1.00 |
| `monte_carlo_simulate` | Monte Carlo with correlated variables (Cholesky). P10/P50/P90. Up to 100,000 trials. | $1.00 |
| `dcf_value` | DCF valuation — exit multiple or Gordon Growth terminal value. Enterprise value, equity value, implied share price, 9×9 WACC sensitivity matrix. | $1.00 |
| `sfr_underwrite` | SFR/DSCR rental proforma. Monthly cash flow model. Tracks DSCR and LTV annually. | $0.50 |
| `fix_flip_underwrite` | Fix & flip. Solves backwards from desired profit to max purchase price. Hard money loan sizing. | $0.50 |
| `xirr_compute` | XIRR on irregular cash flows. PE distributions, RE waterfalls, project finance. | $0.25 |
| `amortization_schedule` | Full amortization schedule. Milestones, IO period support, extra payment scenarios. | $0.25 |
| `fx_pnl` | FX-adjusted P&L. Decomposes return into asset performance vs currency movement. | $0.25 |

All calculations are deterministic, formula-traceable, and Excel-convention compliant. No LLM inside the engine.

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
8% pref, 10% catch-up, IRR hurdles. Tiers: 80/20 to 15%, 75/25 to 18%,
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
Underwrite a 3BR/2BA Folly Beach vacation rental at $650K.
Q1: $220 ADR, 58% occupancy. Q2: $290, 72%. Q3: $380, 88%. Q4: $240, 62%.
Insurance $3,200/yr, property tax $5,800/yr, utilities $3,600/yr.
25% down, 7.25% rate.
```

**SFR:**
```
Underwrite 142 Oak St Greenville SC at $285K: $2,600/month rent,
$850/month expenses, 30% down, 7% rate, 7-year hold, 6% exit cap.
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
GET /str/schema
GET /sfr/schema
GET /fix-flip/schema
GET /xirr/schema
GET /amortization/schema
GET /monte-carlo/schema
GET /fx/schema
GET /dcf/schema
```

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
