"""Índices aditivos y búsqueda de subcadenas; no cambia datos comerciales."""
import datetime as dt
import sqlite3

def utc_bounds(start,end):
    def midnight(day):
        return dt.datetime.combine(day,dt.time()).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
    return midnight(dt.date.fromisoformat(str(start))),midnight(dt.date.fromisoformat(str(end))+dt.timedelta(days=1))

def install(db):
    for table in ('sales','returns','cash_movements','customer_ledger','card_fees','audit_log'):
        if db.execute("SELECT 1 FROM sqlite_master WHERE name=?",(table,)).fetchone():
            db.execute(f'CREATE INDEX IF NOT EXISTS {table}_created ON {table}(created_at,id)')
    db.execute('CREATE INDEX IF NOT EXISTS ledger_customer_order ON customer_ledger(customer_id,id)')
    db.execute('CREATE INDEX IF NOT EXISTS audit_request_lookup ON audit_log(action,json_extract(details,\'$.request_key\'))')
    existed=db.execute("SELECT 1 FROM sqlite_master WHERE name='products_search'").fetchone()
    try:
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS products_search USING fts5(name,generic_name,content='products',content_rowid='id',tokenize='trigram')")
    except sqlite3.OperationalError:return
    db.executescript('''CREATE TRIGGER IF NOT EXISTS products_search_insert AFTER INSERT ON products BEGIN
      INSERT INTO products_search(rowid,name,generic_name) VALUES(new.id,new.name,new.generic_name); END;
    CREATE TRIGGER IF NOT EXISTS products_search_delete AFTER DELETE ON products BEGIN
      INSERT INTO products_search(products_search,rowid,name,generic_name) VALUES('delete',old.id,old.name,old.generic_name); END;
    CREATE TRIGGER IF NOT EXISTS products_search_update AFTER UPDATE OF name,generic_name ON products BEGIN
      INSERT INTO products_search(products_search,rowid,name,generic_name) VALUES('delete',old.id,old.name,old.generic_name);
      INSERT INTO products_search(rowid,name,generic_name) VALUES(new.id,new.name,new.generic_name); END;''')
    if not existed:rebuild(db)

def rebuild(db):
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='products_search'").fetchone():
        db.execute("INSERT INTO products_search(products_search) VALUES('rebuild')")

def product_search(db,query):
    if query and db.execute('SELECT 1 FROM products WHERE barcode=? AND active=1',(query,)).fetchone():
        return 'p.barcode=?',(query,)
    if len(query)>=3 and not any(c in query for c in ('%','_')) and db.execute("SELECT 1 FROM sqlite_master WHERE name='products_search'").fetchone():
        return 'p.id IN (SELECT rowid FROM products_search WHERE products_search MATCH ?)',('"'+query.replace('"','""')+'"',)
    return '(p.barcode=? OR p.name LIKE ? OR p.generic_name LIKE ?)',(query,'%'+query+'%','%'+query+'%')
