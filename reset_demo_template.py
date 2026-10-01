import sqlite3
from datetime import datetime, timedelta
import os

DB_FILE = 'finance.db'

def reset_demo_user():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    
    demo_user_id = 1
    # Cleanup old corrupted data for demo user
    cur.execute("DELETE FROM balance_history WHERE user_id = ?", (demo_user_id,))
    cur.execute("DELETE FROM credit_cards WHERE user_id = ?", (demo_user_id,))
    cur.execute("DELETE FROM budgets WHERE user_id = ?", (demo_user_id,))
    cur.execute("DELETE FROM transactions WHERE user_id = ?", (demo_user_id,))
    cur.execute("DELETE FROM accounts WHERE user_id = ?", (demo_user_id,))
    
    # Insert clean data
    cur.executemany(
        "INSERT INTO accounts (user_id, name, type, balance) VALUES (?, ?, ?, ?)",
        [
            (demo_user_id, 'Wallet', 'Cash', 620.00),
            (demo_user_id, 'Bank Account', 'Checking', 12480.00),
            (demo_user_id, 'Savings', 'Savings', 8850.00),
        ],
    )
    
    cur.execute(
        "INSERT INTO credit_cards (user_id, card_name, debt_amount, credit_limit, interest_rate, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (demo_user_id, 'Primary Card', 4720.00, 15000.00, 19.99, datetime.utcnow().isoformat())
    )
    
    cur.executemany(
        "INSERT INTO budgets (user_id, category, limit_amount, spent_amount, created_at) VALUES (?, ?, ?, ?, ?)",
        [
            (demo_user_id, 'Entertainment', 500.00, 320.00, datetime.utcnow().isoformat()),
            (demo_user_id, 'Groceries', 900.00, 640.00, datetime.utcnow().isoformat()),
            (demo_user_id, 'Travel', 1800.00, 1150.00, datetime.utcnow().isoformat()),
            (demo_user_id, 'Utilities', 260.00, 210.00, datetime.utcnow().isoformat()),
        ],
    )
    
    # We need to map accounts for transactions. Since we explicitly created them above, 
    # we can fetch their IDs back by name for accuracy.
    cur.execute("SELECT id, name FROM accounts WHERE user_id = ?", (demo_user_id,))
    acc_map = {row[1]: row[0] for row in cur.fetchall()}

    today = datetime.utcnow().date()
    cur.executemany(
        "INSERT INTO transactions (user_id, account_id, amount, transaction_type, category, description, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (demo_user_id, acc_map['Bank Account'], 4200.00, 'Credit', 'Income', 'Salary Deposit', (today - timedelta(days=4)).isoformat()),
            (demo_user_id, acc_map['Wallet'], 84.50, 'Debit', 'Groceries', 'Grocery Market', (today - timedelta(days=6)).isoformat()),
            (demo_user_id, acc_map['Wallet'], 12.20, 'Debit', 'Entertainment', 'Coffee Shop', (today - timedelta(days=7)).isoformat()),
            (demo_user_id, acc_map['Bank Account'], 1500.00, 'Credit', 'Payments', 'Credit Card Payment', (today - timedelta(days=10)).isoformat()),
            (demo_user_id, acc_map['Wallet'], 45.00, 'Debit', 'Utilities', 'Electric Bill', (today - timedelta(days=12)).isoformat()),
        ],
    )
    
    base_balance = 21950.0
    history_rows = []
    for offset in range(60):
        date = (today - timedelta(days=59 - offset)).isoformat()
        snapshot = base_balance + offset * 80 - (offset % 5) * 30
        history_rows.append((demo_user_id, date, max(snapshot, 0)))
    
    cur.executemany(
        "INSERT OR REPLACE INTO balance_history (user_id, snapshot_date, total_balance) VALUES (?, ?, ?)",
        history_rows
    )
    
    conn.commit()
    conn.close()
    print("Master Demo Account Reseeded!")

if __name__ == "__main__":
    reset_demo_user()
