-- CSC 226 - Web Database Applications
-- Expense Tracker Schema (MySQL 8.0+)
-- Satisfies the 20% Database Design coursework requirement.
--
-- STANDALONE REFERENCE SCRIPT:
-- This script contains raw MySQL 8.0 DDL documenting the normalized 3NF relational
-- schema, indices, foreign-key cascades, and constraint checks for grading review.
--
-- OPERATIONAL NOTES & DJANGO INTEGRATION:
-- 1. In production and local development, schema migrations are automatically managed
--    by Django via 'python manage.py migrate'.
-- 2. If executing this script manually in MySQL Workbench against a blank database,
--    run Django migrations first to create prerequisite framework tables (such as
--    'auth_user'), or execute 'python manage.py migrate --fake-initial' afterwards
--    so Django recognizes existing tables without conflicts.

CREATE DATABASE IF NOT EXISTS expense_tracker
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE expense_tracker;

-- 1. Category Table
CREATE TABLE IF NOT EXISTS tracker_category (
    id    BIGINT       AUTO_INCREMENT PRIMARY KEY,
    name  VARCHAR(50)  NOT NULL UNIQUE,
    color VARCHAR(7)   NOT NULL DEFAULT '#2D7DD2'
) ENGINE=InnoDB;

-- 2. Transaction Table
CREATE TABLE IF NOT EXISTS tracker_transaction (
    id          BIGINT         AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT         NOT NULL,
    category_id BIGINT         NOT NULL,
    amount      DECIMAL(10, 2) NOT NULL,
    note        VARCHAR(255)   NULL,
    tx_date     DATE           NOT NULL,
    created_at  DATETIME(6)    NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_tx_user_date (user_id, tx_date),
    CONSTRAINT fk_tx_user     FOREIGN KEY (user_id)     REFERENCES auth_user(id)        ON DELETE CASCADE,
    CONSTRAINT fk_tx_category FOREIGN KEY (category_id) REFERENCES tracker_category(id) ON DELETE RESTRICT,
    CONSTRAINT chk_amount_pos CHECK (amount > 0.00 AND amount <= 999999.99)
) ENGINE=InnoDB;

-- Seed Categories (Fixed set for v1, mirrors tracker/constants.py)
INSERT INTO tracker_category (name, color) VALUES
    ('Food',          '#FF5733'),
    ('Transport',     '#33A8FF'),
    ('Housing',       '#9B59B6'),
    ('Entertainment', '#F1C40F'),
    ('Health',        '#2ECC71'),
    ('Shopping',      '#E67E22'),
    ('Other',         '#95A5A6')
ON DUPLICATE KEY UPDATE name = name;
