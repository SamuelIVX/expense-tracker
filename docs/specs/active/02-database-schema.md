# Spec: Database Schema

## Applicable Skills
- `codebase-design`: Relational normalization (3NF), domain constraints, foreign-key cascade invariants, composite indexing.

## Objective
Establish the relational data model for the expense tracker: provide a raw `schema.sql` script for
execution in MySQL Workbench (satisfying the 20% Database Design coursework requirement) and define
the corresponding Django ORM models (`Category` and `Transaction`) in `tracker/models.py` linking
to Django's built-in `auth_user` table. Seed initial expense categories so transaction recording
can proceed immediately.

## Scope
- Package: `expense-tracker`
- Modifies (creates):
  - `schema.sql` (root-level MySQL DDL with constraints, foreign keys, and seed records for Workbench)
  - `tracker/models.py` (`Category` and `Transaction` models)
  - `tracker/migrations/0001_initial.py` (Django initial migration)
  - `tracker/management/commands/seed_categories.py` (convenience seed command for Django CLI)
- Off-limits: `expense_tracker/settings.py` (owned by `01-project-scaffold`); views and templates (owned by specs 03–07).

## Non-Goals
- No user-editable category administration in v1 (categories are system-seeded).
- No multi-currency support (all transactions stored in USD).
- No receipt file attachments or binary blob storage.

## Invariants
- `Transaction.amount` MUST be stored as `DECIMAL(10, 2)` (MySQL `DECIMAL(10, 2)` / Django `DecimalField`) — floating-point types (`FLOAT`, `DOUBLE`) are strictly forbidden due to binary rounding errors on monetary values. [Currency Invariant]
- `Transaction.user` MUST reference the user primary key with `ON DELETE CASCADE` (`on_delete=models.CASCADE`) — deleting a user must automatically purge all associated financial transactions. [Relational Integrity / GDPR]
- `Transaction.category` MUST reference `Category` with `ON DELETE RESTRICT` (`on_delete=models.PROTECT`) — categories cannot be deleted while transactions are assigned to them. [Referential Integrity]
- `amount` MUST be strictly positive (`CHECK (amount > 0)` in SQL, `MinValueValidator(Decimal('0.01'))` in Django).
- The default seed category list is fixed for v1: Food, Transport, Housing, Entertainment, Health, Shopping, Other.

## Requirements
1. THE SYSTEM SHALL provide `schema.sql` in the project root containing complete DDL for MySQL Workbench to create `categories` and `transactions` tables with primary keys, foreign keys, and column constraints.
2. THE SYSTEM SHALL define a `Category` model in `tracker/models.py` with:
   - `id`: Auto-incrementing primary key
   - `name`: `CharField(max_length=50, unique=True)`
   - `color`: `CharField(max_length=7, default='#2D7DD2')` (HEX color for badges and chart)
3. THE SYSTEM SHALL define a `Transaction` model in `tracker/models.py` with:
   - `id`: Auto-incrementing primary key
   - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')`
   - `category`: `ForeignKey(Category, on_delete=models.PROTECT, related_name='transactions')`
   - `amount`: `DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])`
   - `tx_date`: `DateField()`
   - `note`: `CharField(max_length=255, blank=True, null=True)`
   - `created_at`: `DateTimeField(auto_now_add=True)`
4. WHEN `python manage.py makemigrations` and `python manage.py migrate` are executed, THE SYSTEM SHALL create the corresponding tables in the connected MySQL database without errors.
5. THE SYSTEM SHALL seed the 7 default categories (`Food`, `Transport`, `Housing`, `Entertainment`, `Health`, `Shopping`, `Other`) via both `schema.sql` (for MySQL Workbench) and a data migration or management command (`seed_categories`).

## Failure Modes & Edge Cases
1. **Zero or Negative Amounts:** WHEN a transaction is created with amount ≤ 0, THE SYSTEM SHALL fail validation at both the model validation level (`ValidationError`) and the database constraint level.
2. **Missing Category:** WHEN a transaction is submitted with a non-existent `category_id`, THE SYSTEM SHALL reject the write with a foreign key violation or validation error.
3. **Duplicate Category Names:** WHEN attempting to insert a category with an existing name, THE SYSTEM SHALL reject the write due to the `UNIQUE` constraint.

## Acceptance Criteria
- [ ] `schema.sql` executes in MySQL Workbench without warnings or syntax errors.
- [ ] `python manage.py makemigrations` generates `0001_initial.py`.
- [ ] `python manage.py migrate` applies successfully against local MySQL.
- [ ] Running `Category.objects.count()` in `python manage.py shell` returns 7 after seeding.
- [ ] Inserting a test transaction with `amount = Decimal('-5.00')` raises a `ValidationError`.

## Design

### `schema.sql` (For MySQL Workbench & Course Grading)
```sql
-- CSC 226 - Web Database Applications
-- Expense Tracker Schema (MySQL 8.0+)

CREATE DATABASE IF NOT EXISTS expense_tracker
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE expense_tracker;

-- Drop in reverse foreign-key order
DROP TABLE IF EXISTS tracker_transaction;
DROP TABLE IF EXISTS tracker_category;

CREATE TABLE tracker_category (
    id         INT          AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(50)  NOT NULL UNIQUE,
    color      VARCHAR(7)   NOT NULL DEFAULT '#2D7DD2'
) ENGINE=InnoDB;

CREATE TABLE tracker_transaction (
    id          INT            AUTO_INCREMENT PRIMARY KEY,
    user_id     INT            NOT NULL,
    category_id INT            NOT NULL,
    amount      DECIMAL(10, 2) NOT NULL,
    note        VARCHAR(255)   NULL,
    tx_date     DATE           NOT NULL,
    created_at  DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    CONSTRAINT fk_tx_user     FOREIGN KEY (user_id)     REFERENCES auth_user(id)          ON DELETE CASCADE,
    CONSTRAINT fk_tx_category FOREIGN KEY (category_id) REFERENCES tracker_category(id)   ON DELETE RESTRICT,
    CONSTRAINT chk_amount_pos CHECK (amount > 0.00)
) ENGINE=InnoDB;

-- Index for dashboard and history performance
CREATE INDEX idx_tx_user_date ON tracker_transaction(user_id, tx_date);

-- Seed Categories
INSERT INTO tracker_category (name, color) VALUES
    ('Food',          '#FF5733'),
    ('Transport',     '#33A8FF'),
    ('Housing',       '#9B59B6'),
    ('Entertainment', '#F1C40F'),
    ('Health',        '#2ECC71'),
    ('Shopping',      '#E67E22'),
    ('Other',         '#95A5A6')
ON DUPLICATE KEY UPDATE name=name;
```

### `tracker/models.py`
```python
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(max_length=7, default='#2D7DD2')

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name

class Transaction(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='transactions'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    tx_date = models.DateField()
    note = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-tx_date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'tx_date']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.category.name} - ${self.amount} ({self.tx_date})"
```

## Current State
- `[verified]` Django ORM seamlessly integrates with `django.contrib.auth.models.User` on `auth_user`.
- `[assumed]` MySQL 8.0 `CHECK` constraints are active and enforced by default in InnoDB.

## Tests
- `test_category_uniqueness (R2)` — attempting to insert duplicate category name raises `IntegrityError`.
- `test_transaction_positive_amount (R3)` — amount <= 0 raises `ValidationError`.
- `test_user_cascade_delete (Invariant)` — deleting a user deletes their transactions.

## Constraints
- Dependencies: `01-project-scaffold` must be merged.
- Downstream: `05-add-transaction`, `06-dashboard`, and `07-transaction-history` consume these models.
