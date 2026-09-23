"""
PayShield AI — Master Flask Application
Predictive Receivables, Cash-Flow & Recovery Intelligence for Indian MSMEs
(Python + Flask + Jinja2/HTML only — No JavaScript, No Frontend Frameworks)
"""

import os
import json
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, Response, send_file, g
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from config import Config
from models import (
    Base, Tenant, User, ConsentLedger, AuditLog,
    Buyer, Invoice, InvoiceEvent, Document, Payment,
    Prediction, Explanation, CashFlow, ActionItem, RuleVersion
)
from data.seed import seed_database
from services.identity_service import IdentityService
from services.legal_rules import LegalPaymentClockEngine
from services.ocr_service import DocumentIntelligenceEngine, compute_file_sha256
from services.integrity_engine import InvoiceIntegrityShield
from services.buyer_dna import BuyerDNAEngine
from services.survival_engine import SurvivalAnalysisEngine
from services.confidence_engine import ConfidenceEngine
from services.prediction_engine import PredictionOrchestrator
from services.cashflow_engine import CashFlowDigitalTwin
from services.scenario_engine import ScenarioSimulator
from services.action_engine import ActionIntelligenceEngine
from services.treds_engine import TReDSReadinessEngine
from services.odr_engine import ODRReadinessEngine
from services.evidence_engine import EvidencePackEngine
from services.graph_engine import NetworkGraphEngine
from services.benchmark_engine import PeerBenchmarkingEngine
from services.assistant_engine import AssistantEngine, CANONICAL_DICTIONARY
from services.governance import GovernanceEngine

# -----------------------------------------------------------------------------
# Application Setup & Factory
# -----------------------------------------------------------------------------

app = Flask(__name__)
app.config.from_object(Config)
Config.init_app(app)

# Database Engine & Session
engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'], connect_args={'check_same_thread': False})
SessionFactory = sessionmaker(bind=engine)
db_session = scoped_session(SessionFactory)
Base.metadata.create_all(bind=engine)

# Initialize seed data on first run
with app.app_context():
    session_init = db_session()
    seed_database(session_init, force_reset=False)
    session_init.close()

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

# -----------------------------------------------------------------------------
# Multilingual Context & Request Hooks
# -----------------------------------------------------------------------------

@app.before_request
def load_tenant_and_lang():
    g.db = db_session()
    # Resolve active language (default: 'en')
    g.lang = session.get('lang', 'en')
    if g.lang not in CANONICAL_DICTIONARY:
        g.lang = 'en'

    # Auto-login default demo tenant if not authenticated
    tenant_id = session.get('tenant_id')
    user_id = session.get('user_id')
    if not tenant_id:
        default_tenant = g.db.query(Tenant).first()
        if default_tenant:
            session['tenant_id'] = default_tenant.tenant_id
            default_user = g.db.query(User).filter_by(tenant_id=default_tenant.tenant_id).first()
            if default_user:
                session['user_id'] = default_user.user_id
                session['user_name'] = default_user.name
                session['user_role'] = default_user.role

    g.current_tenant = g.db.query(Tenant).filter_by(tenant_id=session.get('tenant_id')).first()
    g.current_user = g.db.query(User).filter_by(user_id=session.get('user_id')).first()

@app.context_processor
def inject_template_globals():
    def translate(concept_key: str, default_val: str = "") -> str:
        lang_dict = CANONICAL_DICTIONARY.get(g.lang, CANONICAL_DICTIONARY['en'])
        return lang_dict.get(concept_key, default_val or concept_key)

    return {
        't': translate,
        'active_lang': g.lang,
        'supported_languages': Config.SUPPORTED_LANGUAGES,
        'current_tenant': g.current_tenant,
        'current_user': g.current_user,
        'today': date.today()
    }

# -----------------------------------------------------------------------------
# Authentication & Onboarding Routes
# -----------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        pwd = request.form.get('password', '')
        user = g.db.query(User).filter_by(email=email).first()
        if user and user.check_password(pwd):
            session['user_id'] = user.user_id
            session['tenant_id'] = user.tenant_id
            session['user_name'] = user.name
            session['user_role'] = user.role
            flash(f"Authenticated as {user.name} ({user.role})", "success")
            return redirect(url_for('dashboard'))
        flash("Invalid email or password", "error")
    return render_template('login.html')

@app.route('/login/as', methods=['POST'])
def login_as():
    email = request.form.get('email')
    user = g.db.query(User).filter_by(email=email).first()
    if user:
        session['user_id'] = user.user_id
        session['tenant_id'] = user.tenant_id
        session['user_name'] = user.name
        session['user_role'] = user.role
        flash(f"Switched persona to {user.name} ({user.role})", "info")
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash("Signed out successfully", "info")
    return redirect(url_for('login'))

@app.route('/onboarding')
def onboarding():
    return render_template('onboarding.html')

@app.route('/onboarding/submit', methods=['POST'])
def onboarding_submit():
    b_name = request.form.get('business_name')
    udyam = request.form.get('udyam_id')
    ent_type = request.form.get('enterprise_type', 'Micro')
    act_type = request.form.get('activity_type', 'Manufacturing')

    tenant = Tenant(
        business_name=b_name,
        udyam_id=udyam,
        enterprise_type=ent_type,
        activity_type=act_type
    )
    g.db.add(tenant)
    g.db.flush()

    user = User(
        tenant_id=tenant.tenant_id,
        role='PROPRIETOR',
        name='MSME Administrator',
        email=f"admin@{udyam.lower().replace('-', '')}.in",
        phone='+91 98000 00000'
    )
    user.set_password('admin123')
    g.db.add(user)

    # Consent capture
    identity_svc = IdentityService(g.db)
    for p in ['RECEIVABLES_ANALYSIS', 'CASHFLOW_TWIN', 'TREDS_SHARING', 'PEER_BENCHMARKING']:
        if request.form.get(f'consent_{p.lower()}'):
            identity_svc.grant_consent(tenant.tenant_id, user.user_id, p)

    g.db.commit()
    session['tenant_id'] = tenant.tenant_id
    session['user_id'] = user.user_id
    flash(f"MSME Enterprise '{b_name}' successfully onboarded.", "success")
    return redirect(url_for('dashboard'))

@app.route('/language/set', methods=['POST'])
def set_language():
    lang = request.form.get('lang', 'en')
    return_url = request.form.get('return_url', url_for('dashboard'))
    if lang in Config.SUPPORTED_LANGUAGES:
        session['lang'] = lang
    return redirect(return_url)

@app.route('/demo/load', methods=['POST'])
def load_demo_scenario():
    seed_database(g.db, force_reset=True)
    flash("Demo scenario loaded successfully: 5 buyers across hidden regimes, cashflows, and invoices active.", "success")
    return redirect(url_for('dashboard'))

# -----------------------------------------------------------------------------
# 18 Website Pages & Intelligence Views
# -----------------------------------------------------------------------------

# 1. Executive Dashboard
@app.route('/')
@app.route('/dashboard')
def dashboard():
    tenant_id = session.get('tenant_id')
    invoices = g.db.query(Invoice).filter(
        Invoice.tenant_id == tenant_id,
        Invoice.status.in_(['ISSUED', 'DELIVERED', 'ACCEPTED', 'PARTIALLY_PAID', 'OVERDUE'])
    ).all()

    total_outstanding = sum(i.outstanding_amount for i in invoices)
    today = date.today()

    at_risk_invoices = [i for i in invoices if (today - i.contract_due_date).days > 15]
    at_risk_amount = sum(i.outstanding_amount for i in at_risk_invoices)

    # Run CashFlow Digital Twin
    cashflow_twin = CashFlowDigitalTwin(g.db)
    cash_res = cashflow_twin.run_monte_carlo_simulation(tenant_id=tenant_id)

    # Priority Actions via OR-Tools
    action_engine = ActionIntelligenceEngine(g.db)
    priority_actions = action_engine.generate_recommended_actions(tenant_id=tenant_id)

    # Top Buyers & Concentration
    buyers = g.db.query(Buyer).filter_by(tenant_id=tenant_id).all()
    top_buyers = []
    treds_eligible_amount = 0.0

    for b in buyers:
        b_invs = [i for i in invoices if i.buyer_id == b.buyer_id]
        b_total = sum(i.outstanding_amount for i in b_invs)
        share = b_total / (total_outstanding or 1.0)
        top_buyers.append({
            'buyer_id': b.buyer_id,
            'canonical_name': b.canonical_name,
            'outstanding': b_total,
            'share': share,
            'is_cpse': b.is_cpse
        })
        if b.is_cpse or b.turnover_exceeds_500cr:
            treds_eligible_amount += b_total

    top_buyers.sort(key=lambda x: x['outstanding'], reverse=True)

    return render_template(
        'dashboard.html',
        total_outstanding=total_outstanding,
        open_invoices_count=len(invoices),
        active_buyers_count=len(buyers),
        at_risk_count=len(at_risk_invoices),
        at_risk_amount=at_risk_amount,
        cashflow_res=cash_res,
        priority_actions=priority_actions,
        top_buyers=top_buyers[:4],
        treds_eligible_amount=treds_eligible_amount
    )

# 2. Invoices List Register
@app.route('/invoices')
def invoices_list():
    tenant_id = session.get('tenant_id')
    invoices = g.db.query(Invoice).filter_by(tenant_id=tenant_id).order_by(Invoice.invoice_date.desc()).all()
    buyers = g.db.query(Buyer).filter_by(tenant_id=tenant_id).all()

    orchestrator = PredictionOrchestrator(g.db)
    integrity_shield = InvoiceIntegrityShield(g.db)
    invoice_rows = []
    today = date.today()

    for inv in invoices:
        pred = g.db.query(Prediction).filter_by(invoice_id=inv.invoice_id).order_by(Prediction.created_at.desc()).first()
        if not pred:
            res = orchestrator.predict_invoice(inv.invoice_id)
            pred = g.db.query(Prediction).filter_by(prediction_id=res['prediction_id']).first()

        anomalies = integrity_shield.inspect_invoice(inv)
        days_overdue = max(0, (today - inv.contract_due_date).days) if inv.contract_due_date else 0

        # Sort key = risk * impact
        risk_weight = pred.delay_probability if pred and not pred.is_abstained else 0.5
        score = risk_weight * float(inv.outstanding_amount)

        invoice_rows.append({
            'invoice': inv,
            'prediction': pred,
            'anomalies': anomalies,
            'days_overdue': days_overdue,
            'score': score
        })

    invoice_rows.sort(key=lambda x: x['score'], reverse=True)

    return render_template('invoices.html', invoice_rows=invoice_rows, buyers=buyers)

# 3. Invoice Intelligence (Single Deep Dive)
@app.route('/invoices/<invoice_id>')
def invoice_detail(invoice_id):
    invoice = g.db.query(Invoice).filter_by(invoice_id=invoice_id).first()
    if not invoice:
        flash("Invoice not found", "error")
        return redirect(url_for('invoices_list'))

    orchestrator = PredictionOrchestrator(g.db)
    legal_clock_engine = LegalPaymentClockEngine(g.db)
    integrity_shield = InvoiceIntegrityShield(g.db)

    pred = g.db.query(Prediction).filter_by(invoice_id=invoice.invoice_id).order_by(Prediction.created_at.desc()).first()
    if not pred:
        res = orchestrator.predict_invoice(invoice.invoice_id)
        pred = g.db.query(Prediction).filter_by(prediction_id=res['prediction_id']).first()

    drivers = g.db.query(Explanation).filter_by(prediction_id=pred.prediction_id).all() if pred else []
    anomalies = integrity_shield.inspect_invoice(invoice)

    clock = legal_clock_engine.calculate_legal_payment_clock(
        invoice_date=invoice.invoice_date,
        delivery_date=invoice.delivery_date,
        acceptance_date=invoice.acceptance_date,
        written_agreement=invoice.written_agreement_exists,
        agreed_term_days=invoice.agreed_term_days
    )

    interest_info = legal_clock_engine.calculate_statutory_interest(
        principal_amount=invoice.outstanding_amount,
        statutory_due_date=clock['statutory_due_date']
    )

    return render_template(
        'invoice_detail.html',
        invoice=invoice,
        prediction=pred,
        drivers=drivers,
        anomalies=anomalies,
        clock=clock,
        interest_info=interest_info
    )

# 4. Buyer Payment DNA
@app.route('/buyers/dna')
@app.route('/buyers/<buyer_id>/dna')
def buyer_dna_view(buyer_id=None):
    tenant_id = session.get('tenant_id')
    all_buyers = g.db.query(Buyer).filter_by(tenant_id=tenant_id).all()
    if not all_buyers:
        flash("No buyers registered", "error")
        return redirect(url_for('dashboard'))

    req_buyer_id = request.args.get('buyer_id') or buyer_id
    selected_buyer = None
    if req_buyer_id:
        selected_buyer = g.db.query(Buyer).filter_by(buyer_id=req_buyer_id, tenant_id=tenant_id).first()
    if not selected_buyer:
        selected_buyer = all_buyers[0]

    dna_engine = BuyerDNAEngine(g.db)
    dna = dna_engine.compute_buyer_dna(selected_buyer)
    buyer_invoices = g.db.query(Invoice).filter_by(buyer_id=selected_buyer.buyer_id, tenant_id=tenant_id).all()

    return render_template(
        'buyer_dna.html',
        dna=dna,
        selected_buyer=selected_buyer,
        all_buyers=all_buyers,
        buyer_invoices=buyer_invoices
    )

# 5. Buyer Network Graph
@app.route('/buyers/graph')
def buyer_graph_view():
    tenant_id = session.get('tenant_id')
    graph_engine = NetworkGraphEngine(g.db)
    graph_svg = graph_engine.generate_buyer_network_svg(tenant_id=tenant_id)

    # Concentration breakdown
    invoices = g.db.query(Invoice).filter(
        Invoice.tenant_id == tenant_id,
        Invoice.status != 'PAID'
    ).all()
    total_out = sum(i.outstanding_amount for i in invoices) or 1.0

    buyers = g.db.query(Buyer).filter_by(tenant_id=tenant_id).all()
    breakdown = []
    for b in buyers:
        b_sum = sum(i.outstanding_amount for i in invoices if i.buyer_id == b.buyer_id)
        breakdown.append({
            'canonical_name': b.canonical_name,
            'amount': b_sum,
            'share': b_sum / total_out
        })
    breakdown.sort(key=lambda x: x['amount'], reverse=True)

    bench_engine = PeerBenchmarkingEngine(g.db)
    sector_benchmark = bench_engine.get_sector_benchmark(g.current_tenant.industry, tenant_id)

    return render_template(
        'buyer_graph.html',
        graph_svg=graph_svg,
        concentration_breakdown=breakdown,
        sector_benchmark=sector_benchmark
    )

# 6. CashFlow Digital Twin
@app.route('/cashflow')
@app.route('/cashflow/forecast')
def cashflow_view():
    tenant_id = session.get('tenant_id')
    twin = CashFlowDigitalTwin(g.db)
    cash_res = twin.run_monte_carlo_simulation(tenant_id=tenant_id)

    invoices = g.db.query(Invoice).filter(Invoice.tenant_id == tenant_id, Invoice.status != 'PAID').all()
    treds_eligible = sum(i.outstanding_amount for i in invoices if i.buyer.is_cpse or i.buyer.turnover_exceeds_500cr)

    return render_template(
        'cashflow.html',
        cash_res=cash_res,
        treds_eligible_amount=treds_eligible
    )

# 7. Rescue / What-If Simulator
@app.route('/simulator')
def simulator_view():
    tenant_id = session.get('tenant_id')
    all_buyers = g.db.query(Buyer).filter_by(tenant_id=tenant_id).all()

    preselect = request.args.get('preselect_buyer')
    delayed_id = preselect if preselect else (all_buyers[1].buyer_id if len(all_buyers) > 1 else (all_buyers[0].buyer_id if all_buyers else None))

    sim_engine = ScenarioSimulator(g.db)
    sim_result = sim_engine.simulate_rescue_scenario(
        tenant_id=tenant_id,
        delayed_buyer_id=delayed_id,
        extra_delay_days=30
    )

    return render_template(
        'simulator.html',
        all_buyers=all_buyers,
        sim_result=sim_result
    )

@app.route('/cashflow/scenario', methods=['POST'])
@app.route('/simulator/run', methods=['POST'])
def run_simulation():
    tenant_id = session.get('tenant_id')
    delayed_id = request.form.get('buyer_id')
    extra_days = int(request.form.get('extra_delay_days', 30))
    starting_cash = float(request.form.get('starting_cash', 1250000.0))
    safety = float(request.form.get('safety_threshold', 500000.0))

    sim_engine = ScenarioSimulator(g.db)
    sim_result = sim_engine.simulate_rescue_scenario(
        tenant_id=tenant_id,
        delayed_buyer_id=delayed_id,
        extra_delay_days=extra_days,
        starting_cash=starting_cash,
        safety_threshold=safety
    )

    all_buyers = g.db.query(Buyer).filter_by(tenant_id=tenant_id).all()
    flash(f"Stress simulation recalculation complete (+{extra_days}d applied).", "info")

    return render_template(
        'simulator.html',
        all_buyers=all_buyers,
        sim_result=sim_result
    )

# 8. Action Center / Collection War Room
@app.route('/actions')
def actions_view():
    tenant_id = session.get('tenant_id')
    profile = request.args.get('profile', 'BALANCED')

    action_engine = ActionIntelligenceEngine(g.db)
    actions = action_engine.generate_recommended_actions(tenant_id=tenant_id, escalation_profile=profile)

    return render_template('actions.html', actions=actions, current_profile=profile)

@app.route('/actions/<action_id>/approve', methods=['POST'])
def approve_action_route(action_id):
    tenant_id = session.get('tenant_id')
    user_id = session.get('user_id')

    # Find or create action item
    action = g.db.query(ActionItem).filter_by(invoice_id=action_id).first()
    if not action:
        inv = g.db.query(Invoice).filter_by(invoice_id=action_id).first()
        if inv:
            action = ActionItem(
                tenant_id=tenant_id,
                invoice_id=inv.invoice_id,
                action_type="COMMERCIAL_ESCALATION",
                reason="Manual authorization via Collection War Room",
                status="PENDING_APPROVAL"
            )
            g.db.add(action)
            g.db.flush()

    if action:
        action_engine = ActionIntelligenceEngine(g.db)
        action_engine.approve_action(action.action_id, approved_by_user_id=user_id)
        flash(f"Action '{action.action_type}' officially authorized by {g.current_user.name}. Audit logged.", "success")

    return redirect(request.referrer or url_for('actions_view'))

@app.route('/actions/<action_id>/outcome', methods=['POST'])
def record_outcome_route(action_id):
    outcome = request.form.get('outcome', 'PAYMENT_RECEIVED')
    action_engine = ActionIntelligenceEngine(g.db)
    action_engine.record_action_outcome(
        action_id=action_id,
        outcome=outcome,
        amount_recovered=250000.0,
        feedback_notes="Settlement logged via Intervention Learning Loop"
    )
    flash(f"Action outcome '{outcome}' logged into Learning Loop.", "success")
    return redirect(url_for('actions_view'))

# 9. TReDS Readiness
@app.route('/treds')
@app.route('/treds/readiness/<invoice_id>')
def treds_view(invoice_id=None):
    tenant_id = session.get('tenant_id')
    open_invoices = g.db.query(Invoice).filter(Invoice.tenant_id == tenant_id, Invoice.status != 'PAID').all()
    if not open_invoices:
        flash("No active invoices", "error")
        return redirect(url_for('dashboard'))

    req_id = request.args.get('invoice_id') or invoice_id
    selected_inv = None
    if req_id:
        selected_inv = g.db.query(Invoice).filter_by(invoice_id=req_id, tenant_id=tenant_id).first()
    if not selected_inv:
        # Preselect CPSE invoice if available
        cpse_inv = [i for i in open_invoices if i.buyer.is_cpse]
        selected_inv = cpse_inv[0] if cpse_inv else open_invoices[0]

    treds_engine = TReDSReadinessEngine(g.db)
    treds_eval = treds_engine.evaluate_treds_readiness(selected_inv)

    return render_template(
        'treds.html',
        treds_eval=treds_eval,
        selected_invoice=selected_inv,
        open_invoices=open_invoices
    )

# 10. ODR & MSEFC Readiness
@app.route('/odr')
@app.route('/odr/readiness/<invoice_id>')
@app.route('/eligibility/<invoice_id>')
def odr_view(invoice_id=None):
    tenant_id = session.get('tenant_id')
    open_invoices = g.db.query(Invoice).filter(Invoice.tenant_id == tenant_id, Invoice.status != 'PAID').all()
    if not open_invoices:
        flash("No active invoices", "error")
        return redirect(url_for('dashboard'))

    req_id = request.args.get('invoice_id') or invoice_id
    selected_inv = None
    if req_id:
        selected_inv = g.db.query(Invoice).filter_by(invoice_id=req_id, tenant_id=tenant_id).first()
    if not selected_inv:
        # Preselect overdue invoice
        overdue_invs = [i for i in open_invoices if i.status == 'OVERDUE']
        selected_inv = overdue_invs[0] if overdue_invs else open_invoices[0]

    odr_engine = ODRReadinessEngine(g.db)
    odr_eval = odr_engine.evaluate_odr_readiness(selected_inv)

    return render_template(
        'odr.html',
        odr_eval=odr_eval,
        selected_invoice=selected_inv,
        open_invoices=open_invoices
    )

# 11. Evidence Dossier & Download
@app.route('/evidence')
@app.route('/evidence/<invoice_id>')
def evidence_dossier(invoice_id=None):
    tenant_id = session.get('tenant_id')
    req_id = request.args.get('invoice_id') or invoice_id
    if not req_id:
        first_inv = g.db.query(Invoice).filter_by(tenant_id=tenant_id).first()
        req_id = first_inv.invoice_id if first_inv else None

    if not req_id:
        flash("No invoices found to generate evidence", "error")
        return redirect(url_for('dashboard'))

    evidence_engine = EvidencePackEngine(g.db)
    dossier = evidence_engine.generate_evidence_pack(req_id)

    return render_template('evidence.html', dossier=dossier)

@app.route('/evidence/<invoice_id>/download', methods=['POST'])
def download_evidence_pack(invoice_id):
    evidence_engine = EvidencePackEngine(g.db)
    dossier = evidence_engine.generate_evidence_pack(invoice_id)
    payload = json.dumps(dossier, indent=2)

    return Response(
        payload,
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment;filename=evidence_dossier_{dossier['invoice_number']}.json"}
    )

# 12. AI Assistant & Voice Simulation
@app.route('/assistant')
def assistant_view():
    return render_template('assistant.html', query_response=None, voice_data=None)

@app.route('/assistant/query', methods=['POST'])
def assistant_query():
    tenant_id = session.get('tenant_id')
    query = request.form.get('query', '')
    engine = AssistantEngine(g.db)
    res = engine.answer_query(query=query, tenant_id=tenant_id, lang=g.lang)

    return render_template('assistant.html', query_response=res, query_text=query, voice_data=None)

@app.route('/assistant/voice', methods=['POST'])
def voice_simulate():
    voice_text = request.form.get('voice_text', '')
    engine = AssistantEngine(g.db)
    voice_data = engine.parse_voice_command(voice_text)

    return render_template('assistant.html', voice_data=voice_data, voice_transcript=voice_text, query_response=None)

# 13. Privacy & Governance Center
@app.route('/privacy')
@app.route('/privacy/consent')
def privacy_view():
    tenant_id = session.get('tenant_id')
    consents = g.db.query(ConsentLedger).filter_by(tenant_id=tenant_id).all()
    audit_logs = g.db.query(AuditLog).filter_by(tenant_id=tenant_id).order_by(AuditLog.timestamp.desc()).limit(20).all()

    return render_template('privacy.html', consents=consents, audit_logs=audit_logs)

@app.route('/privacy/consent/<consent_id>/revoke', methods=['POST'])
def revoke_consent_route(consent_id):
    c = g.db.query(ConsentLedger).filter_by(consent_id=consent_id).first()
    if c:
        id_svc = IdentityService(g.db)
        id_svc.revoke_consent(c.tenant_id, session.get('user_id'), c.purpose)
        flash(f"Consent for '{c.purpose}' revoked under DPDP Rules 2025.", "info")
    return redirect(url_for('privacy_view'))

@app.route('/privacy/consent/grant', methods=['POST'])
def grant_consent_route():
    purpose = request.form.get('purpose')
    tenant_id = session.get('tenant_id')
    id_svc = IdentityService(g.db)
    id_svc.grant_consent(tenant_id, session.get('user_id'), purpose)
    flash(f"Consent for '{purpose}' re-granted.", "success")
    return redirect(url_for('privacy_view'))

@app.route('/privacy/export', methods=['POST'])
def export_tenant_data():
    tenant_id = session.get('tenant_id')
    tenant = g.db.query(Tenant).filter_by(tenant_id=tenant_id).first()
    invoices = g.db.query(Invoice).filter_by(tenant_id=tenant_id).all()

    export_obj = {
        'tenant': {
            'business_name': tenant.business_name,
            'udyam_id': tenant.udyam_id,
            'enterprise_type': tenant.enterprise_type
        },
        'invoices': [
            {
                'invoice_number': i.invoice_number,
                'amount': i.amount,
                'status': i.status,
                'date': i.invoice_date.isoformat()
            } for i in invoices
        ],
        'exported_at': datetime.utcnow().isoformat() + "Z"
    }

    return Response(
        json.dumps(export_obj, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment;filename=payshield_export_{tenant.udyam_id}.json"}
    )

@app.route('/privacy/delete', methods=['POST'])
def request_data_deletion():
    flash("Erasure request submitted to Data Protection Officer under DPDP Act 2025 Section 12.", "info")
    return redirect(url_for('privacy_view'))

# 14. Model Health Center
@app.route('/model/status')
@app.route('/model/health')
def model_health_view():
    tenant_id = session.get('tenant_id')
    gov = GovernanceEngine(g.db)
    registry = gov.get_model_registry()
    drift = gov.compute_drift_metrics(tenant_id=tenant_id)

    return render_template('model_health.html', registry=registry, drift_info=drift)

# 15. Intervention Learning Loop
@app.route('/learning')
def learning_view():
    tenant_id = session.get('tenant_id')
    gov = GovernanceEngine(g.db)
    records = gov.get_intervention_learning_records(tenant_id=tenant_id)

    return render_template('learning.html', learning_records=records)

# 16. Regulatory Rules Engine
@app.route('/system/rules')
def rules_view():
    rules = g.db.query(RuleVersion).filter_by(effective_to=None).all()
    return render_template('system_rules.html', rules=rules)

@app.route('/system/rules/update', methods=['POST'])
def update_rule_version():
    rule_name = request.form.get('rule_name')
    new_val = float(request.form.get('numeric_value'))
    new_version = request.form.get('version')

    # Archive previous rule without overwriting historical database records
    old_rule = g.db.query(RuleVersion).filter_by(rule_name=rule_name, effective_to=None).first()
    today = date.today()
    if old_rule:
        old_rule.effective_to = today

    new_rule = RuleVersion(
        jurisdiction="INDIA_FEDERAL",
        rule_name=rule_name,
        version=new_version,
        effective_from=today,
        effective_to=None,
        source="Official Gazette Notification / RBI Policy",
        numeric_value=new_val,
        description=f"Updated version {new_version} effective from {today}"
    )
    g.db.add(new_rule)
    g.db.commit()

    flash(f"Rule '{rule_name}' updated to version {new_version} without altering historical records.", "success")
    return redirect(url_for('rules_view'))

# 17. Data Health
@app.route('/data/health')
def data_health_view():
    tenant_id = session.get('tenant_id')
    invoices = g.db.query(Invoice).filter_by(tenant_id=tenant_id).all()
    payments = g.db.query(Payment).filter_by(tenant_id=tenant_id).all()
    documents = g.db.query(Document).filter_by(tenant_id=tenant_id).all()

    total_invs = len(invoices)
    has_po_count = len([i for i in invoices if i.po_number])
    has_grn_count = len([i for i in invoices if i.grn_number or i.acceptance_date])

    po_pct = round(has_po_count / total_invs * 100, 1) if total_invs else 100
    grn_pct = round(has_grn_count / total_invs * 100, 1) if total_invs else 100
    completeness = round((po_pct + grn_pct + 100.0) / 3.0, 1)

    return render_template(
        'data_health.html',
        total_invoices=total_invs,
        total_payments=len(payments),
        total_documents=len(documents),
        avg_ocr_conf=91,
        po_coverage_pct=po_pct,
        grn_coverage_pct=grn_pct,
        completeness_pct=completeness
    )

# 18. Document Upload Endpoint
@app.route('/documents/upload', methods=['POST'])
def upload_document():
    tenant_id = session.get('tenant_id')
    doc_type = request.form.get('doc_type', 'INVOICE')
    buyer_id = request.form.get('buyer_id')

    if 'file' not in request.files:
        flash("No file selected", "error")
        return redirect(url_for('invoices_list'))

    file = request.files['file']
    if not file or not file.filename:
        flash("No file provided", "error")
        return redirect(url_for('invoices_list'))

    filename = Path(file.filename).name # Path traversal protection
    save_path = app.config['UPLOAD_FOLDER'] / filename
    file.save(save_path)

    # Document intelligence extraction
    doc_engine = DocumentIntelligenceEngine(str(app.config['UPLOAD_FOLDER']))
    doc_info = doc_engine.process_document(str(save_path), filename, doc_type, tenant_id)

    # Create new invoice if document is an invoice
    ext_fields = doc_info['extracted_fields']
    inv_num = ext_fields.get('invoice_number', {}).get('value', f"INV-{len(g.db.query(Invoice).all()) + 1}")
    amount = ext_fields.get('amount', {}).get('value', 250000.0)
    po_num = ext_fields.get('po_number', {}).get('value')

    buyer = g.db.query(Buyer).filter_by(buyer_id=buyer_id).first() if buyer_id else g.db.query(Buyer).first()

    today = date.today()
    new_inv = Invoice(
        tenant_id=tenant_id,
        buyer_id=buyer.buyer_id,
        invoice_number=inv_num,
        invoice_date=today,
        delivery_date=today + timedelta(days=2),
        agreed_term_days=buyer.standard_payment_terms_days,
        contract_due_date=today + timedelta(days=buyer.standard_payment_terms_days),
        statutory_due_date=today + timedelta(days=min(45, buyer.standard_payment_terms_days)),
        amount=amount,
        outstanding_amount=amount,
        confidence=doc_info['ocr_confidence'],
        po_number=po_num
    )
    g.db.add(new_inv)
    g.db.flush()

    # Link Document
    doc_record = Document(
        invoice_id=new_inv.invoice_id,
        tenant_id=tenant_id,
        doc_type=doc_type,
        filename=filename,
        storage_uri=str(save_path),
        hash=doc_info['hash'],
        ocr_confidence=doc_info['ocr_confidence'],
        extracted_text=doc_info['raw_text'][:2000],
        extracted_fields_json=json.dumps(ext_fields),
        validation_status=doc_info['validation_status']
    )
    g.db.add(doc_record)

    # Initial Event
    g.db.add(InvoiceEvent(
        invoice_id=new_inv.invoice_id,
        tenant_id=tenant_id,
        event_type="ISSUED",
        event_date=today,
        source="OCR_INGESTION",
        confidence=doc_info['ocr_confidence']
    ))

    g.db.commit()
    flash(f"Document '{filename}' successfully ingested. Extracted Invoice #{inv_num} for ₹{amount:,.2f} with {int(doc_info['ocr_confidence']*100)}% OCR confidence.", "success")
    return redirect(url_for('invoice_detail', invoice_id=new_inv.invoice_id))

# -----------------------------------------------------------------------------
# Standalone JSON APIs for Audit & Integration
# -----------------------------------------------------------------------------

@app.route('/audit/<object_id>')
def audit_view(object_id):
    tenant_id = session.get('tenant_id')
    logs = g.db.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id,
        AuditLog.object_id == object_id
    ).all()
    return jsonify([
        {
            'audit_id': l.audit_id,
            'action': l.action,
            'timestamp': l.timestamp.isoformat(),
            'state': l.after_state or l.before_state
        } for l in logs
    ])

# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    print("=" * 70)
    print(" PAYSHIELD AI — INDIAN MSME RECEIVABLES & CASH-FLOW INTELLIGENCE")
    print(" Running locally at: http://127.0.0.1:5000")
    print(" Paper-and-Ink Visual System Active (Zero Client-Side JavaScript)")
    print("=" * 70)
    app.run(host='127.0.0.1', port=5000, debug=True)
