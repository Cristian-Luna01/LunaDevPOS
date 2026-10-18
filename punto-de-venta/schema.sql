PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS permissions(code TEXT PRIMARY KEY, label TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
 display_name TEXT NOT NULL, password_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1 CHECK(active IN(0,1)),
 created_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE TABLE IF NOT EXISTS roles(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS user_roles(user_id INTEGER REFERENCES users(id),role_id INTEGER REFERENCES roles(id),PRIMARY KEY(user_id,role_id));
CREATE TABLE IF NOT EXISTS role_permissions(role_id INTEGER REFERENCES roles(id),permission_code TEXT REFERENCES permissions(code),PRIMARY KEY(role_id,permission_code));
CREATE TABLE IF NOT EXISTS user_permissions(user_id INTEGER REFERENCES users(id),permission_code TEXT REFERENCES permissions(code),allowed INTEGER NOT NULL CHECK(allowed IN(0,1)),PRIMARY KEY(user_id,permission_code));
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),expires_at INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS login_attempts(username TEXT PRIMARY KEY,failures INTEGER NOT NULL,blocked_until INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY,business_name TEXT NOT NULL,contact TEXT NOT NULL DEFAULT '',phone TEXT NOT NULL DEFAULT '',credit_days INTEGER NOT NULL DEFAULT 0 CHECK(credit_days>=0),active INTEGER NOT NULL DEFAULT 1 CHECK(active IN(0,1)));
CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY,name TEXT NOT NULL,phone TEXT NOT NULL DEFAULT '',discount_bps INTEGER NOT NULL DEFAULT 0 CHECK(discount_bps BETWEEN 0 AND 10000),active INTEGER NOT NULL DEFAULT 1 CHECK(active IN(0,1)));
CREATE INDEX IF NOT EXISTS customers_phone ON customers(phone);
CREATE INDEX IF NOT EXISTS customers_name ON customers(name COLLATE NOCASE);
-- Los precios incluyen impuestos; importes en centavos, tasas en puntos base.
CREATE TABLE IF NOT EXISTS products(
 id INTEGER PRIMARY KEY,barcode TEXT NOT NULL UNIQUE,name TEXT NOT NULL,generic_name TEXT NOT NULL DEFAULT '',
 category_id INTEGER NOT NULL REFERENCES categories(id),cost_cents INTEGER NOT NULL CHECK(cost_cents>=0),
 price_cents INTEGER NOT NULL CHECK(price_cents>=0),tax_bps INTEGER NOT NULL DEFAULT 0 CHECK(tax_bps BETWEEN 0 AND 10000),
 min_stock INTEGER NOT NULL DEFAULT 0 CHECK(min_stock>=0),max_stock INTEGER NOT NULL DEFAULT 100 CHECK(max_stock>=min_stock),
 reorder_point INTEGER NOT NULL DEFAULT 5 CHECK(reorder_point>=0),requires_prescription INTEGER NOT NULL DEFAULT 0 CHECK(requires_prescription IN(0,1)),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN(0,1)));
CREATE INDEX IF NOT EXISTS products_name ON products(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS products_generic ON products(generic_name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS products_category ON products(category_id);
CREATE TABLE IF NOT EXISTS batches(
 id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),supplier_id INTEGER REFERENCES suppliers(id),
 lot_number TEXT NOT NULL,expires_on TEXT CHECK(expires_on IS NULL OR (length(expires_on)=10 AND date(expires_on) IS NOT NULL AND date(expires_on)=expires_on)),
 received_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity>=0),unit_cost_cents INTEGER NOT NULL CHECK(unit_cost_cents>=0));
CREATE INDEX IF NOT EXISTS batches_fefo ON batches(product_id,expires_on,received_at,id) WHERE quantity>0;
CREATE TABLE IF NOT EXISTS cash_shifts(
 id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),register_id TEXT NOT NULL,
 opened_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')),closed_at TEXT,
 opening_cents INTEGER NOT NULL CHECK(opening_cents>=0),counted_cents INTEGER CHECK(counted_cents>=0),
 expected_cents INTEGER,report_json TEXT,
 CHECK((closed_at IS NULL AND counted_cents IS NULL AND expected_cents IS NULL AND report_json IS NULL) OR
 (closed_at IS NOT NULL AND counted_cents IS NOT NULL AND expected_cents IS NOT NULL AND report_json IS NOT NULL)));
CREATE UNIQUE INDEX IF NOT EXISTS one_shift_per_register ON cash_shifts(register_id) WHERE closed_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS one_shift_per_user ON cash_shifts(user_id) WHERE closed_at IS NULL;
CREATE TABLE IF NOT EXISTS cash_movements(
 id INTEGER PRIMARY KEY,shift_id INTEGER NOT NULL REFERENCES cash_shifts(id),user_id INTEGER NOT NULL REFERENCES users(id),
 direction TEXT NOT NULL CHECK(direction IN('in','out')),category TEXT NOT NULL CHECK(category IN('change','supplier','expense','safekeeping')),
 amount_cents INTEGER NOT NULL CHECK(amount_cents>0),supplier_id INTEGER REFERENCES suppliers(id),invoice_ref TEXT,
 concept TEXT NOT NULL CHECK(length(trim(concept))>0),created_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 CHECK((direction='in' AND category='change') OR (direction='out' AND category IN('supplier','expense','safekeeping'))),
 CHECK(category!='supplier' OR (supplier_id IS NOT NULL AND length(trim(invoice_ref))>0 AND invoice_ref IS NOT NULL)));
CREATE INDEX IF NOT EXISTS cash_movements_shift ON cash_movements(shift_id);
CREATE TABLE IF NOT EXISTS sales(
 id INTEGER PRIMARY KEY,request_key TEXT NOT NULL UNIQUE,request_hash TEXT NOT NULL,shift_id INTEGER NOT NULL REFERENCES cash_shifts(id),
 user_id INTEGER NOT NULL REFERENCES users(id),customer_id INTEGER REFERENCES customers(id),
 total_cents INTEGER NOT NULL CHECK(total_cents>=0),tax_cents INTEGER NOT NULL CHECK(tax_cents>=0),discount_cents INTEGER NOT NULL CHECK(discount_cents>=0),
 status TEXT NOT NULL DEFAULT 'completed' CHECK(status IN('completed','partial_return','returned','voided')),
 created_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE INDEX IF NOT EXISTS sales_shift ON sales(shift_id);
CREATE INDEX IF NOT EXISTS sales_customer ON sales(customer_id,created_at);
CREATE TABLE IF NOT EXISTS sale_items(
 id INTEGER PRIMARY KEY,sale_id INTEGER NOT NULL REFERENCES sales(id),product_id INTEGER NOT NULL REFERENCES products(id),
 category_id INTEGER NOT NULL REFERENCES categories(id),product_name TEXT NOT NULL,quantity INTEGER NOT NULL CHECK(quantity>0),
 unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents>=0),tax_bps INTEGER NOT NULL CHECK(tax_bps BETWEEN 0 AND 10000),
 discount_cents INTEGER NOT NULL CHECK(discount_cents>=0),total_cents INTEGER NOT NULL CHECK(total_cents>=0),tax_cents INTEGER NOT NULL CHECK(tax_cents>=0));
CREATE INDEX IF NOT EXISTS sale_items_sale ON sale_items(sale_id);
CREATE TABLE IF NOT EXISTS sale_item_batches(
 id INTEGER PRIMARY KEY,sale_item_id INTEGER NOT NULL REFERENCES sale_items(id),batch_id INTEGER NOT NULL REFERENCES batches(id),
 quantity INTEGER NOT NULL CHECK(quantity>0),unit_cost_cents INTEGER NOT NULL CHECK(unit_cost_cents>=0),UNIQUE(sale_item_id,batch_id));
CREATE TABLE IF NOT EXISTS sale_payments(
 id INTEGER PRIMARY KEY,sale_id INTEGER NOT NULL REFERENCES sales(id),method TEXT NOT NULL CHECK(method IN('cash','debit','credit','transfer')),
 amount_cents INTEGER NOT NULL CHECK(amount_cents>0),tendered_cents INTEGER NOT NULL,reference TEXT NOT NULL DEFAULT '',
 CHECK(tendered_cents>=amount_cents),CHECK(method='cash' OR tendered_cents=amount_cents),UNIQUE(sale_id,method));
CREATE TABLE IF NOT EXISTS prescriptions(
 id INTEGER PRIMARY KEY,sale_item_id INTEGER NOT NULL UNIQUE REFERENCES sale_items(id),doctor_name TEXT NOT NULL,
 license_number TEXT NOT NULL,prescription_ref TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS returns(
 id INTEGER PRIMARY KEY,sale_id INTEGER NOT NULL REFERENCES sales(id),shift_id INTEGER NOT NULL REFERENCES cash_shifts(id),
 user_id INTEGER NOT NULL REFERENCES users(id),request_key TEXT NOT NULL UNIQUE,request_hash TEXT NOT NULL,
 reason TEXT NOT NULL CHECK(length(trim(reason))>0),kind TEXT NOT NULL CHECK(kind IN('return','void')),
 total_cents INTEGER NOT NULL CHECK(total_cents>=0),created_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE INDEX IF NOT EXISTS returns_shift ON returns(shift_id);
CREATE TABLE IF NOT EXISTS return_items(
 id INTEGER PRIMARY KEY,return_id INTEGER NOT NULL REFERENCES returns(id),sale_item_id INTEGER NOT NULL REFERENCES sale_items(id),
 quantity INTEGER NOT NULL CHECK(quantity>0),total_cents INTEGER NOT NULL CHECK(total_cents>=0),tax_cents INTEGER NOT NULL CHECK(tax_cents>=0),
 disposition TEXT NOT NULL CHECK(disposition IN('restock','quarantine')),UNIQUE(return_id,sale_item_id));
CREATE TABLE IF NOT EXISTS return_allocations(
 id INTEGER PRIMARY KEY,return_item_id INTEGER NOT NULL REFERENCES return_items(id),sale_item_batch_id INTEGER NOT NULL REFERENCES sale_item_batches(id),
 quantity INTEGER NOT NULL CHECK(quantity>0));
CREATE TABLE IF NOT EXISTS return_payments(
 id INTEGER PRIMARY KEY,return_id INTEGER NOT NULL REFERENCES returns(id),method TEXT NOT NULL CHECK(method IN('cash','debit','credit','transfer')),
 amount_cents INTEGER NOT NULL CHECK(amount_cents>0),UNIQUE(return_id,method));
CREATE TABLE IF NOT EXISTS inventory_movements(
 id INTEGER PRIMARY KEY,batch_id INTEGER NOT NULL REFERENCES batches(id),user_id INTEGER NOT NULL REFERENCES users(id),
 quantity_delta INTEGER NOT NULL CHECK(quantity_delta!=0),kind TEXT NOT NULL CHECK(kind IN('receipt','sale','return','adjustment')),
 reason TEXT NOT NULL CHECK(length(trim(reason))>0),sale_item_id INTEGER REFERENCES sale_items(id),return_item_id INTEGER REFERENCES return_items(id),
 created_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE INDEX IF NOT EXISTS inventory_kardex ON inventory_movements(batch_id,id);
CREATE TABLE IF NOT EXISTS quarantine(
 id INTEGER PRIMARY KEY,batch_id INTEGER NOT NULL REFERENCES batches(id),return_item_id INTEGER NOT NULL REFERENCES return_items(id),
 quantity INTEGER NOT NULL CHECK(quantity>0),reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_log(
 id INTEGER PRIMARY KEY,user_id INTEGER REFERENCES users(id),action TEXT NOT NULL,entity_id INTEGER,details TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE TRIGGER IF NOT EXISTS immutable_inventory_update BEFORE UPDATE ON inventory_movements BEGIN SELECT RAISE(ABORT,'Kardex inmutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_inventory_delete BEFORE DELETE ON inventory_movements BEGIN SELECT RAISE(ABORT,'Kardex inmutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_audit_update BEFORE UPDATE ON audit_log BEGIN SELECT RAISE(ABORT,'Auditoria inmutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_audit_delete BEFORE DELETE ON audit_log BEGIN SELECT RAISE(ABORT,'Auditoria inmutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_closed_shift BEFORE UPDATE ON cash_shifts WHEN OLD.closed_at IS NOT NULL BEGIN SELECT RAISE(ABORT,'Corte cerrado inmutable'); END;
CREATE TABLE IF NOT EXISTS inventory_imports(
 id INTEGER PRIMARY KEY,request_key TEXT NOT NULL UNIQUE,request_hash TEXT NOT NULL,
 user_id INTEGER NOT NULL REFERENCES users(id),result_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE TABLE IF NOT EXISTS promotions(
 id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL UNIQUE REFERENCES products(id),name TEXT NOT NULL,
 price_cents INTEGER NOT NULL CHECK(price_cents>=0),starts_on TEXT NOT NULL,ends_on TEXT NOT NULL,
 schedule_type TEXT NOT NULL DEFAULT 'temporary' CHECK(schedule_type IN ('temporary','permanent','recurring')),
 weekday_mask INTEGER NOT NULL DEFAULT 127 CHECK(weekday_mask BETWEEN 1 AND 127),
 bundle_quantity INTEGER NOT NULL DEFAULT 1 CHECK(bundle_quantity BETWEEN 1 AND 10000),
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN(0,1)),CHECK(length(starts_on)=10 AND length(ends_on)=10 AND starts_on<=ends_on));
CREATE TABLE IF NOT EXISTS business_branding(id INTEGER PRIMARY KEY CHECK(id=1),png_base64 TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS business_settings(id INTEGER PRIMARY KEY CHECK(id=1),name TEXT NOT NULL,receipt_footer TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customer_ledger(id INTEGER PRIMARY KEY,customer_id INTEGER NOT NULL REFERENCES customers(id),sale_id INTEGER UNIQUE REFERENCES sales(id),shift_id INTEGER NOT NULL REFERENCES cash_shifts(id),user_id INTEGER NOT NULL REFERENCES users(id),amount_cents INTEGER NOT NULL CHECK(amount_cents!=0),method TEXT CHECK(method IN ('cash','debit','transfer')),request_key TEXT UNIQUE,request_hash TEXT,created_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')));
PRAGMA user_version=10;
