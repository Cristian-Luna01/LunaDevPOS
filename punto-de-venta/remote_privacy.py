"""Reduce identificadores y texto libre en la réplica central; no altera reportes locales."""
import hashlib

PROFILE = 'central-minima-v1'


def fingerprint(value):
    return hashlib.sha256(f'{PROFILE}:{value}'.encode()).hexdigest()


def direction(data):
    return {
        **data,
        'suppliers': [{**s, 'contact': '', 'phone': ''} for s in data['suppliers']],
        'shifts': [{**s, 'user': 'Operador'} for s in data['shifts']],
        'history_fingerprints': {day: fingerprint(value) for day, value in data['history_fingerprints'].items()},
    }


def history(data):
    return {
        **data,
        'cash_movements': [
            {**m, 'user_name': 'Operador', 'concept': '', 'invoice_ref': ''}
            for m in data.get('cash_movements', [])
        ],
        'inventory_adjustments': [
            {**a, 'user_name': 'Operador', 'reason': 'Consulta el motivo en el POS local'}
            for a in data.get('inventory_adjustments', [])
        ],
    }
