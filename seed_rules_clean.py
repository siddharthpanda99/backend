import sys
import os
import uuid
import random
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Python Libs', 'common_lib', 'src')))
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.rules_engine.models import RuleSetModel, RuleModel, RuleSetRuleLink
from sqlmodel import select, delete

def get_db_session():
    for session in get_session(): return session
session = get_db_session()

# Clear everything
session.exec(delete(RuleSetRuleLink))
session.exec(delete(RuleModel))
session.exec(delete(RuleSetModel))
session.commit()

# Insert new RuleSet
rs_id = f'rs_{uuid.uuid4().hex[:8]}'
rs = RuleSetModel(
    id=rs_id,
    name='Global Security Master Rules',
    description='A collection of critical reusable security and platform policies.',
    enabled=True,
    priority=100
)
session.add(rs)

types = ['conditional', 'policy', 'scoring', 'transformation']
names = [
    'IP Blacklist Check', 'Rate Limit Exceeded', 'Missing Auth Token', 'Invalid Payload Schema', 'Geoloc Restricted Area',
    'Guest Access Policy', 'Sensitive Data Access', 'Multiple Failed Logins', 'Unverified Device Connection', 'Weekend Transaction Policy',
    'Botnet Traffic Gateway', 'Payment Fraud Detection', 'Admin Privilege Escalation', 'Compliance Violation Gateway', 'High-Value Transfer Gateway'
]
action_types = ['activate_hook', 'notify', 'flag', 'block', 'log', 'quarantine']
fields = ['request.ip', 'user.role', 'payload.amount', 'device.trusted', 'session.failed_attempts']
operators = ['eq', 'ne', 'gt', 'lt', 'contains']

for i, name in enumerate(names):
    # Generate random conditions
    children = []
    for _ in range(random.randint(1, 3)):
        children.append({
            'id': f'cond_{uuid.uuid4().hex[:6]}',
            'field_path': random.choice(fields),
            'operator': random.choice(operators),
            'value': str(random.randint(1, 100)) if 'amount' in random.choice(fields) else 'true'
        })
    
    # Generate random actions
    actions = []
    for _ in range(random.randint(1, 2)):
        actions.append({
            'id': f'act_{uuid.uuid4().hex[:6]}',
            'action_type': random.choice(action_types),
            'target': 'system',
            'payload': '{}'
        })

    descriptions_map = {
        'IP Blacklist Check': 'Blocks traffic from known malicious IP addresses globally.',
        'Rate Limit Exceeded': 'Triggers a temporary ban or cooldown when API requests exceed normal thresholds.',
        'Missing Auth Token': 'Rejects access attempts that lack valid authentication credentials.',
        'Invalid Payload Schema': 'Validates incoming request bodies against predefined strict schemas.',
        'Geoloc Restricted Area': 'Prevents access from embargoed or high-risk geographic locations.',
        'Guest Access Policy': 'Restricts guest user privileges and data access scope.',
        'Sensitive Data Access': 'Monitors and flags access to PII and highly confidential system records.',
        'Multiple Failed Logins': 'Detects brute-force attempts and enforces temporary account lockouts.',
        'Unverified Device Connection': 'Challenges connections from new, unverified devices with MFA.',
        'Weekend Transaction Policy': 'Applies strict approval thresholds for transactions occurring outside business hours.',
        'Botnet Traffic Gateway': 'Filters suspected automated bot traffic using behavioral analysis.',
        'Payment Fraud Detection': 'Evaluates transaction patterns to flag potential fraudulent activity.',
        'Admin Privilege Escalation': 'Logs and alerts on any unauthorized attempts to escalate privileges.',
        'Compliance Violation Gateway': 'Ensures actions comply with regulatory data protection guidelines.',
        'High-Value Transfer Gateway': 'Requires multi-party approval for transactions exceeding $10,000.'
    }

    # metadata
    meta = {
        'description': descriptions_map.get(name, f'This rule evaluates {len(children)} condition(s) and executes {len(actions)} action(s).'),
        'author': 'System Admin',
        'version': '1.0'
    }

    r = RuleModel(
        id=f'rule_{uuid.uuid4().hex[:12]}',
        name=name,
        type=random.choice(types),
        enabled=True,
        priority=10 * (i+1),
        condition_group={'id': 'root', 'logical_operator': 'AND', 'children': children},
        actions=actions,
        metadata_json=json.dumps(meta)
    )
    session.add(r)
    session.add(RuleSetRuleLink(rule_set_id=rs_id, rule_id=r.id))

session.commit()
print('Seeded cleanly with conditions and actions.')
