# PayShield AI
**Predictive Receivables, Cash-Flow & Recovery Intelligence for Indian MSMEs**  
*(Python + Flask + Jinja2/HTML only — No JavaScript, No Frontend Frameworks)*

---

## 1. Guiding Philosophy
$$\text{PREDICT} \longrightarrow \text{VERIFY} \longrightarrow \text{EXPLAIN} \longrightarrow \text{SIMULATE} \longrightarrow \text{ACT} \longrightarrow \text{PROVE} \longrightarrow \text{LEARN}$$

PayShield is an evidence-backed receivables decision-support system and orchestration platform for Indian Micro, Small, and Medium Enterprises (MSMEs). Rather than collapsing credit intelligence into an unexplained, cosmetic "score," PayShield grounds every prediction, legal deadline, and cash flow estimate in verifiable records, right-censored survival curves, and versioned statutory rules under the MSMED Act 2006.

---

## 2. Non-Negotiable Guardrails & Principles

1. **Strict No-JavaScript Architecture**: The entire user interface is server-rendered via Flask, Jinja2, and embedded CSS. No React, Vue, Angular, Node.js, or external JS chart libraries are used. Every interaction (scenario simulation, language switching, action approval) is backed by real server round-trips.
2. **Deterministic Legal Payment Clock**: Legal due dates and MSMED Act Section 15/16 calculations are governed by a deterministic rules engine with versioned parameters (e.g. 45-day statutory outer limit, 15-day deemed acceptance, 3x RBI bank rate compound interest). An ML model never decides legal eligibility.
3. **Right-Censored Survival Modeling**: Unpaid invoices are modeled via `lifelines` Kaplan-Meier / Cox hazard survival analysis, producing probability distributions across time rather than fabricated single dates.
4. **Honest Uncertainty & Abstention**: Sparse data or low OCR quality triggers an explicit **Abstention Path** (*"Insufficient evidence for a reliable buyer-specific prediction"*) rather than hallucinating an overconfident score.
5. **Human Approval Gateway**: AI recommendations require explicit human sign-off (*AI Recommendation $\rightarrow$ Human Approval $\rightarrow$ Send/Execute*).
6. **Strict Multi-Tenant Isolation**: Row-level tenant isolation is enforced at the query layer.

---

## 3. Technology Stack

- **Backend**: Python 3.14+, Flask (blueprints & modular architecture)
- **Database**: SQLite default via SQLAlchemy (swappable to PostgreSQL)
- **ML / Analytics**: `lifelines` (survival analysis), `scikit-learn`, `xgboost`, `shap` (TreeSHAP explanations), `networkx` (buyer-supplier graph), `ortools` (integer programming action optimizer), `pandas`, `numpy`
- **OCR**: `pytesseract` and `Pillow` with regex parsing and prompt-injection neutralization
- **Visuals**: Server-rendered SVG diagrams, HTML/CSS ruled ledgers, tabular numerals
- **Design System**: Paper-and-Ink Ledger Aesthetic (`#1B2430` ledger ink, `#F7F5F0` paper canvas, `#2E4057` institutional seal)

---

## 4. System Architecture: The 12 Engines

The application is structured into 12 dedicated engines under `services/` and `ml/`:

| Engine | File | Description |
|---|---|---|
| **Engine 1: Identity & Consent** | `services/identity_service.py` | Tenant isolation, DPDP Act 2025 consent ledger, audit logging |
| **Engine 2: Document Intelligence** | `services/ocr_service.py` | OCR extraction, confidence scoring, prompt injection defense |
| **Engine 3: Invoice Integrity Shield** | `services/integrity_engine.py` | 3-way match, duplicate detection, date consistency checks |
| **Engine 4: Legal Payment Clock** | `services/legal_rules.py` | MSMED Act 2006 (Sec 15/16/18), 3x RBI interest computation |
| **Engine 5: Buyer Payment DNA** | `services/buyer_dna.py` | Historical behavioral profiling, median/P90 delay metrics |
| **Engine 6: Survival & Delay ML** | `services/survival_engine.py`, `ml/delay_model.py` | Lifelines hazard curves, right-censored P10/P50/P90 payment dates |
| **Engine 7: Explainability & Confidence** | `services/confidence_engine.py` | TreeSHAP Prediction Drivers, multi-factor confidence rating, abstention |
| **Engine 8: CashFlow Digital Twin** | `services/cashflow_engine.py` | Monte Carlo cash runway simulation, Cash Survival Date ($P < \text{₹5L}$) |
| **Engine 9: Rescue What-If Simulator** | `services/scenario_engine.py` | Server-side dynamic recalculation of hypothetical delay shocks |
| **Engine 10: Action Intelligence** | `services/action_engine.py`, `services/optimizer.py` | Google OR-Tools IP optimizer, Human Approval Gateway |
| **Engine 11: Ecosystem Readiness** | `services/treds_engine.py`, `services/odr_engine.py`, `services/evidence_engine.py` | TReDS pass/fail checklist, ODR statutory readiness, SHA-256 evidence |
| **Engine 12: Learning & Governance** | `services/governance.py` | Model drift monitor (PSI), model registry, outcome feedback loop |

---

## 5. Sandboxed / Simulated Integrations

In accordance with Section 16 guardrails, external government and banking connectors are clearly identified with the **`DEMO / SANDBOX`** badge:

1. **Udyam External Verification API** (`services/identity_service.py`, `templates/onboarding.html`)
2. **Account Aggregator (AA) Open Banking Feed** (`services/cashflow_engine.py`, `templates/cashflow.html`)
3. **TReDS Exchange Submission** (`services/treds_engine.py`, `templates/treds.html`)
4. **ODR / MSEFC Portal Filing** (`services/odr_engine.py`, `templates/odr.html`)
5. **Voice Interface Simulation** (`services/assistant_engine.py`, `templates/assistant.html`)

---

## 6. Installation & Quickstart

### Prerequisites
- Python 3.10+ (tested on Python 3.14)
- Pip

### 1. Clone & Install Dependencies
```powershell
cd C:\Users\haitr\.gemini\antigravity\scratch\payshield
python -m pip install -r requirements.txt
```

### 2. Launch the Application
```powershell
python app.py
```
The application will start at `http://127.0.0.1:5000`.

### 3. Quick-Start Demo Persona
- Navigate to `http://127.0.0.1:5000`.
- The database auto-initializes with **Apex Precision Tools Pvt Ltd** (Micro-enterprise, Pune).
- Pre-seeded users:
  - **Proprietor**: `admin@apexprecision.in` / `admin123`
  - **CFO**: `neha@apexprecision.in` / `cfo123`
- Click the **"LOAD DEMO SCENARIO"** button in the dashboard at any time to re-populate the complete scenario.

---

## 7. Testing Suite Execution

Run the complete test suite:
```powershell
python -m pytest -v
```

The test suite validates:
- Multi-tenant query isolation and data leakage protection
- Prompt-injection sanitization
- Section 15 45-day statutory cap and Section 16 compound interest accrual
- 15-day deemed acceptance rule
- Duplicate invoice and date inconsistency detection
- Survival analysis P10/P50/P90 percentile monotonicity
- Cold-start buyer abstention path
- Monte Carlo cash flow forecasting & liquidity gap range
- OR-Tools integer programming action portfolio optimization
- Mandatory Human Approval Gateway
- TReDS and ODR pass/fail checklists
- Tamper-proof SHA-256 Evidence Pack manifest generation

---

## 8. Complete Demo Walkthrough Narrative

1. **Dashboard Overview**: Inspect total receivables (₹88.5L), at-risk receivables, Cash Survival Date, and liquidity gap range.
2. **Invoice Ingestion & OCR**: Upload a tax invoice (PDF/image) and verify field extraction and confidence scoring.
3. **Integrity Anomaly Detection**: Open invoice `INV-2026-STR-41` to inspect a PO/Invoice quantity discrepancy.
4. **Prediction & Explainability**: Open invoice `INV-2026-DLT-88` to examine the right-censored survival payment window and ranked Prediction Drivers.
5. **Cold-Start Abstention**: Inspect invoice `INV-2026-ZNT-01` (Zenith Solar) and verify that the engine abstains from fabricating an ungrounded score.
6. **Rescue Simulator**: In the Rescue Simulator, select *Delta Infrastructure Corp (+30 days late)* and observe the real-time server recalculation of runway lost and liquidity shock.
7. **Collection War Room**: Review OR-Tools prioritized interventions and approve actions through the Human Approval Gateway.
8. **TReDS Checklist**: Review TReDS suitability for BHEL (CPSE mandatory onboarding).
9. **ODR & Evidence Dossier**: View Section 18 statutory eligibility and click *Download Verifiable Evidence Bundle* to export an immutable SHA-256 evidence manifest.
10. **Multilingual & Voice Interface**: Switch languages between English, Hindi, Bengali, Tamil, Telugu, and Marathi, and test the voice simulation confirmation step.
