"""Migraciones locales: conserva IDs y relaciones al permitir fecha desconocida."""
import contextlib
import sqlite3
import secrets
from credit import TABLE as CREDIT_TABLE
from branding import TABLE as BRANDING_TABLE, SETTINGS_TABLE
from promotions import TABLE as PROMOTIONS_TABLE, EXTRA_COLUMNS

IMPORT_TABLE = '''CREATE TABLE IF NOT EXISTS inventory_imports(
 id INTEGER PRIMARY KEY,request_key TEXT NOT NULL UNIQUE,request_hash TEXT NOT NULL,
 user_id INTEGER NOT NULL REFERENCES users(id),result_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')))'''

def upgrade(path, permissions):
    with contextlib.closing(sqlite3.connect(path, timeout=10, isolation_level=None)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='products'").fetchone():
            return
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version > 10:
            raise RuntimeError('Esta base requiere una versión más reciente de Botica')
        if version == 10:
            return
        if version==9:
            from entity_management import install
            backup_path=str(path)+'.antes-v10-'+secrets.token_hex(4)+'.sqlite3'
            with contextlib.closing(sqlite3.connect(backup_path)) as copy:
                db.backup(copy)
                if copy.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('No se pudo verificar la copia previa')
            db.execute('BEGIN IMMEDIATE')
            try:install(db);db.execute('PRAGMA user_version=10');db.commit()
            except Exception:db.rollback();raise
            return
        if version==8:
            from card_fees import install
            backup_path=str(path)+'.antes-v9-'+secrets.token_hex(4)+'.sqlite3'
            with contextlib.closing(sqlite3.connect(backup_path)) as safety_copy:db.backup(safety_copy)
            db.execute('BEGIN IMMEDIATE')
            try:
                install(db)
                from entity_management import install as install_entities
                install_entities(db)
                db.execute('PRAGMA user_version=10');db.commit()
            except Exception:db.rollback();raise
            return
        if version==7:
            from billing_schema import install
            backup_path=str(path)+'.antes-v8-'+secrets.token_hex(4)+'.sqlite3'
            with contextlib.closing(sqlite3.connect(backup_path)) as safety_copy:
                db.backup(safety_copy)
                if safety_copy.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('No se pudo verificar el respaldo previo a la migración')
            db.execute('BEGIN IMMEDIATE')
            try:
                if db.execute('PRAGMA foreign_key_check').fetchone():raise RuntimeError('La migración detectó relaciones inconsistentes')
                install(db)
                for code in ('billing.issue','billing.manage'):
                    db.execute('INSERT OR IGNORE INTO permissions VALUES (?,?)',(code,permissions[code]))
                    db.execute("INSERT OR IGNORE INTO role_permissions SELECT id,? FROM roles WHERE name='Administrador'",(code,))
                db.execute('PRAGMA user_version=10');db.commit()
            except Exception:db.rollback();raise
            return
        # Copia consistente antes de modificar una base creada por la versión anterior.
        backup_path=str(path)+('.antes-v2-' if version<2 else '.antes-v7-')+secrets.token_hex(4)+'.sqlite3'
        with contextlib.closing(sqlite3.connect(backup_path)) as safety_copy:
            db.backup(safety_copy)
            if safety_copy.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise RuntimeError('No se pudo verificar la copia previa a la actualización')
        db.execute('PRAGMA foreign_keys=OFF')
        db.execute('BEGIN IMMEDIATE')
        try:
            column = next(c for c in db.execute('PRAGMA table_info(batches)') if c[1]=='expires_on')
            if column[3]:
                db.execute('''CREATE TABLE batches_new(
                 id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),supplier_id INTEGER REFERENCES suppliers(id),
                 lot_number TEXT NOT NULL,expires_on TEXT CHECK(expires_on IS NULL OR (length(expires_on)=10 AND date(expires_on) IS NOT NULL AND date(expires_on)=expires_on)),
                 received_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                 quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity>=0),unit_cost_cents INTEGER NOT NULL CHECK(unit_cost_cents>=0))''')
                db.execute('INSERT INTO batches_new SELECT * FROM batches')
                db.execute('DROP TABLE batches')
                db.execute('ALTER TABLE batches_new RENAME TO batches')
                db.execute('CREATE INDEX batches_fefo ON batches(product_id,expires_on,received_at,id) WHERE quantity>0')
            db.execute(CREDIT_TABLE)
            db.execute(IMPORT_TABLE)
            db.execute(BRANDING_TABLE)
            db.execute(SETTINGS_TABLE)
            db.execute(PROMOTIONS_TABLE)
            columns={c[1] for c in db.execute('PRAGMA table_info(promotions)')}
            for name,definition in EXTRA_COLUMNS.items():
                if name not in columns:db.execute('ALTER TABLE promotions ADD COLUMN '+name+' '+definition)
            for code in ('inventory.import','inventory.export','backup.manage'):
                db.execute('INSERT OR IGNORE INTO permissions VALUES (?,?)',(code,permissions[code]))
                db.execute("INSERT OR IGNORE INTO role_permissions SELECT id,? FROM roles WHERE name='Administrador'",(code,))
            if db.execute('PRAGMA foreign_key_check').fetchone():
                raise RuntimeError('La migración detectó relaciones inconsistentes')
            from billing_schema import install
            install(db)
            for code in ('billing.issue','billing.manage'):
                db.execute('INSERT OR IGNORE INTO permissions VALUES (?,?)',(code,permissions[code]))
                db.execute("INSERT OR IGNORE INTO role_permissions SELECT id,? FROM roles WHERE name='Administrador'",(code,))
            db.execute('PRAGMA user_version=10')
            db.commit()
        except Exception:
            db.rollback()
            raise
