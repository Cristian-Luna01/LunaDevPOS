import datetime as dt
import unittest
from branch_sync import retained_history

class CloudRetentionTest(unittest.TestCase):
    def test_old_reports_send_only_summary_without_mutating_local_history(self):
        r={'from':'2026-09-12','to':'2026-09-12','totals':{'net_cents':1000},'products':[{'id':1,'net_cents':1000}],
           'events':[{'ticket_id':1}], 'cash_movements':[{'direction':'in','amount_cents':500},{'direction':'out','amount_cents':200}], 'card_fees':[{'fee_cents':40}]}
        compact=retained_history(r,r['from'],dt.date(2026,10,12))
        self.assertEqual(compact['events'],[]);self.assertEqual(compact['cash_totals'],{'in':500,'out':200})
        self.assertEqual(compact['totals'],r['totals']);self.assertEqual(compact['products'],r['products'])
        self.assertEqual(len(r['events']),1);self.assertEqual(len(r['cash_movements']),2)
        self.assertIs(retained_history(r,'2026-09-13',dt.date(2026,10,12)),r)
