import json
import random
import string
import uuid
import sys
import os

# Add to path to allow importing app and common_lib
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Python Libs', 'common_lib', 'src')))

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.rules_engine.models import RuleSetModel, RuleModel, RuleSetRuleLink

def get_db_session():
    # Use context manager
    for session in get_session():
        return session

def generate_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))

types = ['conditional', 'policy', 'scoring', 'transformation', 'event_driven', 'stateful', 'workflow', 'anomaly_detection', 'rate_limiting']

def get_random(arr):
    return random.choice(arr)

def seed_db():
    session = get_db_session()
    
    # 1. Create a Rule Set
    rs_id = f"rs_{uuid.uuid4().hex[:8]}"
    rs = RuleSetModel(
        id=rs_id,
        name="Global Platform Rules",
        description="A collection of reusable blocks (simple to comprehensive).",
        enabled=True,
        priority=100
    )
    session.add(rs)
    session.commit()

    all_rules = []
    simple_names = ['IP Blacklist Check', 'Rate Limit Exceeded', 'Missing Auth Token', 'Invalid Payload Schema', 'Geoloc Restricted Area']
    medium_names = ['Guest Access Policy', 'Sensitive Data Access', 'Multiple Failed Logins', 'Unverified Device Connection', 'Weekend Transaction Policy']
    complex_names = ['Botnet Traffic Gateway', 'Payment Fraud Detection', 'Admin Privilege Escalation', 'Compliance Violation Gateway', 'High-Value Transfer Gateway']
    comprehensive_names = ['Enterprise Security Master', 'Financial Integrity Master', 'Regulatory Compliance Master', 'Insider Threat Master', 'System Stability Master']

    simple_rules = []
    medium_rules = []
    complex_rules = []
    comprehensive_rules = []

    # --- 1. Create 5 Simple Rules ---
    for i in range(1, 6):
        r = RuleModel(
            id=f"rule_simple_{i}_{uuid.uuid4().hex[:4]}",
            name=simple_names[i-1],
            type=get_random(types),
            enabled=True,
            priority=10 * i,
            condition_group={
                "id": f"cg_s_{i}",
                "logical_operator": "AND",
                "children": [
                    { "id": f"cond_s1_{i}", "field_path": "request.method", "operator": "eq", "value": "GET" }
                ]
            },
            actions=[
                { "id": f"act_s1_{i}", "action_type": "log", "target": "audit_log", "payload": '{"msg": "Simple rule triggered"}' }
            ],
            metadata_json='{"complexity": "simple"}'
        )
        session.add(r)
        session.add(RuleSetRuleLink(rule_set_id=rs_id, rule_id=r.id))
        simple_rules.append(r)

    # --- 2. Create 5 Medium Rules (built from Simple) ---
    for i in range(1, 6):
        s1, s2 = random.sample(simple_rules, 2)
        r = RuleModel(
            id=f"rule_medium_{i}_{uuid.uuid4().hex[:4]}",
            name=medium_names[i-1],
            type=get_random(types),
            enabled=True,
            priority=20 * i,
            condition_group={
                "id": f"cg_m_{i}",
                "logical_operator": "AND",
                "children": [
                    { "id": f"ref_m1_{i}", "ref_rule_id": s1.id },
                    { "id": f"ref_m2_{i}", "ref_rule_id": s2.id },
                    { "id": f"cond_m1_{i}", "field_path": "user.role", "operator": "eq", "value": "guest" }
                ]
            },
            actions=[
                { "id": f"act_m1_{i}", "action_type": "notify", "target": "security_team", "payload": '{"alert": "Medium rule matched"}' }
            ],
            metadata_json='{"complexity": "medium"}'
        )
        session.add(r)
        session.add(RuleSetRuleLink(rule_set_id=rs_id, rule_id=r.id))
        medium_rules.append(r)

    # --- 3. Create 5 Complex Rules (built from Medium) ---
    for i in range(1, 6):
        m1, m2 = random.sample(medium_rules, 2)
        r = RuleModel(
            id=f"rule_complex_{i}_{uuid.uuid4().hex[:4]}",
            name=complex_names[i-1],
            type=get_random(types),
            enabled=True,
            priority=30 * i,
            condition_group={
                "id": f"cg_c_{i}",
                "logical_operator": "OR",
                "children": [
                    { "id": f"ref_c1_{i}", "ref_rule_id": m1.id },
                    { "id": f"ref_c2_{i}", "ref_rule_id": m2.id }
                ]
            },
            actions=[
                { "id": f"act_c1_{i}", "action_type": "require_mfa", "target": "session", "payload": '{"timeout": 300}' }
            ],
            metadata_json='{"complexity": "complex"}'
        )
        session.add(r)
        session.add(RuleSetRuleLink(rule_set_id=rs_id, rule_id=r.id))
        complex_rules.append(r)

    # --- 4. Create 5 Comprehensive Rules (built from Complex) ---
    for i in range(1, 6):
        c1, c2 = random.sample(complex_rules, 2)
        r = RuleModel(
            id=f"rule_comprehensive_{i}_{uuid.uuid4().hex[:4]}",
            name=comprehensive_names[i-1],
            type=get_random(types),
            enabled=True,
            priority=50 * i,
            condition_group={
                "id": f"cg_comp_{i}",
                "logical_operator": "AND",
                "children": [
                    { "id": f"ref_comp1_{i}", "ref_rule_id": c1.id },
                    { "id": f"ref_comp2_{i}", "ref_rule_id": c2.id },
                    {
                        "id": f"cg_comp_nested_{i}",
                        "logical_operator": "NOT",
                        "children": [
                            { "id": f"cond_comp1_{i}", "field_path": "user.is_vip", "operator": "eq", "value": "true" }
                        ]
                    }
                ]
            },
            actions=[
                { "id": f"act_comp1_{i}", "action_type": "quarantine", "target": "transaction", "payload": '{"review_required": true}' },
                { "id": f"act_comp2_{i}", "action_type": "trigger_workflow", "target": "fraud_review", "payload": '{"priority": "urgent"}' }
            ],
            metadata_json='{"complexity": "comprehensive"}'
        )
        session.add(r)
        session.add(RuleSetRuleLink(rule_set_id=rs_id, rule_id=r.id))
        comprehensive_rules.append(r)

    session.commit()
    print("Database seeded with Rules Engine Data!")

if __name__ == '__main__':
    seed_db()
