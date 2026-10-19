"""Índices auxiliares: no cambian datos ni la versión del formato de respaldo."""
import contextlib
import sqlite3

STATEMENTS = 'CREATE INDEX IF NOT EXISTS batches_product_received ON batches(product_id,received_at DESC,id DESC);\nCREATE INDEX IF NOT EXISTS returns_sale ON returns(sale_id);\nCREATE INDEX IF NOT EXISTS return_items_sale_item ON return_items(sale_item_id);\nCREATE INDEX IF NOT EXISTS return_allocations_item ON return_allocations(return_item_id);\n'

def install(path):
    with contextlib.closing(sqlite3.connect(path, timeout=10)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='return_allocations'").fetchone():
            return
        with db:
            for statement in STATEMENTS.split(';'):
                if statement.strip():
                    db.execute(statement)
