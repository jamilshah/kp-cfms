-- =========================================================================
-- KP-CFMS: PostgreSQL Row-Level Security (RLS) Setup
-- =========================================================================
-- Purpose: Add database-level data isolation for multi-tenancy
-- Security Layer: Defense-in-depth (complements Django ORM filtering)
-- 
-- This script enables Row-Level Security on critical tables to prevent
-- accidental data leaks even if Django query filters are bypassed.
-- =========================================================================

-- Enable RLS Extension (if not already enabled)
-- Note: RLS is built into PostgreSQL 9.5+, no extension needed

-- =========================================================================
-- STEP 1: Enable RLS on Critical Tables
-- =========================================================================

-- Finance Module
ALTER TABLE finance_voucher ENABLE ROW LEVEL SECURITY;
ALTER TABLE finance_journalentry ENABLE ROW LEVEL SECURITY;
ALTER TABLE finance_budgethead ENABLE ROW LEVEL SECURITY;
ALTER TABLE finance_accountbalance ENABLE ROW LEVEL SECURITY;

-- Expenditure Module
ALTER TABLE expenditure_bill ENABLE ROW LEVEL SECURITY;
ALTER TABLE expenditure_billline ENABLE ROW LEVEL SECURITY;
ALTER TABLE expenditure_payment ENABLE ROW LEVEL SECURITY;

-- Revenue Module
ALTER TABLE revenue_revenuedemand ENABLE ROW LEVEL SECURITY;
ALTER TABLE revenue_revenuecollection ENABLE ROW LEVEL SECURITY;

-- Budgeting Module
ALTER TABLE budgeting_budgetallocation ENABLE ROW LEVEL SECURITY;
ALTER TABLE budgeting_quarterlyrelease ENABLE ROW LEVEL SECURITY;

-- =========================================================================
-- STEP 2: Create RLS Policies
-- =========================================================================

-- NOTE: These policies use custom session variables set by Django middleware
-- The middleware should execute: SET app.current_org_id = %s;

-- Policy for TMAs: Can only see their own organization's data
-- Policy for LCB/LGD: Can see all data (org_id = 0 or NULL)

-- Finance Tables
CREATE POLICY org_isolation_policy ON finance_voucher
    FOR ALL
    USING (
        organization_id = COALESCE(
            NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
            0
        )
        OR COALESCE(
            NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
            0
        ) = 0  -- LCB/LGD users
    );

CREATE POLICY org_isolation_policy ON finance_journalentry
    FOR ALL
    USING (
        voucher_id IN (
            SELECT id FROM finance_voucher
            WHERE organization_id = COALESCE(
                NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
                0
            )
            OR COALESCE(
                NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
                0
            ) = 0
        )
    );

CREATE POLICY org_isolation_policy ON finance_accountbalance
    FOR ALL
    USING (
        organization_id = COALESCE(
            NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
            0
        )
        OR COALESCE(
            NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
            0
        ) = 0
    );

-- Expenditure Tables
CREATE POLICY org_isolation_policy ON expenditure_bill
    FOR ALL
    USING (
        organization_id = COALESCE(
            NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
            0
        )
        OR COALESCE(
            NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
            0
        ) = 0
    );

CREATE POLICY org_isolation_policy ON expenditure_billline
    FOR ALL
    USING (
        bill_id IN (
            SELECT id FROM expenditure_bill
            WHERE organization_id = COALESCE(
                NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
                0
            )
            OR COALESCE(
                NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
                0
            ) = 0
        )
    );

CREATE POLICY org_isolation_policy ON expenditure_payment
    FOR ALL
    USING (
        organization_id = COALESCE(
            NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
            0
        )
        OR COALESCE(
            NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
            0
        ) = 0
    );

-- Revenue Tables
CREATE POLICY org_isolation_policy ON revenue_revenuedemand
    FOR ALL
    USING (
        organization_id = COALESCE(
            NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
            0
        )
        OR COALESCE(
            NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
            0
        ) = 0
    );

CREATE POLICY org_isolation_policy ON revenue_revenuecollection
    FOR ALL
    USING (
        organization_id = COALESCE(
            NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
            0
        )
        OR COALESCE(
            NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
            0
        ) = 0
    );

-- Budgeting Tables
CREATE POLICY org_isolation_policy ON budgeting_budgetallocation
    FOR ALL
    USING (
        organization_id = COALESCE(
            NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
            0
        )
        OR COALESCE(
            NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
            0
        ) = 0
    );

CREATE POLICY org_isolation_policy ON budgeting_quarterlyrelease
    FOR ALL
    USING (
        organization_id = COALESCE(
            NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
            0
        )
        OR COALESCE(
            NULLIF(current_setting('app.current_org_id', TRUE), '')::integer,
            0
        ) = 0
    );

-- =========================================================================
-- STEP 3: Grant Bypass for Superuser (Optional)
-- =========================================================================
-- This allows Django migrations and admin tasks to work without RLS

-- For the Django database user (replace 'cfms_user' with your actual user)
-- ALTER USER cfms_user BYPASSRLS;

-- =========================================================================
-- VERIFICATION QUERIES
-- =========================================================================

-- Check RLS Status
SELECT schemaname, tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
AND rowsecurity = true
ORDER BY tablename;

-- Check Policies
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual
FROM pg_policies
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY tablename, policyname;

-- =========================================================================
-- DJANGO MIDDLEWARE INTEGRATION
-- =========================================================================
/*
Add to apps/core/middleware.py in TenantMiddleware.process_request():

from django.db import connection

def process_request(self, request):
    if request.user.is_authenticated:
        org_id = request.user.organization_id if request.user.organization else 0
        
        with connection.cursor() as cursor:
            cursor.execute("SET app.current_org_id = %s", [org_id])
    
    return None
*/

-- =========================================================================
-- TESTING
-- =========================================================================
/*
1. Set organization context:
   SET app.current_org_id = 1;

2. Query should only return data for org 1:
   SELECT * FROM finance_voucher;

3. Test LCB/LGD access (all data):
   SET app.current_org_id = 0;
   SELECT * FROM finance_voucher;
*/

-- =========================================================================
-- ROLLBACK (If needed)
-- =========================================================================
/*
-- Disable RLS
ALTER TABLE finance_voucher DISABLE ROW LEVEL SECURITY;
ALTER TABLE finance_journalentry DISABLE ROW LEVEL SECURITY;
-- ... repeat for all tables

-- Drop Policies
DROP POLICY IF EXISTS org_isolation_policy ON finance_voucher;
DROP POLICY IF EXISTS org_isolation_policy ON finance_journalentry;
-- ... repeat for all tables
*/
