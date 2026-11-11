"""
Raw parameterized SQL queries for tracker analytics and reports.
Satisfies CSC 226 Database Design & Raw Query coursework requirements.

All queries execute via Django's connection.cursor() with strict parameterization
to ensure SQL-injection safety and full 3NF relational index utilization.
"""

from decimal import Decimal, ROUND_HALF_UP
from django.db import connection

CENT = Decimal('0.01')

def _money(value):
    """
    Normalizes raw database numeric values to exact 2-decimal-place currency amounts.
    """
    if value is None:
        return Decimal('0.00')
    if isinstance(value, Decimal):
        return value.quantize(CENT, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)

def get_monthly_spending_summary(user_id, start_date, end_date):
    """
    Executes a raw SQL aggregation query to calculate the user's total spending
    and transaction count within a specific date range.

    Args:
        user_id (int): Primary key of the authenticated User.
        start_date (date|str): Beginning of date window (inclusive).
        end_date (date|str): End of date window (inclusive).

    Returns:
        dict: Keys 'total_spent' (Decimal) and 'tx_count' (int).
    """
    sql = """
        SELECT COALESCE(SUM(amount), 0) AS total_spent,
               COUNT(id) AS tx_count
        FROM tracker_transaction
        WHERE user_id = %s
          AND tx_date >= %s
          AND tx_date <= %s
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [user_id, start_date, end_date])
        row = cursor.fetchone()
        total_val = row[0] if row else 0
        count_val = row[1] if row else 0
        return {
            'total_spent': _money(total_val),
            'tx_count': int(count_val),
        }

def get_monthly_category_breakdown(user_id, start_date, end_date, total_spent=None):
    """
    Executes a raw SQL GROUP BY query to aggregate spending by category for a user
    during a date window, ordered by highest expenditure.

    Args:
        user_id (int): Primary key of the authenticated User.
        start_date (date|str): Beginning of date window (inclusive).
        end_date (date|str): End of date window (inclusive).
        total_spent (Decimal, optional): Total spending across all categories for percentage calculation.

    Returns:
        list[dict]: List of category expenditure dictionaries.
    """
    sql = """
        SELECT c.id,
               c.name,
               c.color,
               COALESCE(SUM(t.amount), 0) AS category_total,
               COUNT(t.id) AS tx_count
        FROM tracker_category c
        INNER JOIN tracker_transaction t ON c.id = t.category_id
        WHERE t.user_id = %s
          AND t.tx_date >= %s
          AND t.tx_date <= %s
        GROUP BY c.id, c.name, c.color
        ORDER BY category_total DESC, c.name ASC
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [user_id, start_date, end_date])
        rows = cursor.fetchall()

    breakdown = []
    # Use caller-supplied monthly total if available; otherwise calculate
    # the sum of returned category amounts as the baseline for percentage shares.
    if total_spent is not None and total_spent > 0:
        total = _money(total_spent)
    else:
        total = sum((_money(r[3]) for r in rows), Decimal('0.00'))

    for row in rows:
        cat_total = _money(row[3])
        pct = float((cat_total / total) * 100) if total > 0 else 0.0
        breakdown.append({
            'category_id': row[0],
            'name': row[1],
            'color': row[2],
            'total': cat_total,
            'tx_count': int(row[4]),
            'percentage': round(pct, 1),
        })

    return breakdown

def get_recent_transactions(user_id, limit=5):
    """
    Executes a raw SQL query retrieving the most recent transactions for a user
    joined with category metadata.

    Args:
        user_id (int): Primary key of the authenticated User.
        limit (int): Maximum number of records to return.

    Returns:
        list[dict]: List of recent transaction dictionaries.
    """
    sql = """
        SELECT t.id,
               t.amount,
               t.tx_date,
               t.note,
               c.name AS category_name,
               c.color AS category_color
        FROM tracker_transaction t
        INNER JOIN tracker_category c ON t.category_id = c.id
        WHERE t.user_id = %s
        ORDER BY t.tx_date DESC, t.id DESC
        LIMIT %s
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [user_id, limit])
        rows = cursor.fetchall()

    recent = []
    for row in rows:
        recent.append({
            'id': row[0],
            'amount': _money(row[1]),
            'tx_date': row[2],
            'note': row[3],
            'category_name': row[4],
            'category_color': row[5],
        })

    return recent

def get_filtered_transactions(user_id, category_id=None, start_date=None, end_date=None, search=None):
    """
    Executes a parameterized raw SQL query retrieving all transactions for a user
    matching optional filter parameters (category, date range, substring search in note).

    Args:
        user_id (int): Primary key of the authenticated User.
        category_id (int|str|None): Optional category ID to filter on.
        start_date (date|str|None): Optional inclusive start date.
        end_date (date|str|None): Optional inclusive end date.
        search (str|None): Optional search string to match within notes.

    Returns:
        list[dict]: List of matching transaction dictionaries ordered by tx_date DESC, id DESC.
    """
    sql = """
        SELECT t.id,
               t.amount,
               t.tx_date,
               t.note,
               c.id AS category_id,
               c.name AS category_name,
               c.color AS category_color
        FROM tracker_transaction t
        INNER JOIN tracker_category c ON t.category_id = c.id
        WHERE t.user_id = %s
    """
    params = [user_id]

    if category_id:
        sql += " AND t.category_id = %s"
        params.append(category_id)

    if start_date:
        sql += " AND t.tx_date >= %s"
        params.append(start_date)

    if end_date:
        sql += " AND t.tx_date <= %s"
        params.append(end_date)

    if search:
        search_term = search.strip()
        if search_term:
            escaped_term = connection.ops.prep_for_like_query(search_term)
            if connection.vendor == 'sqlite':
                sql += r" AND t.note LIKE %s ESCAPE '\'"
            else:
                sql += " AND t.note LIKE %s"
            params.append(f"%{escaped_term}%")

    sql += " ORDER BY t.tx_date DESC, t.id DESC"

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()

    transactions = []
    for row in rows:
        transactions.append({
            'id': row[0],
            'amount': _money(row[1]),
            'tx_date': row[2],
            'note': row[3],
            'category_id': row[4],
            'category_name': row[5],
            'category_color': row[6],
        })

    return transactions
