// Global state
let globalData = {};
let filteredTransactions = [];
let currentPage = 1;
const itemsPerPage = 8;
let currentView = 'view-dashboard';

// Utilities
function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icon = type === 'success'
        ? `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color:var(--success)"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`
        : `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color:var(--danger)"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;

    toast.innerHTML = `${icon} <span style="font-size: 14px; font-weight: 500;">${message}</span>`;
    container.appendChild(toast);

    // Trigger animation
    setTimeout(() => toast.classList.add('show'), 10);

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function hexToRGBA(hex, alpha) {
    const normalized = hex.replace('#', '');
    const bigint = parseInt(normalized, 16);
    const r = (bigint >> 16) & 255;
    const g = (bigint >> 8) & 255;
    const b = bigint & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

// Layout & View Management
function switchView(viewId, title) {
    // Hide all sections
    document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
    document.getElementById(viewId).classList.add('active');

    // Update sidebar active states
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    const activeNav = document.querySelector(`.nav-item[data-target="${viewId}"]`);
    if (activeNav) activeNav.classList.add('active');

    // Update Title
    const titles = {
        'view-dashboard': { title: 'Dashboard', sub: "Here's your financial overview." },
        'view-transactions': { title: 'Transactions', sub: 'Your comprehensive history.' },
        'view-expenses': { title: 'Expenses', sub: 'Record and track where your money goes.' },
        'view-income': { title: 'Income', sub: 'Record incoming funds.' },
        'view-budgets': { title: 'Budgets', sub: 'Manage category spending limits.' },
        'view-savings': { title: 'Accounts & Savings', sub: 'Manage your accounts and liquidity.' },
        'view-settings': { title: 'Settings', sub: 'Configure your preferences.' }
    };

    const tInfo = titles[viewId];
    if (tInfo) {
        document.getElementById('pageTitle').innerText = tInfo.title;
        document.getElementById('pageSubtitle').innerText = tInfo.sub;
        document.getElementById('navTitles').style.display = 'block';
    }

    if (window.innerWidth <= 768) {
        document.getElementById('appSidebar').classList.remove('open');
    }
}

document.querySelectorAll('.nav-item[data-target]').forEach(item => {
    item.addEventListener('click', (e) => {
        switchView(e.currentTarget.getAttribute('data-target'));
    });
});

// Authentication
function toggleAuth(e) {
    e.preventDefault();
    const loginTab = document.getElementById('loginTab');
    const registerTab = document.getElementById('registerTab');
    if (loginTab.style.display !== 'none') {
        loginTab.style.display = 'none';
        registerTab.style.display = 'block';
    } else {
        loginTab.style.display = 'block';
        registerTab.style.display = 'none';
    }
}

async function checkAuth() {
    try {
        const response = await fetch('/api/check-auth', { credentials: 'include' });
        if (response.ok) {
            document.getElementById('authContainer').style.display = 'none';
            document.getElementById('mainApp').style.display = 'flex';
            loadDashboard();
        } else {
            document.getElementById('authContainer').style.display = 'flex';
            document.getElementById('mainApp').style.display = 'none';
        }
    } catch (error) {
        console.error('Auth check failed:', error);
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    const errorEl = document.getElementById('loginError');
    errorEl.textContent = '';

    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        if (!response.ok) {
            const data = await response.json();
            errorEl.textContent = data.error || 'Login failed';
            return;
        }

        document.getElementById('userNamePlaceholder').innerText = username;
        // Set initial dynamically
        document.querySelector('.avatar').innerText = username.substring(0, 2).toUpperCase();

        document.getElementById('loginForm').reset();
        checkAuth();
    } catch (error) {
        errorEl.textContent = 'Error during login';
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const username = document.getElementById('registerUsername').value;
    const password = document.getElementById('registerPassword').value;
    const confirm = document.getElementById('registerConfirm').value;
    const errorEl = document.getElementById('registerError');
    errorEl.textContent = '';

    if (password !== confirm) {
        errorEl.textContent = 'Passwords do not match';
        return;
    }

    try {
        const response = await fetch('/api/register', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        if (!response.ok) {
            const data = await response.json();
            errorEl.textContent = data.error || 'Registration failed';
            return;
        }

        document.getElementById('registerForm').reset();
        toggleAuth({ preventDefault: () => { } });
        showToast('Registration successful! Please login.', 'success');
    } catch (error) {
        errorEl.textContent = 'Error during registration';
    }
}

async function handleLogout() {
    try {
        await fetch('/api/logout', { method: 'POST', credentials: 'include' });
        checkAuth();
    } catch (error) {
        console.error('Logout failed:', error);
    }
}

// Data Loading
async function loadDashboard() {
    try {
        const response = await fetch('/api/overview?t=' + Date.now(), { credentials: 'include' });
        if (!response.ok) throw new Error('Failed to load data');
        const data = await response.json();
        globalData = data;
        filteredTransactions = data.recent_transactions || [];
        currentPage = 1;
        updateUI(data);
    } catch (error) {
        console.error('Dashboard load error:', error);
        showToast('Error loading dashboard data', 'error');
    }
}

// UI Updating
function updateUI(data) {
    // Update Header Totals
    document.getElementById('dashboardTotalBalance').textContent = '₹' + (data.total_balance || 0).toFixed(2);

    // Calculate Income & Expenses
    let totalIncome = 0;
    let totalExpense = 0;
    (data.recent_transactions || []).forEach(tx => {
        // Crude calculation, just for visual overview based on recent Tx
        if (tx.transaction_type === 'Credit') totalIncome += tx.amount;
        if (tx.transaction_type === 'Debit') totalExpense += tx.amount;
    });

    document.getElementById('dashboardTotalIncome').textContent = '₹' + totalIncome.toFixed(2);
    document.getElementById('dashboardTotalExpenses').textContent = '₹' + totalExpense.toFixed(2);

    let savingsBal = 0;
    (data.accounts || []).forEach(acc => {
        if (acc.type === 'Savings') savingsBal += acc.balance;
    });
    document.getElementById('dashboardTotalSavings').textContent = '₹' + savingsBal.toFixed(2);

    // Update Dropdowns
    populateDropdowns(data);

    // Draw Dashboard Tables
    renderDashboardTransactions(data.recent_transactions);

    // Render Full Transactions Grid
    renderFullTransactionsList();

    // Render Accounts
    renderAccounts(data.accounts);

    // Render Budgets
    renderBudgets(data.budgets);

    // Draw Charts
    drawCharts(data);
}

function populateDropdowns(data) {
    const accounts = data.accounts || [];
    let accHtml = '';
    accounts.forEach(acc => {
        accHtml += `<option value="${acc.id}">${acc.name} (₹${acc.balance.toFixed(2)})</option>`;
    });

    document.querySelectorAll('.tx-account-select').forEach(sel => sel.innerHTML = accHtml);

    const predefined = ['Income', 'Entertainment', 'Groceries', 'Travel', 'Utilities', 'Other'];
    let budgets = data.budgets || [];
    budgets.forEach(b => {
        if (!predefined.includes(b.category)) predefined.push(b.category);
    });

    let catHtml = '';
    predefined.forEach(cat => {
        catHtml += `<option value="${cat}">${cat}</option>`;
    });

    document.querySelectorAll('.tx-category-select').forEach(sel => sel.innerHTML = catHtml);

    const filterCat = document.getElementById('filterTxCategory');
    filterCat.innerHTML = `<option value="">All Categories</option>` + catHtml;
}

// Sections Rendering
function renderDashboardTransactions(transactions) {
    const tbody = document.getElementById('dashboardRecentTxTbody');
    tbody.innerHTML = '';
    const subset = (transactions || []).slice(0, 5);

    subset.forEach(txn => {
        const isCredit = txn.transaction_type === 'Credit';
        const indicator = isCredit ? '<span class="trend-amount trend-positive">+</span>' : '<span class="trend-amount trend-negative">-</span>';

        tbody.innerHTML += `
        <tr>
          <td><span style="color: var(--text-secondary)">${new Date(txn.date).toLocaleDateString()}</span></td>
          <td style="font-weight: 500">${txn.description}</td>
          <td><span class="badge">${txn.category}</span></td>
          <td style="text-align: right;">${indicator} ₹${txn.amount.toFixed(2)}</td>
        </tr>
      `;
    });
}

function renderFullTransactionsList() {
    const tbody = document.getElementById('fullTransactionsTbody');
    const emptyState = document.getElementById('txEmptyState');
    tbody.innerHTML = '';

    if (!filteredTransactions || filteredTransactions.length === 0) {
        emptyState.style.display = 'flex';
        document.getElementById('txPageInfo').style.display = 'none';
        return;
    }

    emptyState.style.display = 'none';
    document.getElementById('txPageInfo').style.display = 'block';

    const start = (currentPage - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    const pageTx = filteredTransactions.slice(start, end);

    pageTx.forEach(txn => {
        const isCredit = txn.transaction_type === 'Credit';
        const indicator = isCredit ? '<span class="trend-amount trend-positive">+</span>' : '<span class="trend-amount trend-negative">-</span>';

        tbody.innerHTML += `
        <tr>
          <td><span style="color: var(--text-secondary)">${new Date(txn.date).toLocaleDateString()}</span></td>
          <td style="font-weight: 500">${txn.description}</td>
          <td><span class="badge">${txn.category}</span></td>
          <td style="text-align: right;">${indicator} ₹${txn.amount.toFixed(2)}</td>
        </tr>
      `;
    });

    document.getElementById('txPageInfo').innerText = `Showing ${start + 1}-${Math.min(end, filteredTransactions.length)} of ${filteredTransactions.length}`;
    document.getElementById('btnPrevPage').disabled = currentPage === 1;
    document.getElementById('btnNextPage').disabled = end >= filteredTransactions.length;
}

function filterTransactionsList() {
    const filterType = document.getElementById('filterTxType').value;
    const filterCategory = document.getElementById('filterTxCategory').value;
    const filterSort = document.getElementById('filterTxSort').value;

    filteredTransactions = (globalData.recent_transactions || []).filter(tx => {
        return (!filterType || tx.transaction_type === filterType) &&
            (!filterCategory || tx.category === filterCategory);
    });

    if (filterSort === 'amount_asc') {
        filteredTransactions.sort((a, b) => a.amount - b.amount);
    } else if (filterSort === 'amount_desc') {
        filteredTransactions.sort((a, b) => b.amount - a.amount);
    } else if (filterSort === 'date_asc') {
        filteredTransactions.sort((a, b) => new Date(a.date) - new Date(b.date));
    } else {
        filteredTransactions.sort((a, b) => new Date(b.date) - new Date(a.date));
    }

    currentPage = 1;
    renderFullTransactionsList();
}

function resetTxFilters() {
    document.getElementById('filterTxType').value = '';
    document.getElementById('filterTxCategory').value = '';
    document.getElementById('filterTxSort').value = 'date_desc';
    filterTransactionsList();
}

function prevTxPage() { if (currentPage > 1) { currentPage--; renderFullTransactionsList(); } }
function nextTxPage() {
    const max = Math.ceil(filteredTransactions.length / itemsPerPage);
    if (currentPage < max) { currentPage++; renderFullTransactionsList(); }
}

function renderBudgets(budgets) {
    const container = document.getElementById('budgetBarsContainer');
    container.innerHTML = '';
    if (!budgets || budgets.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>No budgets created yet.</p></div>';
        return;
    }

    budgets.forEach(b => {
        let colorClass = 'green';
        if (b.percentage > 75) colorClass = 'orange';
        if (b.percentage >= 100) colorClass = 'red';

        container.innerHTML += `
      <div class="progress-group">
        <div class="progress-header">
          <span>${b.category}</span>
          <span><span style="color: var(--text-secondary)">₹${b.spent.toFixed(2)} /</span> ₹${b.limit.toFixed(2)}</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill ${colorClass}" style="width: ${Math.min(b.percentage, 100)}%;"></div>
        </div>
      </div>
    `;
    });
}

function renderAccounts(accounts) {
    const tbody = document.getElementById('accountsTableBody');
    tbody.innerHTML = '';
    if (!accounts || accounts.length === 0) return;

    accounts.forEach(acc => {
        let badgeType = 'badge';
        if (acc.type === 'Savings') badgeType += ' trend-positive';
        tbody.innerHTML += `
      <tr>
        <td style="font-weight: 600;">${acc.name}</td>
        <td><span class="${badgeType}" style="border: 1px solid var(--border)">${acc.type}</span></td>
        <td style="text-align: right; font-weight: 500;">₹${acc.balance.toFixed(2)}</td>
      </tr>
    `;
    });
}


// Data Submissions
async function submitTransaction(e, defaultType) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);

    const txData = {
        amount: parseFloat(formData.get('amount')),
        account_id: parseInt(formData.get('account')),
        transaction_type: defaultType,
        category: formData.get('category'),
        description: formData.get('description') || formData.get('category')
    };

    try {
        const res = await fetch('/api/transaction', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(txData)
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            if (err.error === 'INSUFFICIENT_FUNDS') {
                document.getElementById('ifmMessage').innerText = err.message;
                const modal = document.getElementById('insufficientFundsModal');
                const container = document.getElementById('ifmSuggestionsContainer');
                const select = document.getElementById('ifmAccountSelect');
                const btn = document.getElementById('ifmSelectBtn');

                if (err.suggestedAccounts && err.suggestedAccounts.length > 0) {
                    container.style.display = 'block';
                    select.innerHTML = '';
                    err.suggestedAccounts.forEach(acc => {
                        select.innerHTML += `<option value="${acc.id}">${acc.name} (₹${acc.balance.toFixed(2)})</option>`;
                    });
                    btn.style.display = 'block';
                    btn.onclick = () => {
                        // Update the original form with the new selected account
                        form.querySelector('.tx-account-select').value = select.value;
                        modal.classList.remove('show');
                        setTimeout(() => modal.style.display = 'none', 300);
                    };
                } else {
                    container.style.display = 'none';
                    btn.style.display = 'none';
                }
                modal.style.display = 'flex';
                // setTimeout needed to allow display flex to apply before opacity transition
                setTimeout(() => modal.classList.add('show'), 10);
                throw new Error(err.message);
            }
            throw new Error(err.error || 'Server error');
        }

        const updatedData = await res.json();
        globalData = updatedData;
        filteredTransactions = updatedData.recent_transactions;
        updateUI(updatedData);
        form.reset();
        showToast(`${defaultType} recorded successfully`);

        // Optionally switch back to Dashboard on success
        switchView('view-dashboard');
    } catch (err) {
        if (err.message.indexOf('Insufficient funds') === -1) {
            showToast(err.message, 'error');
        }
    }
}

async function submitBudget(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);

    const budgetData = {
        category: formData.get('category'),
        limit: parseFloat(formData.get('limit'))
    };

    try {
        const response = await fetch('/api/budgets', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(budgetData)
        });

        if (!response.ok) throw new Error('Failed to add budget');
        showToast('Budget created successfully');
        loadDashboard();
        form.reset();
    } catch (error) {
        console.error(error);
        showToast(error.message, 'error');
    }
}

async function submitAccount(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);

    const accData = {
        name: formData.get('name'),
        type: formData.get('type'),
        balance: parseFloat(formData.get('balance'))
    };

    try {
        const response = await fetch('/api/accounts', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(accData)
        });

        if (!response.ok) throw new Error('Failed to create account');
        showToast('Account added successfully');

        const resData = await response.json();
        globalData = resData;
        updateUI(resData);
        form.reset();
    } catch (error) {
        console.error(error);
        showToast(error.message, 'error');
    }
}

function closeModal(id) {
    const modal = document.getElementById(id);
    modal.classList.remove('show');
    setTimeout(() => modal.style.display = 'none', 300);
}

// Visuals/Charts
function changeTheme() {
    const val = document.getElementById('themeSelector').value;
    document.body.setAttribute('data-theme', val);

    // Refresh charts for theme consistency
    if (globalData.accounts) {
        drawCharts(globalData);
    }
}

function drawCharts(data) {
    const isDark = document.body.getAttribute('data-theme') === 'dark';
    const textColor = isDark ? '#94A3B8' : '#64748B';
    const gridColor = isDark ? '#1E293B' : '#E2E8F0';

    if (window.chartIncExp) window.chartIncExp.destroy();
    if (window.chartBrkDown) window.chartBrkDown.destroy();

    const expenseBreakdown = data.expense_breakdown || [];

    // 1. Income vs Expense Trend (Area/Line or Bar)
    const ctx1 = document.getElementById('chartIncomeExpense').getContext('2d');

    // Fake historical data using actual balance history over last 7 points for visual impact
    const history = data.balance_history || [];
    const labels = history.map(h => new Date(h.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
    const balances = history.map(h => h.balance);

    window.chartIncExp = new Chart(ctx1, {
        type: 'line',
        data: {
            labels: labels.length ? labels : ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
            datasets: [{
                label: 'Total Balance Over Time',
                data: balances.length ? balances : [1000, 2500, 2000, 4500, 6000],
                borderColor: '#16A34A',
                backgroundColor: 'rgba(22, 163, 74, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: gridColor },
                    ticks: { color: textColor }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: textColor }
                }
            }
        }
    });

    // 2. Expense Breakdown (Doughnut)
    const ctx2 = document.getElementById('chartExpenseBreakdown').getContext('2d');
    const catLabels = expenseBreakdown.length ? expenseBreakdown.map(e => e.category) : ['No Data'];
    const catData = expenseBreakdown.length ? expenseBreakdown.map(e => e.amount) : [1];

    const colors = ['#16A34A', '#2563EB', '#F59E0B', '#8B5CF6', '#EC4899', '#06B6D4'];

    window.chartBrkDown = new Chart(ctx2, {
        type: 'doughnut',
        data: {
            labels: catLabels,
            datasets: [{
                data: catData,
                backgroundColor: colors.slice(0, catLabels.length),
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '75%',
            plugins: {
                legend: { display: false }
            }
        }
    });

    // Custom legend
    const legendDiv = document.getElementById('expenseLegend');
    legendDiv.innerHTML = '';
    catLabels.forEach((label, i) => {
        if (label !== 'No Data') {
            legendDiv.innerHTML += `
        <div style="display:flex; justify-content: space-between; align-items: center; padding: 4px 6px;">
          <div style="display:flex; align-items: center; gap: 8px;">
            <div style="width: 10px; height: 10px; border-radius: 50%; background: ${colors[i % colors.length]}"></div>
            <span>${label}</span>
          </div>
          <span style="font-weight: 600;">₹${catData[i].toFixed(2)}</span>
        </div>
      `;
        }
    });
}

// Initial bootstrap
document.addEventListener('DOMContentLoaded', () => {
    // Try login
    checkAuth();
});
