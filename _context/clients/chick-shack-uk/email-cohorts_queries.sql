-- Chick Shack email cohorts (OI-83). READ ONLY. Safe to re-run any time.
-- Written 2026-08-16. Sizes the win-back email list before anything is sent.
--
--   scp this file to root@159.65.158.26:/tmp/e.sql, then:
--   docker cp /tmp/e.sql pos-system-postgres-1:/tmp/e.sql
--   docker exec pos-system-postgres-1 sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB -f /tmp/e.sql'
--
-- Predicate is IDENTICAL to discount-analysis_queries.sql (order_visibility.is_real_order()
-- plus rejected/voided removed). Keep it identical or the numbers stop reconciling with OI-82.
-- Emails are lower(trim()) grouped: one human who typed Chris@X once and chris@x later is
-- one recipient, not two.

\pset pager off
\pset border 2
\set cs '''8b2b6223-7db9-443b-8ace-34dd115a9275'''

\echo '=== 1. DO WE ACTUALLY HAVE THE ADDRESSES? ==='
SELECT count(*) AS real_orders,
  count(*) FILTER (WHERE customer_email IS NOT NULL AND btrim(customer_email) <> '') AS orders_with_email,
  count(*) FILTER (WHERE customer_email IS NULL OR btrim(customer_email) = '')       AS orders_without_email,
  count(DISTINCT lower(btrim(customer_email))) FILTER (WHERE customer_email IS NOT NULL AND btrim(customer_email) <> '') AS distinct_emails,
  count(DISTINCT customer_phone) AS distinct_phones
FROM orders
WHERE tenant_id=:cs
  AND (stripe_checkout_session_id IS NULL OR payment_authorized_at IS NOT NULL
       OR accepted_at IS NOT NULL OR rejected_at IS NOT NULL)
  AND rejected_at IS NULL AND status<>'voided';

\echo ''
\echo '=== 2. THE LIST, BY HOW MANY TIMES THEY ORDERED ==='
SELECT CASE WHEN orders=1 THEN 'A. once only'
            WHEN orders=2 THEN 'B. twice'
            ELSE               'C. three or more' END AS cohort,
  count(*) AS people,
  round(100.0*count(*)/sum(count(*)) OVER (),1) AS pct,
  round(avg(spend)/100.0,2) AS avg_lifetime_gbp,
  round(sum(spend)/100.0,2) AS total_gbp
FROM (
  SELECT lower(btrim(customer_email)) AS em, count(*) AS orders, sum(subtotal) AS spend
  FROM orders
  WHERE tenant_id=:cs
    AND (stripe_checkout_session_id IS NULL OR payment_authorized_at IS NOT NULL
         OR accepted_at IS NOT NULL OR rejected_at IS NOT NULL)
    AND rejected_at IS NULL AND status<>'voided'
    AND customer_email IS NOT NULL AND btrim(customer_email) <> ''
  GROUP BY 1
) x GROUP BY cohort ORDER BY cohort;

\echo ''
\echo '=== 3. RECENCY: HOW LONG SINCE EACH PERSON LAST ORDERED ==='
\echo '    This decides who can honestly be told "it has been a while".'
SELECT CASE WHEN days_since <= 6  THEN 'A. 0 to 6 days (active, do NOT win-back)'
            WHEN days_since <= 13 THEN 'B. 7 to 13 days'
            WHEN days_since <= 20 THEN 'C. 14 to 20 days'
            ELSE                       'D. 21+ days (genuinely lapsed)' END AS bucket,
  count(*) AS people,
  count(*) FILTER (WHERE orders=1) AS of_which_one_time_only,
  round(avg(spend)/100.0,2) AS avg_lifetime_gbp
FROM (
  SELECT lower(btrim(customer_email)) AS em, count(*) AS orders, sum(subtotal) AS spend,
    (CURRENT_DATE - max(created_at)::date) AS days_since
  FROM orders
  WHERE tenant_id=:cs
    AND (stripe_checkout_session_id IS NULL OR payment_authorized_at IS NOT NULL
         OR accepted_at IS NOT NULL OR rejected_at IS NOT NULL)
    AND rejected_at IS NULL AND status<>'voided'
    AND customer_email IS NOT NULL AND btrim(customer_email) <> ''
  GROUP BY 1
) x GROUP BY bucket ORDER BY bucket;

\echo ''
\echo '=== 4. THE ACTUAL SEND LIST FOR TEMPLATE 01 (one order, 7+ days ago) ==='
SELECT count(*) AS recipients, round(avg(spend)/100.0,2) AS avg_first_order_gbp,
  min(days_since) AS newest_days, max(days_since) AS oldest_days
FROM (
  SELECT lower(btrim(customer_email)) AS em, count(*) AS orders, sum(subtotal) AS spend,
    (CURRENT_DATE - max(created_at)::date) AS days_since
  FROM orders
  WHERE tenant_id=:cs
    AND (stripe_checkout_session_id IS NULL OR payment_authorized_at IS NOT NULL
         OR accepted_at IS NOT NULL OR rejected_at IS NOT NULL)
    AND rejected_at IS NULL AND status<>'voided'
    AND customer_email IS NOT NULL AND btrim(customer_email) <> ''
  GROUP BY 1
) x WHERE orders=1 AND days_since >= 7;

\echo ''
\echo '=== 5. HYGIENE: anything that would bounce or is obviously not a customer ==='
SELECT count(*) FILTER (WHERE em !~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$') AS malformed,
  count(*) FILTER (WHERE em LIKE '%@example.%' OR em LIKE '%@test.%')                  AS test_looking,
  count(*) AS total_distinct
FROM (
  SELECT DISTINCT lower(btrim(customer_email)) AS em
  FROM orders
  WHERE tenant_id=:cs
    AND (stripe_checkout_session_id IS NULL OR payment_authorized_at IS NOT NULL
         OR accepted_at IS NOT NULL OR rejected_at IS NOT NULL)
    AND rejected_at IS NULL AND status<>'voided'
    AND customer_email IS NOT NULL AND btrim(customer_email) <> ''
) x;

\echo ''
\echo '=== 6. DAILY ORDER SHAPE (for picking a send window that misses the rush) ==='
SELECT extract(hour FROM created_at AT TIME ZONE 'Europe/London')::int AS hour_uk,
  count(*) AS orders
FROM orders
WHERE tenant_id=:cs
  AND (stripe_checkout_session_id IS NULL OR payment_authorized_at IS NOT NULL
       OR accepted_at IS NOT NULL OR rejected_at IS NOT NULL)
  AND rejected_at IS NULL AND status<>'voided'
GROUP BY 1 ORDER BY 1;
