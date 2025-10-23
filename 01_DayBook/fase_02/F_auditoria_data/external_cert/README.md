# External Data Certification Suite

**Purpose:** Scientific validation of Polygon data against independent external vendors
**Status:** IMPLEMENTATION IN PROGRESS

---

## Quick Start

```bash
# 1. Download strategic samples (5 Alpha Vantage calls)
python scripts/external_cert_download.py --config config/samples.yaml

# 2. Normalize vendor data to standard schema
python scripts/external_cert_normalize.py

# 3. Run all validation levels
python scripts/external_cert_validate_L1_minute.py  # Minute bars
python scripts/external_cert_validate_L2_daily.py   # Daily bars
python scripts/external_cert_validate_L3_ca.py      # Corporate actions
python scripts/external_cert_triangulate_L4.py      # Multi-vendor consensus

# 4. Generate final certification report
python scripts/external_cert_report.py --output EXTERNAL_CERTIFICATION_REPORT.md
```

---

## Directory Structure

```
external_cert/
├── README.md                      # This file
├── config/
│   └── samples.yaml              # Sample selection + thresholds
├── scripts/
│   ├── external_cert_download.py         # Download from vendors
│   ├── external_cert_normalize.py        # Normalize schemas
│   ├── external_cert_validate_L1_minute.py  # L1 validation
│   ├── external_cert_validate_L2_daily.py   # L2 validation
│   ├── external_cert_validate_L3_ca.py      # L3 validation
│   ├── external_cert_triangulate_L4.py      # L4 triangulation
│   └── external_cert_report.py           # Final GO/NO-GO report
├── raw_data/                      # Raw vendor responses
│   ├── alphavantage/
│   ├── yahoo/
│   └── twelvedata/
├── normalized/                    # Normalized data (UTC, OHLCV)
│   ├── alphavantage/
│   ├── yahoo/
│   └── twelvedata/
├── validation/                    # Validation results
│   ├── L1_minute/
│   ├── L2_daily/
│   ├── L3_ca/
│   └── L4_triangulation/
└── EXTERNAL_CERTIFICATION_REPORT.md  # Final report (generated)
```

---

## Validation Levels

### Level 1: Minute Bars (PRIMARY)
- Compare `ohlcv_intraday_1m` vs Alpha Vantage + Twelve Data
- **Criteria:** Match rate ≥ 98%, price p95 ≤ 0.10%, volume p95 ≤ 4%
- **Output:** `validation/L1_minute/{symbol}_{date}_result.json`

### Level 2: Daily Bars (SECONDARY)
- Compare our minute→daily aggregation vs vendor daily bars
- **Criteria:** OHLC p95 ≤ 0.10%, volume p95 ≤ 3%
- **Output:** `validation/L2_daily/{symbol}_{date}_result.json`

### Level 3: Corporate Actions (CRITICAL)
- Validate splits/dividends factors reproduce adjusted closes
- **Criteria:** Adj close mean ≤ 0.05%, zero split mismatches
- **Output:** `validation/L3_ca/{symbol}_result.json`

### Level 4: Multi-Vendor Triangulation (ADVANCED)
- Compute consensus (median) across 3+ vendors
- Detect outliers using MAD (Median Absolute Deviation)
- **Criteria:** Our data within 2×MAD for 95% of bars
- **Output:** `validation/L4_triangulation/{symbol}_{date}_result.json`

---

## Priority Tickers (From Our Data)

| Symbol | Rationale | Volume Profile |
|--------|-----------|----------------|
| WOLF | Main test case (98.76% validated) | Low |
| AMC | Meme stock, high volatility | High |
| BTBT | Bitcoin mining | Medium |
| GRI | Small cap representative | Low |
| BAER | Small cap representative | Low |

All tickers selected from our actual data inventory (3,110 symbols available).

---

## API Budget

| Vendor | Calls Available | Strategy |
|--------|-----------------|----------|
| **Alpha Vantage** | 5 | 1 call = 1 month (20 days) = 100 ticker-days total |
| **Yahoo Finance** | Unlimited | Download all symbols/dates |
| **Twelve Data** | 6 | Spot checks only |

**Total Validation:** 100+ ticker-days without exhausting API limits

---

## Success Criteria (GO/NO-GO)

### Hard Requirements (NO-GO if fail)
- L1 match rate < 98%
- L1 price deviation > 0.10%
- L2 OHLC deviation > 0.10%
- L3 adjusted close error > 0.05%
- L3 any split factor mismatch

### Soft Requirements (WARNING if fail)
- L1 price mean > 0.05%
- L2 OHLC mean > 0.05%
- L4 outlier rate > 5%

### Decision Tree
```
IF any hard requirement fails → NO-GO
ELIF 2+ soft requirements fail → GO with WARNINGS
ELSE → GO (CERTIFIED)
```

---

## Current Status

- [x] Specification complete ([8.7.2_EXTERNAL_DATA_CERTIFICATION_SPEC.md](../8.7.2_EXTERNAL_DATA_CERTIFICATION_SPEC.md))
- [x] Directory structure created
- [x] Sample configuration created (config/samples.yaml)
- [ ] Download script (scripts/external_cert_download.py) - IN PROGRESS
- [ ] Normalize script (scripts/external_cert_normalize.py) - PENDING
- [ ] L1 validation script - PENDING
- [ ] L2 validation script - PENDING
- [ ] L3 validation script - PENDING
- [ ] L4 triangulation script - PENDING
- [ ] Report generator script - PENDING
- [ ] Execution and final report - PENDING

---

## Documentation

- **Specification:** [8.7.2_EXTERNAL_DATA_CERTIFICATION_SPEC.md](../8.7.2_EXTERNAL_DATA_CERTIFICATION_SPEC.md)
- **Internal Certification:** [7.5_data_summary.md](../../E_data_analisys/7.5_data_summary.md)
- **Previous Validation:** [8.7.1_Data_Certification_Complete.md](../8.7.1_Data_Certification_Complete.md)

---

**Next Steps:** Complete implementation of 7 scripts, execute validation, generate final GO/NO-GO report.
