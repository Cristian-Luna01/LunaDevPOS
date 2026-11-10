"""Aviso configurable del comercio. No se replica a la cuenta central."""
from core import Error

FIELDS = {'responsible': 160, 'address': 400, 'purposes': 1000,
          'contact': 250, 'full_notice': 12000}


def read(pos):
    with pos.db() as db:
        row = db.execute('SELECT responsible,address,purposes,contact,full_notice FROM privacy_notice WHERE id=1').fetchone()
    return dict(row) if row else {key: '' for key in FIELDS}


def save(pos, uid, data):
    with pos.db(True) as db:
        pos.require(db, uid, 'users.manage')
        values = []
        for key, limit in FIELDS.items():
            value = data.get(key)
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= limit:
                raise Error('Completa todos los campos del aviso y respeta sus límites de texto.')
            values.append(value.strip())
        db.execute('''INSERT INTO privacy_notice VALUES (1,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET responsible=excluded.responsible,address=excluded.address,
            purposes=excluded.purposes,contact=excluded.contact,full_notice=excluded.full_notice''', values)
        pos.audit(db, uid, 'privacy.notice.save', 1, {})
    return {'ok': True}
