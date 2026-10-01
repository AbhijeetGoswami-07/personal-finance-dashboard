import unittest
import json
import os
import tempfile
import server
from datetime import datetime

class TransactionTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        os.close(self.db_fd)
        os.unlink(self.db_path)
        
        # Patch the DB file path
        self.old_db_file = server.DB_FILE
        server.DB_FILE = self.db_path
        
        server.init_db()
        self.client = server.app.test_client()
        
        # Login demo user initially
        self.client.post('/api/login', json={'username': 'demo', 'password': 'demo123'})
        
        # Setup specific accounts data for test predictability
        conn = server.get_db_connection()
        cur = conn.cursor()
        # Set account 1 balance to 100, account 2 balance to 50000, account 3 balance to 100
        cur.execute("UPDATE accounts SET balance = 100 WHERE id = 1 AND user_id = 1")
        cur.execute("UPDATE accounts SET balance = 50000 WHERE id = 2 AND user_id = 1")
        cur.execute("UPDATE accounts SET balance = 100 WHERE id = 3 AND user_id = 1")
        conn.commit()
        conn.close()

    def tearDown(self):
        server.DB_FILE = self.old_db_file
        if os.path.exists(self.db_path):
            try:
                os.unlink(self.db_path)
            except PermissionError:
                pass

    def test_1_valid_debit(self):
        # Balance 100, Debit 50
        res = self.client.post('/api/transaction', json={
            'amount': 50,
            'account_id': 1,
            'transaction_type': 'Debit'
        })
        self.assertEqual(res.status_code, 200)
        conn = server.get_db_connection()
        acc = conn.execute("SELECT balance FROM accounts WHERE id=1").fetchone()
        self.assertEqual(acc['balance'], 50)
        conn.close()

    def test_2_exact_debit(self):
        # Balance 100, Debit 100
        res = self.client.post('/api/transaction', json={
            'amount': 100,
            'account_id': 1,
            'transaction_type': 'Debit'
        })
        self.assertEqual(res.status_code, 200)
        conn = server.get_db_connection()
        acc = conn.execute("SELECT balance FROM accounts WHERE id=1").fetchone()
        self.assertEqual(acc['balance'], 0)
        conn.close()

    def test_3_insufficient_debit(self):
        # Balance 100, Debit 101
        res = self.client.post('/api/transaction', json={
            'amount': 101,
            'account_id': 1,
            'transaction_type': 'Debit'
        })
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertEqual(data['error'], 'INSUFFICIENT_FUNDS')
        
        conn = server.get_db_connection()
        acc = conn.execute("SELECT balance FROM accounts WHERE id=1").fetchone()
        self.assertEqual(acc['balance'], 100) # Balance remains unchanged
        conn.close()

    def test_4_large_insufficient_debit(self):
        res = self.client.post('/api/transaction', json={
            'amount': 2115132,
            'account_id': 1,
            'transaction_type': 'Debit'
        })
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertEqual(data['error'], 'INSUFFICIENT_FUNDS')

    def test_5_zero_debit(self):
        res = self.client.post('/api/transaction', json={
            'amount': 0,
            'account_id': 1,
            'transaction_type': 'Debit'
        })
        self.assertEqual(res.status_code, 400)

    def test_6_negative_debit(self):
        res = self.client.post('/api/transaction', json={
            'amount': -50,
            'account_id': 1,
            'transaction_type': 'Debit'
        })
        self.assertEqual(res.status_code, 400)

    def test_7_invalid_amount(self):
        res = self.client.post('/api/transaction', json={
            'amount': 'abc',
            'account_id': 1,
            'transaction_type': 'Debit'
        })
        self.assertEqual(res.status_code, 400)

    def test_8_suggested_accounts(self):
        # Selected account 1 has 100. Account 2 has 50000. Debit 10000.
        res = self.client.post('/api/transaction', json={
            'amount': 10000,
            'account_id': 1,
            'transaction_type': 'Debit'
        })
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertTrue('suggestedAccounts' in data)
        self.assertTrue(len(data['suggestedAccounts']) == 1)
        self.assertEqual(data['suggestedAccounts'][0]['id'], 2)

    def test_9_no_suitable_accounts(self):
        # Selected account 1 has 100, others 50000 and 100. Debit 60000.
        res = self.client.post('/api/transaction', json={
            'amount': 60000,
            'account_id': 1,
            'transaction_type': 'Debit'
        })
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertTrue(len(data['suggestedAccounts']) == 0)

    def test_10_auth_failure(self):
        # Create a new client without login to simulate auth failure
        new_client = server.app.test_client()
        res = new_client.post('/api/transaction', json={
            'amount': 10,
            'account_id': 1,
            'transaction_type': 'Debit'
        })
        self.assertEqual(res.status_code, 401)

    def test_11_concurrent_transactions(self):
        import concurrent.futures
        
        # Send two 60 requests simultaneously to account 1 which has 100
        # Only one should succeed
        def send_req():
            # Must create separate test_client instances attached to same thread or just issue fetch sequentially?
            # Actually, thread-local context with test_client implies we need session setup.
            # Best way is to use requests if server is running, or simulate concurrent threads creating test_clients.
            c = server.app.test_client()
            c.post('/api/login', json={'username': 'demo', 'password': 'demo123'})
            return c.post('/api/transaction', json={
                'amount': 60,
                'account_id': 1,
                'transaction_type': 'Debit'
            })
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(send_req), executor.submit(send_req)]
            results = [f.result() for f in futures]
            
        status_codes = [r.status_code for r in results]
        self.assertTrue(400 in status_codes, "At least one request should have failed due to insufficient funds.")
        self.assertTrue(200 in status_codes, "One request should have succeeded.")
        
        conn = server.get_db_connection()
        acc = conn.execute("SELECT balance FROM accounts WHERE id=1").fetchone()
        self.assertEqual(acc['balance'], 40)
        conn.close()

    def test_12_subsequent_transactions(self):
        res1 = self.client.post('/api/transaction', json={
            'amount': 60,
            'account_id': 1,
            'transaction_type': 'Debit'
        })
        self.assertEqual(res1.status_code, 200)
        
        res2 = self.client.post('/api/transaction', json={
            'amount': 50,
            'account_id': 1,
            'transaction_type': 'Debit'
        })
        self.assertEqual(res2.status_code, 400)
        data = json.loads(res2.data)
        self.assertEqual(data['error'], 'INSUFFICIENT_FUNDS')

if __name__ == '__main__':
    unittest.main()
