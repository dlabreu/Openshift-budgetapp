import json
import os
import uuid
from collections import defaultdict
from datetime import date, datetime

import requests
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "budget-app-secret-key-2024")
app.config["SHOW_TEST_BANNER"] = os.environ.get("SHOW_TEST_BANNER", "false").lower() == "true"

DATA_DIR = "data"
TRANSACTIONS_FILE = os.path.join(DATA_DIR, "transactions.json")
BUDGETS_FILE = os.path.join(DATA_DIR, "budgets.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
RATES_FILE = os.path.join(DATA_DIR, "rates.json")

CURRENCIES = {
    "USD": {"symbol": "$", "name": "US Dollar"},
    "EUR": {"symbol": "€", "name": "Euro"},
    "GBP": {"symbol": "£", "name": "British Pound"},
    "ZAR": {"symbol": "R", "name": "South African Rand"},
    "JPY": {"symbol": "¥", "name": "Japanese Yen"},
    "AUD": {"symbol": "A$", "name": "Australian Dollar"},
    "CAD": {"symbol": "C$", "name": "Canadian Dollar"},
    "CHF": {"symbol": "Fr", "name": "Swiss Franc"},
    "CNY": {"symbol": "¥", "name": "Chinese Yuan"},
    "INR": {"symbol": "₹", "name": "Indian Rupee"},
    "BRL": {"symbol": "R$", "name": "Brazilian Real"},
    "NGN": {"symbol": "₦", "name": "Nigerian Naira"},
}

INCOME_CATEGORIES = [
    "Salary",
    "Freelance",
    "Investment",
    "Business",
    "Rental",
    "Gift",
    "Other Income",
]
EXPENSE_CATEGORIES = [
    "Food & Dining",
    "Housing",
    "Transport",
    "Healthcare",
    "Entertainment",
    "Shopping",
    "Education",
    "Travel",
    "Utilities",
    "Insurance",
    "Savings",
    "Other",
]

FALLBACK_RATES = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "ZAR": 18.63,
    "JPY": 149.50,
    "AUD": 1.53,
    "CAD": 1.36,
    "CHF": 0.89,
    "CNY": 7.24,
    "INR": 83.12,
    "BRL": 4.97,
    "NGN": 1540.0,
}


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_json(filepath, default):
    ensure_data_dir()
    if not os.path.exists(filepath):
        return default
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def save_json(filepath, data):
    ensure_data_dir()
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def get_settings():
    return load_json(SETTINGS_FILE, {"base_currency": "USD"})


def get_rates():
    rates_data = load_json(RATES_FILE, {})
    if rates_data and "rates" in rates_data:
        return rates_data["rates"]
    return FALLBACK_RATES


def convert_amount(amount, from_currency, to_currency):
    if from_currency == to_currency:
        return amount
    rates = get_rates()
    usd_amount = amount / rates.get(from_currency, 1.0)
    return usd_amount * rates.get(to_currency, 1.0)


def format_currency(amount, currency):
    symbol = CURRENCIES.get(currency, {}).get("symbol", currency)
    if currency == "JPY" or currency == "NGN":
        return f"{symbol}{amount:,.0f}"
    return f"{symbol}{amount:,.2f}"


def get_transactions():
    return load_json(TRANSACTIONS_FILE, [])


def save_transactions(transactions):
    save_json(TRANSACTIONS_FILE, transactions)


def get_budgets():
    return load_json(BUDGETS_FILE, [])


def save_budgets(budgets):
    save_json(BUDGETS_FILE, budgets)


@app.route("/")
def index():
    settings = get_settings()
    base_currency = settings["base_currency"]
    transactions = get_transactions()
    now = datetime.now()
    current_month = now.strftime("%Y-%m")

    total_income = 0.0
    total_expenses = 0.0
    month_income = 0.0
    month_expenses = 0.0
    expense_by_category = defaultdict(float)
    monthly_data = defaultdict(lambda: {"income": 0.0, "expenses": 0.0})

    for t in transactions:
        converted = convert_amount(t["amount"], t["currency"], base_currency)
        month = t["date"][:7]
        if t["type"] == "income":
            total_income += converted
            monthly_data[month]["income"] += converted
            if month == current_month:
                month_income += converted
        else:
            total_expenses += converted
            monthly_data[month]["expenses"] += converted
            expense_by_category[t["category"]] += converted
            if month == current_month:
                month_expenses += converted

    balance = total_income - total_expenses
    recent_transactions = sorted(transactions, key=lambda x: x["date"], reverse=True)[
        :5
    ]

    # Budget progress this month
    budgets = get_budgets()
    budget_progress = []
    for b in budgets:
        if b.get("month") == current_month or not b.get("month"):
            spent = expense_by_category.get(b["category"], 0.0)
            limit = convert_amount(b["limit"], b["currency"], base_currency)
            pct = min((spent / limit * 100) if limit > 0 else 0, 100)
            budget_progress.append(
                {
                    "category": b["category"],
                    "spent": spent,
                    "limit": limit,
                    "pct": round(pct, 1),
                    "over": spent > limit,
                }
            )

    # Last 6 months chart data
    months = []
    for i in range(5, -1, -1):
        m = datetime(now.year, now.month, 1)
        month_offset = now.month - i
        year = now.year
        if month_offset <= 0:
            month_offset += 12
            year -= 1
        months.append(f"{year}-{month_offset:02d}")

    chart_labels = [datetime.strptime(m, "%Y-%m").strftime("%b %Y") for m in months]
    chart_income = [round(monthly_data[m]["income"], 2) for m in months]
    chart_expenses = [round(monthly_data[m]["expenses"], 2) for m in months]

    top_categories = sorted(
        expense_by_category.items(), key=lambda x: x[1], reverse=True
    )[:6]
    cat_labels = [c[0] for c in top_categories]
    cat_values = [round(c[1], 2) for c in top_categories]

    return render_template(
        "index.html",
        base_currency=base_currency,
        currencies=CURRENCIES,
        balance=format_currency(balance, base_currency),
        total_income=format_currency(total_income, base_currency),
        total_expenses=format_currency(total_expenses, base_currency),
        month_income=format_currency(month_income, base_currency),
        month_expenses=format_currency(month_expenses, base_currency),
        recent_transactions=recent_transactions,
        budget_progress=budget_progress,
        chart_labels=json.dumps(chart_labels),
        chart_income=json.dumps(chart_income),
        chart_expenses=json.dumps(chart_expenses),
        cat_labels=json.dumps(cat_labels),
        cat_values=json.dumps(cat_values),
        format_currency=format_currency,
        current_month=current_month,
    )


@app.route("/transactions")
def transactions():
    settings = get_settings()
    base_currency = settings["base_currency"]
    all_transactions = get_transactions()
    filter_type = request.args.get("type", "all")
    filter_category = request.args.get("category", "all")
    filter_month = request.args.get("month", "")

    filtered = all_transactions
    if filter_type != "all":
        filtered = [t for t in filtered if t["type"] == filter_type]
    if filter_category != "all":
        filtered = [t for t in filtered if t["category"] == filter_category]
    if filter_month:
        filtered = [t for t in filtered if t["date"].startswith(filter_month)]

    filtered = sorted(filtered, key=lambda x: x["date"], reverse=True)

    return render_template(
        "transactions.html",
        transactions=filtered,
        base_currency=base_currency,
        currencies=CURRENCIES,
        income_categories=INCOME_CATEGORIES,
        expense_categories=EXPENSE_CATEGORIES,
        filter_type=filter_type,
        filter_category=filter_category,
        filter_month=filter_month,
        format_currency=format_currency,
        convert_amount=convert_amount,
        today=date.today().isoformat(),
    )


@app.route("/transactions/add", methods=["POST"])
def add_transaction():
    data = request.form
    transactions = get_transactions()
    transaction = {
        "id": str(uuid.uuid4()),
        "type": data["type"],
        "amount": float(data["amount"]),
        "currency": data["currency"],
        "category": data["category"],
        "description": data.get("description", "").strip(),
        "date": data["date"],
        "created_at": datetime.now().isoformat(),
    }
    transactions.append(transaction)
    save_transactions(transactions)
    flash(
        f"{'Income' if transaction['type'] == 'income' else 'Expense'} added successfully!",
        "success",
    )
    return redirect(url_for("transactions"))


@app.route("/transactions/delete/<transaction_id>", methods=["POST"])
def delete_transaction(transaction_id):
    transactions = get_transactions()
    transactions = [t for t in transactions if t["id"] != transaction_id]
    save_transactions(transactions)
    flash("Transaction deleted.", "info")
    return redirect(url_for("transactions"))


@app.route("/budgets")
def budgets():
    settings = get_settings()
    base_currency = settings["base_currency"]
    all_budgets = get_budgets()
    transactions = get_transactions()
    now = datetime.now()
    current_month = now.strftime("%Y-%m")

    expense_by_category = defaultdict(float)
    for t in transactions:
        if t["type"] == "expense" and t["date"].startswith(current_month):
            expense_by_category[t["category"]] += convert_amount(
                t["amount"], t["currency"], base_currency
            )

    enriched = []
    for b in all_budgets:
        limit_converted = convert_amount(b["limit"], b["currency"], base_currency)
        spent = expense_by_category.get(b["category"], 0.0)
        remaining = limit_converted - spent
        pct = min((spent / limit_converted * 100) if limit_converted > 0 else 0, 100)
        enriched.append(
            {
                **b,
                "limit_converted": limit_converted,
                "spent": spent,
                "remaining": remaining,
                "pct": round(pct, 1),
                "over": spent > limit_converted,
            }
        )

    return render_template(
        "budgets.html",
        budgets=enriched,
        base_currency=base_currency,
        currencies=CURRENCIES,
        expense_categories=EXPENSE_CATEGORIES,
        format_currency=format_currency,
        current_month=current_month,
    )


@app.route("/budgets/add", methods=["POST"])
def add_budget():
    data = request.form
    budgets = get_budgets()
    category = data["category"]
    existing = next((b for b in budgets if b["category"] == category), None)
    if existing:
        existing["limit"] = float(data["limit"])
        existing["currency"] = data["currency"]
        existing["updated_at"] = datetime.now().isoformat()
        flash(f"Budget for '{category}' updated.", "success")
    else:
        budgets.append(
            {
                "id": str(uuid.uuid4()),
                "category": category,
                "limit": float(data["limit"]),
                "currency": data["currency"],
                "created_at": datetime.now().isoformat(),
            }
        )
        flash(f"Budget for '{category}' created.", "success")
    save_budgets(budgets)
    return redirect(url_for("budgets"))


@app.route("/budgets/delete/<budget_id>", methods=["POST"])
def delete_budget(budget_id):
    budgets = get_budgets()
    budgets = [b for b in budgets if b["id"] != budget_id]
    save_budgets(budgets)
    flash("Budget removed.", "info")
    return redirect(url_for("budgets"))


@app.route("/reports")
def reports():
    settings = get_settings()
    base_currency = settings["base_currency"]
    transactions = get_transactions()
    now = datetime.now()

    monthly_summary = defaultdict(
        lambda: {"income": 0.0, "expenses": 0.0, "categories": defaultdict(float)}
    )
    for t in transactions:
        month = t["date"][:7]
        converted = convert_amount(t["amount"], t["currency"], base_currency)
        if t["type"] == "income":
            monthly_summary[month]["income"] += converted
        else:
            monthly_summary[month]["expenses"] += converted
            monthly_summary[month]["categories"][t["category"]] += converted

    sorted_months = sorted(monthly_summary.keys(), reverse=True)
    report_data = []
    for m in sorted_months[:12]:
        d = monthly_summary[m]
        net = d["income"] - d["expenses"]
        report_data.append(
            {
                "month": datetime.strptime(m, "%Y-%m").strftime("%B %Y"),
                "month_key": m,
                "income": d["income"],
                "expenses": d["expenses"],
                "net": net,
                "top_categories": sorted(
                    d["categories"].items(), key=lambda x: x[1], reverse=True
                )[:3],
            }
        )

    # All-time stats
    all_income = sum(
        convert_amount(t["amount"], t["currency"], base_currency)
        for t in transactions
        if t["type"] == "income"
    )
    all_expenses = sum(
        convert_amount(t["amount"], t["currency"], base_currency)
        for t in transactions
        if t["type"] == "expense"
    )

    all_expense_cats = defaultdict(float)
    for t in transactions:
        if t["type"] == "expense":
            all_expense_cats[t["category"]] += convert_amount(
                t["amount"], t["currency"], base_currency
            )

    cat_chart_labels = json.dumps(
        [
            k
            for k, _ in sorted(
                all_expense_cats.items(), key=lambda x: x[1], reverse=True
            )
        ]
    )
    cat_chart_values = json.dumps(
        [
            round(v, 2)
            for _, v in sorted(
                all_expense_cats.items(), key=lambda x: x[1], reverse=True
            )
        ]
    )

    trend_labels = json.dumps([r["month"] for r in reversed(report_data)])
    trend_income = json.dumps([round(r["income"], 2) for r in reversed(report_data)])
    trend_expenses = json.dumps(
        [round(r["expenses"], 2) for r in reversed(report_data)]
    )
    trend_net = json.dumps([round(r["net"], 2) for r in reversed(report_data)])

    return render_template(
        "reports.html",
        base_currency=base_currency,
        currencies=CURRENCIES,
        report_data=report_data,
        all_income=format_currency(all_income, base_currency),
        all_expenses=format_currency(all_expenses, base_currency),
        all_net=format_currency(all_income - all_expenses, base_currency),
        cat_chart_labels=cat_chart_labels,
        cat_chart_values=cat_chart_values,
        trend_labels=trend_labels,
        trend_income=trend_income,
        trend_expenses=trend_expenses,
        trend_net=trend_net,
        format_currency=format_currency,
    )


@app.route("/settings", methods=["GET", "POST"])
def settings():
    current = get_settings()
    if request.method == "POST":
        current["base_currency"] = request.form["base_currency"]
        save_json(SETTINGS_FILE, current)
        flash("Settings saved.", "success")
        return redirect(url_for("settings"))
    rates = get_rates()
    rates_updated = load_json(RATES_FILE, {}).get("updated_at", "Never")
    return render_template(
        "settings.html",
        settings=current,
        currencies=CURRENCIES,
        rates=rates,
        rates_updated=rates_updated,
    )


@app.route("/api/refresh-rates", methods=["POST"])
def refresh_rates():
    try:
        resp = requests.get("https://api.frankfurter.app/latest?base=USD", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        rates = {**data["rates"], "USD": 1.0}
        save_json(
            RATES_FILE,
            {
                "rates": rates,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M UTC"),
            },
        )
        flash("Exchange rates updated successfully!", "success")
    except Exception as e:
        flash(f"Could not fetch live rates: {e}. Using cached rates.", "warning")
    return redirect(url_for("settings"))


@app.route("/api/convert")
def api_convert():
    try:
        amount = float(request.args.get("amount", 1))
        from_c = request.args.get("from", "USD")
        to_c = request.args.get("to", "EUR")
        result = convert_amount(amount, from_c, to_c)
        return jsonify(
            {
                "amount": amount,
                "from": from_c,
                "to": to_c,
                "result": round(result, 4),
                "formatted": format_currency(result, to_c),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    ensure_data_dir()
    app.run(host="0.0.0.0", port=8080, debug=False)
