import os
import sqlite3
import uuid
import threading
from datetime import datetime, timedelta
import math
from flask import Flask, jsonify, request, render_template, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

DB_FILE = 'finance.db'
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
CORS(app)

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with all required tables."""
    exists = os.path.exists(DB_FILE)
    conn = get_db_connection()
    cur = conn.cursor()

    # Users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Accounts table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, name)
        )
    """)

    # Transactions table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            transaction_type TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    # Budgets table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            limit_amount REAL NOT NULL,
            spent_amount REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, category)
        )
    """)

    # Balance history table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS balance_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            snapshot_date TEXT NOT NULL,
            total_balance REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, snapshot_date)
        )
    """)

    # Credit card table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS credit_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            card_name TEXT NOT NULL,
            debt_amount REAL NOT NULL DEFAULT 0,
            credit_limit REAL NOT NULL,
            interest_rate REAL NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, card_name)
        )
    """)

    conn.commit()

    # Initialize with sample data if fresh database
    if not exists:
        # Create default demo user
        demo_user_id = 1
        cur.execute(
            "INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)",
            ('demo', generate_password_hash('demo123'), datetime.utcnow().isoformat())
        )
        conn.commit()

        # Sample accounts for demo user
        cur.executemany(
            "INSERT INTO accounts (user_id, name, type, balance) VALUES (?, ?, ?, ?)",
            [
                (demo_user_id, 'Wallet', 'Cash', 620.00),
                (demo_user_id, 'Bank Account', 'Checking', 12480.00),
                (demo_user_id, 'Savings', 'Savings', 8850.00),
            ],
        )

        # Sample credit card for demo user
        cur.execute(
            "INSERT INTO credit_cards (user_id, card_name, debt_amount, credit_limit, interest_rate, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (demo_user_id, 'Primary Card', 4720.00, 15000.00, 19.99, datetime.utcnow().isoformat())
        )

        # Sample budgets for demo user
        cur.executemany(
            "INSERT INTO budgets (user_id, category, limit_amount, spent_amount, created_at) VALUES (?, ?, ?, ?, ?)",
            [
                (demo_user_id, 'Entertainment', 500.00, 320.00, datetime.utcnow().isoformat()),
                (demo_user_id, 'Groceries', 900.00, 640.00, datetime.utcnow().isoformat()),
                (demo_user_id, 'Travel', 1800.00, 1150.00, datetime.utcnow().isoformat()),
                (demo_user_id, 'Utilities', 260.00, 210.00, datetime.utcnow().isoformat()),
            ],
        )

        # Sample transactions for demo user
        today = datetime.utcnow().date()
        cur.executemany(
            "INSERT INTO transactions (user_id, account_id, amount, transaction_type, category, description, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (demo_user_id, 2, 4200.00, 'Credit', 'Income', 'Salary Deposit', (today - timedelta(days=4)).isoformat()),
                (demo_user_id, 1, 84.50, 'Debit', 'Groceries', 'Grocery Market', (today - timedelta(days=6)).isoformat()),
                (demo_user_id, 1, 12.20, 'Debit', 'Entertainment', 'Coffee Shop', (today - timedelta(days=7)).isoformat()),
                (demo_user_id, 2, 1500.00, 'Credit', 'Payments', 'Credit Card Payment', (today - timedelta(days=10)).isoformat()),
                (demo_user_id, 1, 45.00, 'Debit', 'Utilities', 'Electric Bill', (today - timedelta(days=12)).isoformat()),
            ],
        )

        # Balance history for demo user
        base_balance = 21950.0
        history_rows = []
        for offset in range(60):
            date = today - timedelta(days=59 - offset)
            snapshot = base_balance + offset * 80 - (offset % 5) * 30
            history_rows.append((demo_user_id, date.isoformat(), max(snapshot, 0)))
        
        for row in history_rows:
            try:
                cur.execute(
                    "INSERT INTO balance_history (user_id, snapshot_date, total_balance) VALUES (?, ?, ?)",
                    row
                )
            except sqlite3.IntegrityError:
                pass

        conn.commit()

    conn.close()

# Helper functions
def cleanup_user(conn, user_id):
    """Deletes all data for a specific user ID."""
    conn.execute("DELETE FROM balance_history WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM credit_cards WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM budgets WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM transactions WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM accounts WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

def cleanup_old_demo_sessions():
    """Background task to remove demo sessions older than 4 hours to prevent DB bloat."""
    def _cleanup():
        conn = get_db_connection()
        cutoff = (datetime.utcnow() - timedelta(hours=4)).isoformat()
        old_users = conn.execute("SELECT id FROM users WHERE username LIKE 'demo_session_%' AND created_at < ?", (cutoff,)).fetchall()
        for u in old_users:
            cleanup_user(conn, u['id'])
        conn.commit()
        conn.close()
    
    threading.Thread(target=_cleanup).start()

def clone_demo_data(conn, source_id, dest_id):
    """Clones all financial data from the master demo user to a target user session."""
    accounts = conn.execute("SELECT * FROM accounts WHERE user_id = ?", (source_id,)).fetchall()
    account_mapping = {}
    for account in accounts:
        cur = conn.execute("INSERT INTO accounts (user_id, name, type, balance) VALUES (?, ?, ?, ?)", 
                           (dest_id, account['name'], account['type'], account['balance']))
        account_mapping[account['id']] = cur.lastrowid

    transactions = conn.execute("SELECT * FROM transactions WHERE user_id = ?", (source_id,)).fetchall()
    for txn in transactions:
        new_account_id = account_mapping.get(txn['account_id'])
        if new_account_id:
            conn.execute("INSERT INTO transactions (user_id, account_id, amount, transaction_type, category, description, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (dest_id, new_account_id, txn['amount'], txn['transaction_type'], txn['category'], txn['description'], txn['created_at']))

    budgets = conn.execute("SELECT * FROM budgets WHERE user_id = ?", (source_id,)).fetchall()
    for b in budgets:
        conn.execute("INSERT INTO budgets (user_id, category, limit_amount, spent_amount, created_at) VALUES (?, ?, ?, ?, ?)",
                     (dest_id, b['category'], b['limit_amount'], b['spent_amount'], b['created_at']))

    cards = conn.execute("SELECT * FROM credit_cards WHERE user_id = ?", (source_id,)).fetchall()
    for c in cards:
        conn.execute("INSERT INTO credit_cards (user_id, card_name, debt_amount, credit_limit, interest_rate, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (dest_id, c['card_name'], c['debt_amount'], c['credit_limit'], c['interest_rate'], c['updated_at']))

    history = conn.execute("SELECT * FROM balance_history WHERE user_id = ?", (source_id,)).fetchall()
    for h in history:
        conn.execute("INSERT INTO balance_history (user_id, snapshot_date, total_balance) VALUES (?, ?, ?)",
                     (dest_id, h['snapshot_date'], h['total_balance']))

def get_current_user_id():
    """Get current user ID from session."""
    return session.get('user_id')

def calculate_total_balance(user_id):
    """Get sum of all account balances for a user."""
    conn = get_db_connection()
    result = conn.execute("SELECT SUM(balance) as total FROM accounts WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return float(result['total']) if result['total'] else 0.0

def get_credit_card_debt(user_id):
    """Get total credit card debt for a user."""
    conn = get_db_connection()
    result = conn.execute("SELECT SUM(debt_amount) as total FROM credit_cards WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return float(result['total']) if result['total'] else 0.0

def update_balance_history(user_id):
    """Record current total balance in history for a user."""
    conn = get_db_connection()
    today = datetime.utcnow().date().isoformat()
    balance = calculate_total_balance(user_id)
    try:
        conn.execute(
            "INSERT INTO balance_history (user_id, snapshot_date, total_balance) VALUES (?, ?, ?)",
            (user_id, today, balance)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.execute(
            "UPDATE balance_history SET total_balance = ? WHERE user_id = ? AND snapshot_date = ?",
            (balance, user_id, today)
        )
        conn.commit()
    conn.close()

# Routes

@app.route('/api/register', methods=['POST'])
def register():
    """Register a new user."""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), datetime.utcnow().isoformat())
        )
        conn.commit()
        user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        
        session['user_id'] = user['id']
        return jsonify({'success': True, 'message': 'Registration successful'}), 201
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Username already exists'}), 400

@app.route('/api/login', methods=['POST'])
def login():
    """Login user, provisioning a sandbox session if it is a demo account."""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    conn = get_db_connection()
    user = conn.execute("SELECT id, password FROM users WHERE username = ?", (username,)).fetchone()

    if not user or not check_password_hash(user['password'], password):
        conn.close()
        return jsonify({'error': 'Invalid username or password'}), 401
    
    if username.lower() == 'demo':
        # Trigger background cleanup of old sessions
        cleanup_old_demo_sessions()
        
        # Provision isolated demo session
        session_username = f"demo_session_{uuid.uuid4().hex}"
        cur = conn.execute(
            "INSERT INTO users (username, password, created_at) VALUES (?, ?, ?)",
            (session_username, generate_password_hash('ephemeral'), datetime.utcnow().isoformat())
        )
        new_demo_id = cur.lastrowid
        clone_demo_data(conn, user['id'], new_demo_id)
        conn.commit()
        session['user_id'] = new_demo_id
    else:
        session['user_id'] = user['id']
        
    conn.close()
    return jsonify({'success': True, 'message': 'Login successful'}), 200

@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout user and immediately drop demo sandbox if applicable."""
    user_id = session.get('user_id')
    if user_id:
        conn = get_db_connection()
        user = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
        if user and user['username'].startswith('demo_session_'):
            cleanup_user(conn, user_id)
            conn.commit()
        conn.close()
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out'}), 200

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    """Check if user is authenticated."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'authenticated': False}), 401
    return jsonify({'authenticated': True, 'user_id': user_id}), 200

@app.route('/', methods=['GET'])
def index():
    """Serve the dashboard HTML."""
    return render_template('index.html')

@app.route('/api/overview', methods=['GET'])
def overview():
    """Get complete dashboard overview for current user."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = get_db_connection()
    accounts = conn.execute("SELECT id, name, type, balance FROM accounts WHERE user_id = ?", (user_id,)).fetchall()
    recent_txns = conn.execute(
        "SELECT t.*, a.name as account_name FROM transactions t LEFT JOIN accounts a ON t.account_id = a.id WHERE t.user_id = ? ORDER BY t.created_at DESC LIMIT 8",
        (user_id,)
    ).fetchall()
    budgets = conn.execute("SELECT id, category, limit_amount, spent_amount FROM budgets WHERE user_id = ?", (user_id,)).fetchall()
    history = conn.execute("SELECT snapshot_date as date, total_balance as balance FROM balance_history WHERE user_id = ? ORDER BY snapshot_date ASC", (user_id,)).fetchall()
    credit_cards = conn.execute("SELECT id, card_name, debt_amount, credit_limit FROM credit_cards WHERE user_id = ?", (user_id,)).fetchall()

    # Get expense breakdown by category (current month)
    expenses = conn.execute(
        "SELECT category, SUM(amount) as amount FROM transactions WHERE user_id = ? AND transaction_type = 'Debit' AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now') GROUP BY category",
        (user_id,)
    ).fetchall()
    # Get expense breakdown for last month
    last_month_expenses = conn.execute(
        "SELECT category, SUM(amount) as amount FROM transactions WHERE user_id = ? AND transaction_type = 'Debit' AND strftime('%Y-%m', created_at) = strftime('%Y-%m', datetime('now', '-1 month')) GROUP BY category",
        (user_id,)
    ).fetchall()
    conn.close()

    return jsonify({
        'total_balance': calculate_total_balance(user_id),
        'credit_card_debt': get_credit_card_debt(user_id),
        'accounts': [
            {'id': row['id'], 'name': row['name'], 'type': row['type'], 'balance': float(row['balance'])}
            for row in accounts
        ],
        'recent_transactions': [
            {
                'id': row['id'],
                'account_name': row['account_name'],
                'date': row['created_at'],
                'description': row['description'] or row['category'],
                'category': row['category'],
                'transaction_type': row['transaction_type'],
                'amount': float(row['amount'])
            }
            for row in recent_txns
        ],
        'budgets': [
            {
                'id': row['id'],
                'category': row['category'],
                'limit': float(row['limit_amount']),
                'spent': float(row['spent_amount']),
                'percentage': int((float(row['spent_amount']) / float(row['limit_amount']) * 100)) if row['limit_amount'] > 0 else 0
            }
            for row in budgets
        ],
        'expense_breakdown': [
            {'category': row['category'], 'amount': float(row['amount'])}
            for row in expenses
        ],
        'last_month_expenses': [
            {'category': row['category'], 'amount': float(row['amount'])}
            for row in last_month_expenses
        ],
        'balance_history': [
            {'date': row['date'], 'balance': float(row['balance'])}
            for row in history
        ],
        'credit_cards': [
            {
                'id': row['id'],
                'name': row['card_name'],
                'debt': float(row['debt_amount']),
                'limit': float(row['credit_limit']),
                'utilization': int((float(row['debt_amount']) / float(row['credit_limit']) * 100)) if row['credit_limit'] > 0 else 0
            }
            for row in credit_cards
        ]
    })

@app.route('/api/transaction', methods=['POST'])
def add_transaction():
    """Add a new transaction."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    try:
        amount = float(data.get('amount', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'Amount must be a valid number'}), 400
        
    account_id = int(data.get('account_id', 2))
    transaction_type = data.get('transaction_type', 'Debit')
    category = data.get('category', 'General')
    description = data.get('description', '')

    if amount <= 0 or math.isnan(amount) or math.isinf(amount):
        return jsonify({'error': 'Amount must be a valid positive number'}), 400

    conn = get_db_connection()
    conn.isolation_level = 'EXCLUSIVE'
    cur = conn.cursor()
    
    try:
        cur.execute("BEGIN EXCLUSIVE")
        # Check actual balance first and lock DB
        cur.execute("SELECT name, balance FROM accounts WHERE id = ? AND user_id = ?", (account_id, user_id))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return jsonify({'error': 'Account not found'}), 404
            
        current_balance = float(row['balance'])
        account_name = row['name']
        
        if transaction_type == 'Debit' and current_balance < amount:
            shortfall = amount - current_balance
            
            # Find eligible alternate accounts
            cur.execute("SELECT id, name, balance FROM accounts WHERE user_id = ? AND type != 'Credit Card' AND id != ? AND balance >= ? ORDER BY balance DESC", (user_id, account_id, amount))
            alternatives = []
            for alt in cur.fetchall():
                alternatives.append({
                    'id': alt['id'],
                    'name': alt['name'],
                    'balance': float(alt['balance'])
                })
                
            conn.rollback()
            conn.close()
            
            return jsonify({
                'success': False,
                'error': 'INSUFFICIENT_FUNDS',
                'message': f"Insufficient funds. You are trying to debit ₹{amount:,.2f}, but the selected account has only ₹{current_balance:,.2f} available.",
                'requestedAmount': amount,
                'availableBalance': current_balance,
                'shortfall': shortfall,
                'suggestedAccounts': alternatives
            }), 400

        # Update account balance
        if transaction_type == 'Credit':
            cur.execute("UPDATE accounts SET balance = balance + ? WHERE id = ? AND user_id = ?", (amount, account_id, user_id))
        else:
            cur.execute("UPDATE accounts SET balance = balance - ? WHERE id = ? AND user_id = ?", (amount, account_id, user_id))

        # Add transaction record
        created_at = datetime.utcnow().isoformat()
        cur.execute(
            "INSERT INTO transactions (user_id, account_id, amount, transaction_type, category, description, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, account_id, amount, transaction_type, category, description, created_at)
        )

        # Update budget spent amount if debit
        if transaction_type == 'Debit':
            cur.execute(
                "UPDATE budgets SET spent_amount = spent_amount + ? WHERE user_id = ? AND category = ?",
                (amount, user_id, category)
            )

        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'error': str(e)}), 500
    update_balance_history(user_id)

    # Fetch updated overview
    conn = get_db_connection()
    accounts = conn.execute("SELECT id, name, type, balance FROM accounts WHERE user_id = ?", (user_id,)).fetchall()
    recent_txns = conn.execute(
        "SELECT t.*, a.name as account_name FROM transactions t LEFT JOIN accounts a ON t.account_id = a.id WHERE t.user_id = ? ORDER BY t.created_at DESC LIMIT 8",
        (user_id,)
    ).fetchall()
    budgets = conn.execute("SELECT id, category, limit_amount, spent_amount FROM budgets WHERE user_id = ?", (user_id,)).fetchall()
    history = conn.execute("SELECT snapshot_date as date, total_balance as balance FROM balance_history WHERE user_id = ? ORDER BY snapshot_date ASC", (user_id,)).fetchall()
    conn.close()

    return jsonify({
        'total_balance': calculate_total_balance(user_id),
        'credit_card_debt': get_credit_card_debt(user_id),
        'accounts': [
            {'id': row['id'], 'name': row['name'], 'type': row['type'], 'balance': float(row['balance'])}
            for row in accounts
        ],
        'recent_transactions': [
            {
                'id': row['id'],
                'account_name': row['account_name'],
                'date': row['created_at'],
                'description': row['description'] or row['category'],
                'category': row['category'],
                'transaction_type': row['transaction_type'],
                'amount': float(row['amount'])
            }
            for row in recent_txns
        ],
        'budgets': [
            {
                'id': row['id'],
                'category': row['category'],
                'limit': float(row['limit_amount']),
                'spent': float(row['spent_amount']),
                'percentage': int((float(row['spent_amount']) / float(row['limit_amount']) * 100)) if row['limit_amount'] > 0 else 0
            }
            for row in budgets
        ],
        'balance_history': [
            {'date': row['date'], 'balance': float(row['balance'])}
            for row in history
        ]
    })

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Get all accounts for current user."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = get_db_connection()
    accounts = conn.execute("SELECT id, name, type, balance FROM accounts WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    return jsonify([
        {'id': row['id'], 'name': row['name'], 'type': row['type'], 'balance': float(row['balance'])}
        for row in accounts
    ])

@app.route('/api/accounts', methods=['POST'])
def create_account():
    """Create a new account."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    name = data.get('name')
    account_type = data.get('type', 'Checking')
    balance = float(data.get('balance', 0))

    if not name:
        return jsonify({'error': 'Account name is required'}), 400

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO accounts (user_id, name, type, balance) VALUES (?, ?, ?, ?)",
            (user_id, name, account_type, balance)
        )
        conn.commit()
        update_balance_history(user_id)
        
        # Return full overview
        accounts = conn.execute("SELECT id, name, type, balance FROM accounts WHERE user_id = ?", (user_id,)).fetchall()
        recent_txns = conn.execute(
            "SELECT t.*, a.name as account_name FROM transactions t LEFT JOIN accounts a ON t.account_id = a.id WHERE t.user_id = ? ORDER BY t.created_at DESC LIMIT 8",
            (user_id,)
        ).fetchall()
        budgets = conn.execute("SELECT id, category, limit_amount, spent_amount FROM budgets WHERE user_id = ?", (user_id,)).fetchall()
        history = conn.execute("SELECT snapshot_date as date, total_balance as balance FROM balance_history WHERE user_id = ? ORDER BY snapshot_date ASC", (user_id,)).fetchall()
        conn.close()
        
        return jsonify({
            'total_balance': calculate_total_balance(user_id),
            'credit_card_debt': get_credit_card_debt(user_id),
            'accounts': [{'id': row['id'], 'name': row['name'], 'type': row['type'], 'balance': float(row['balance'])} for row in accounts],
            'recent_transactions': [{'id': row['id'], 'account_name': row['account_name'], 'date': row['created_at'], 'description': row['description'] or row['category'], 'category': row['category'], 'transaction_type': row['transaction_type'], 'amount': float(row['amount'])} for row in recent_txns],
            'budgets': [{'id': row['id'], 'category': row['category'], 'limit': float(row['limit_amount']), 'spent': float(row['spent_amount']), 'percentage': int((float(row['spent_amount']) / float(row['limit_amount']) * 100)) if row['limit_amount'] > 0 else 0} for row in budgets],
            'balance_history': [{'date': row['date'], 'balance': float(row['balance'])} for row in history]
        })
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Account name already exists'}), 400

@app.route('/api/accounts/<int:account_id>', methods=['PUT'])
def update_account(account_id):
    """Update account balance."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    new_balance = float(data.get('balance', 0))

    conn = get_db_connection()
    conn.execute("UPDATE accounts SET balance = ? WHERE id = ? AND user_id = ?", (new_balance, account_id, user_id))
    conn.commit()
    update_balance_history(user_id)
    result = conn.execute("SELECT id, name, type, balance FROM accounts WHERE id = ? AND user_id = ?", (account_id, user_id)).fetchone()
    conn.close()

    if not result:
        return jsonify({'error': 'Account not found'}), 404

    return jsonify({'id': result['id'], 'name': result['name'], 'type': result['type'], 'balance': float(result['balance'])})

@app.route('/api/budgets', methods=['GET'])
def get_budgets():
    """Get all budgets for current user."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = get_db_connection()
    budgets = conn.execute("SELECT id, category, limit_amount, spent_amount FROM budgets WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    return jsonify([
        {
            'id': row['id'],
            'category': row['category'],
            'limit': float(row['limit_amount']),
            'spent': float(row['spent_amount']),
            'percentage': int((float(row['spent_amount']) / float(row['limit_amount']) * 100)) if row['limit_amount'] > 0 else 0
        }
        for row in budgets
    ])

@app.route('/api/budgets', methods=['POST'])
def create_budget():
    """Create a new budget."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    category = data.get('category')
    limit_amount = float(data.get('limit', 0))

    if not category or limit_amount <= 0:
        return jsonify({'error': 'Category and limit are required'}), 400

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO budgets (user_id, category, limit_amount, spent_amount, created_at) VALUES (?, ?, ?, 0, ?)",
            (user_id, category, limit_amount, datetime.utcnow().isoformat())
        )
        conn.commit()
        
        # Return full overview
        accounts = conn.execute("SELECT id, name, type, balance FROM accounts WHERE user_id = ?", (user_id,)).fetchall()
        recent_txns = conn.execute(
            "SELECT t.*, a.name as account_name FROM transactions t LEFT JOIN accounts a ON t.account_id = a.id WHERE t.user_id = ? ORDER BY t.created_at DESC LIMIT 8",
            (user_id,)
        ).fetchall()
        budgets = conn.execute("SELECT id, category, limit_amount, spent_amount FROM budgets WHERE user_id = ?", (user_id,)).fetchall()
        history = conn.execute("SELECT snapshot_date as date, total_balance as balance FROM balance_history WHERE user_id = ? ORDER BY snapshot_date ASC", (user_id,)).fetchall()
        conn.close()
        
        return jsonify({
            'total_balance': calculate_total_balance(user_id),
            'credit_card_debt': get_credit_card_debt(user_id),
            'accounts': [{'id': row['id'], 'name': row['name'], 'type': row['type'], 'balance': float(row['balance'])} for row in accounts],
            'recent_transactions': [{'id': row['id'], 'account_name': row['account_name'], 'date': row['created_at'], 'description': row['description'] or row['category'], 'category': row['category'], 'transaction_type': row['transaction_type'], 'amount': float(row['amount'])} for row in recent_txns],
            'budgets': [{'id': row['id'], 'category': row['category'], 'limit': float(row['limit_amount']), 'spent': float(row['spent_amount']), 'percentage': int((float(row['spent_amount']) / float(row['limit_amount']) * 100)) if row['limit_amount'] > 0 else 0} for row in budgets],
            'balance_history': [{'date': row['date'], 'balance': float(row['balance'])} for row in history]
        })
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Budget category already exists'}), 400

@app.route('/api/budgets/<int:budget_id>', methods=['PUT'])
def update_budget(budget_id):
    """Update budget limit."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    new_limit = float(data.get('limit', 0))

    if new_limit <= 0:
        return jsonify({'error': 'Limit must be greater than zero'}), 400

    conn = get_db_connection()
    conn.execute("UPDATE budgets SET limit_amount = ? WHERE id = ? AND user_id = ?", (new_limit, budget_id, user_id))
    conn.commit()
    result = conn.execute("SELECT id, category, limit_amount, spent_amount FROM budgets WHERE id = ? AND user_id = ?", (budget_id, user_id)).fetchone()
    conn.close()

    if not result:
        return jsonify({'error': 'Budget not found'}), 404

    return jsonify({
        'id': result['id'],
        'category': result['category'],
        'limit': float(result['limit_amount']),
        'spent': float(result['spent_amount']),
        'percentage': int((float(result['spent_amount']) / float(result['limit_amount']) * 100)) if result['limit_amount'] > 0 else 0
    })

@app.route('/api/credit-cards', methods=['GET'])
def get_credit_cards():
    """Get all credit cards for current user."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    conn = get_db_connection()
    cards = conn.execute("SELECT id, card_name, debt_amount, credit_limit FROM credit_cards WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    return jsonify([
        {
            'id': row['id'],
            'name': row['card_name'],
            'debt': float(row['debt_amount']),
            'limit': float(row['credit_limit']),
            'utilization': int((float(row['debt_amount']) / float(row['credit_limit']) * 100)) if row['credit_limit'] > 0 else 0
        }
        for row in cards
    ])

@app.route('/api/credit-cards/<int:card_id>', methods=['PUT'])
def update_credit_card(card_id):
    """Update credit card debt."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    data = request.get_json()
    new_debt = float(data.get('debt', 0))

    conn = get_db_connection()
    conn.execute(
        "UPDATE credit_cards SET debt_amount = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (new_debt, datetime.utcnow().isoformat(), card_id, user_id)
    )
    conn.commit()
    result = conn.execute("SELECT id, card_name, debt_amount, credit_limit FROM credit_cards WHERE id = ? AND user_id = ?", (card_id, user_id)).fetchone()
    conn.close()

    if not result:
        return jsonify({'error': 'Credit card not found'}), 404

    return jsonify({
        'id': result['id'],
        'name': result['card_name'],
        'debt': float(result['debt_amount']),
        'limit': float(result['credit_limit']),
        'utilization': int((float(result['debt_amount']) / float(result['credit_limit']) * 100)) if result['credit_limit'] > 0 else 0
    })

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5001)
