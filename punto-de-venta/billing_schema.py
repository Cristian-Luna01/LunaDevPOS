"""Persistencia fiscal separada de los cálculos de ventas y de caja."""
TABLES=['fiscal_config','fiscal_products','fiscal_documents','fiscal_sales','fiscal_payments','fiscal_refunds','fiscal_events']
SCHEMA=(
'''CREATE TABLE IF NOT EXISTS fiscal_config(id INTEGER PRIMARY KEY CHECK(id=1),settings_json TEXT NOT NULL,credential_blob TEXT,revision INTEGER NOT NULL DEFAULT 1)''',
'''CREATE TABLE IF NOT EXISTS fiscal_products(product_id INTEGER PRIMARY KEY REFERENCES products(id),product_code TEXT NOT NULL,unit_code TEXT NOT NULL,tax_object TEXT NOT NULL,tax_factor TEXT NOT NULL,tax_bps INTEGER NOT NULL CHECK(tax_bps IN(0,800,1600)),reviewed INTEGER NOT NULL CHECK(reviewed IN(0,1)))''',
'''CREATE TABLE IF NOT EXISTS fiscal_documents(id INTEGER PRIMARY KEY,request_key TEXT UNIQUE NOT NULL,request_hash TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN('I','P','E')),mode TEXT NOT NULL CHECK(mode='sandbox'),state TEXT NOT NULL CHECK(state IN('draft','ready','sending','rejected','unknown','issued','cancel_pending','cancel_sending','cancelled','abandoned')),user_id INTEGER NOT NULL REFERENCES users(id),config_revision INTEGER NOT NULL,issuer_rfc TEXT NOT NULL,receiver_json TEXT NOT NULL,payload_json TEXT NOT NULL,expected_cents INTEGER NOT NULL CHECK(expected_cents>=0),provider_id TEXT,uuid TEXT UNIQUE,xml_base64 TEXT,pdf_base64 TEXT,cancel_ack_base64 TEXT,cancel_request_json TEXT,last_error TEXT NOT NULL DEFAULT '',attempts INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')),updated_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')))''',
'''CREATE TABLE IF NOT EXISTS fiscal_sales(document_id INTEGER NOT NULL REFERENCES fiscal_documents(id),sale_id INTEGER NOT NULL REFERENCES sales(id),active INTEGER NOT NULL DEFAULT 1 CHECK(active IN(0,1)),PRIMARY KEY(document_id,sale_id))''',
'''CREATE UNIQUE INDEX IF NOT EXISTS one_active_income_invoice ON fiscal_sales(sale_id) WHERE active=1''',
'''CREATE TABLE IF NOT EXISTS fiscal_payments(document_id INTEGER NOT NULL REFERENCES fiscal_documents(id),ledger_id INTEGER NOT NULL REFERENCES customer_ledger(id),income_document_id INTEGER NOT NULL REFERENCES fiscal_documents(id),amount_cents INTEGER NOT NULL CHECK(amount_cents>0),previous_cents INTEGER NOT NULL CHECK(previous_cents>=amount_cents),balance_cents INTEGER NOT NULL CHECK(balance_cents=previous_cents-amount_cents),partiality INTEGER NOT NULL CHECK(partiality>0),active INTEGER NOT NULL DEFAULT 1 CHECK(active IN(0,1)),PRIMARY KEY(document_id,ledger_id,income_document_id))''',
'''CREATE UNIQUE INDEX IF NOT EXISTS one_payment_complement_per_allocation ON fiscal_payments(ledger_id,income_document_id) WHERE active=1''',
'''CREATE TABLE IF NOT EXISTS fiscal_refunds(document_id INTEGER PRIMARY KEY REFERENCES fiscal_documents(id),return_id INTEGER NOT NULL REFERENCES returns(id),income_document_id INTEGER NOT NULL REFERENCES fiscal_documents(id),active INTEGER NOT NULL DEFAULT 1 CHECK(active IN(0,1)))''',
'''CREATE UNIQUE INDEX IF NOT EXISTS one_refund_note ON fiscal_refunds(return_id) WHERE active=1''',
'''CREATE TABLE IF NOT EXISTS fiscal_events(id INTEGER PRIMARY KEY,document_id INTEGER NOT NULL REFERENCES fiscal_documents(id),action TEXT NOT NULL,details TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')))''',
'''CREATE INDEX IF NOT EXISTS fiscal_work ON fiscal_documents(state,id)''',
'''CREATE TRIGGER IF NOT EXISTS fiscal_issued_payload_immutable BEFORE UPDATE OF payload_json,expected_cents,receiver_json,issuer_rfc ON fiscal_documents WHEN OLD.uuid IS NOT NULL BEGIN SELECT RAISE(ABORT,'Documento timbrado inmutable'); END''',
'''CREATE TRIGGER IF NOT EXISTS fiscal_event_update_immutable BEFORE UPDATE ON fiscal_events BEGIN SELECT RAISE(ABORT,'Bitacora fiscal inmutable'); END''',
'''CREATE TRIGGER IF NOT EXISTS fiscal_event_delete_immutable BEFORE DELETE ON fiscal_events BEGIN SELECT RAISE(ABORT,'Bitacora fiscal inmutable'); END''',
)
def install(db):
    from entity_management import install as install_entities
    install_entities(db)
    from card_fees import install as install_fees
    install_fees(db)
    for statement in SCHEMA:db.execute(statement)
