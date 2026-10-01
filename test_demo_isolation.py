import requests

BASE_URL = 'http://127.0.0.1:5001'

def run_tests():
    print("--- Starting Demo Data Isolation Tests ---")
    
    # Session A
    sA = requests.Session()
    resA = sA.post(f'{BASE_URL}/api/login', json={'username': 'demo', 'password': 'demo123'})
    
    if not resA.ok:
        print("Failed to login Session A!")
        return

    dataA = sA.get(f'{BASE_URL}/api/overview').json()
    initial_balance = dataA['total_balance']
    print(f"Session A: Initial Balance {initial_balance}")
    
    account_id = dataA['accounts'][0]['id']
    
    print("Session A: Adding 100.00 Expense under 'DemoTestCategoryA'")
    sA.post(f'{BASE_URL}/api/transaction', json={
        'amount': 100, 'account_id': account_id, 
        'transaction_type': 'Debit', 'category': 'DemoTestCategoryA', 'description': 'Test'
    })
    
    dataA_new = sA.get(f'{BASE_URL}/api/overview').json()
    cats_A = [tx['category'] for tx in dataA_new['recent_transactions']]
    print(f"Session A: Post-Transaction Balance {dataA_new['total_balance']}")
    assert 'DemoTestCategoryA' in cats_A, "Session A failed to record its own transaction."

    # Session B (Simulating TEST C concurrent usage)
    print("\n--- Starting Session B Concurrent ---")
    sB = requests.Session()
    sB.post(f'{BASE_URL}/api/login', json={'username': 'demo', 'password': 'demo123'})
    
    dataB = sB.get(f'{BASE_URL}/api/overview').json()
    print(f"Session B: Initial Balance {dataB['total_balance']}")
    assert dataB['total_balance'] == initial_balance, "Session B did not start with clean initial balance! Data bled from Session A."
    
    cats_B = [tx['category'] for tx in dataB['recent_transactions']]
    assert 'DemoTestCategoryA' not in cats_B, "Session B saw Session A's transaction!"
    
    print("Session B: Adding 500.00 Credit under 'DemoTestCategoryB'")
    sB.post(f'{BASE_URL}/api/transaction', json={
        'amount': 500, 'account_id': account_id, 
        'transaction_type': 'Credit', 'category': 'DemoTestCategoryB', 'description': 'Test'
    })

    # Assert Session A still can't see B
    dataA_final = sA.get(f'{BASE_URL}/api/overview').json()
    cats_A_final = [tx['category'] for tx in dataA_final['recent_transactions']]
    assert 'DemoTestCategoryB' not in cats_A_final, "Session A saw Session B's transaction!"

    # Simulate fully closing Session A (Logout triggering purge)
    print("\n--- Logging out Session A (Simulating closure) ---")
    sA.post(f'{BASE_URL}/api/logout')

    print("\n--- All Isolation Tests Passed! ---")

if __name__ == '__main__':
    run_tests()
