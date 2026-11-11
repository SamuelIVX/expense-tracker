"""
Constants and static metadata for the tracker application.
"""

from decimal import Decimal

# Default monthly budget benchmark for progress bar visualization
DEFAULT_MONTHLY_BUDGET = Decimal('1000.00')

# Default expense categories for v1 (mirrored in schema.sql for manual DDL setup)
DEFAULT_CATEGORIES = [
    ('Food', '#FF5733'),
    ('Transport', '#33A8FF'),
    ('Housing', '#9B59B6'),
    ('Entertainment', '#F1C40F'),
    ('Health', '#2ECC71'),
    ('Shopping', '#E67E22'),
    ('Other', '#95A5A6'),
]
