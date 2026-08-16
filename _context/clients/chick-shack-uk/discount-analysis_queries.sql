-- Chick Shack discount analysis (OI-82). READ ONLY. Safe to re-run any time.
-- Written 2026-08-14. See discount-analysis_2026-08-14.md for the write-up.
--
--   scp this file to root@159.65.158.26:/tmp/q.sql, then:
--   docker cp /tmp/q.sql pos-system-postgres-1:/tmp/q.sql
--   docker exec pos-system-postgres-1 sh -c 'psql -U $POSTGRES_USER -d $POSTGRES_DB -f /tmp/q.sql'
--
-- Gotchas: round(double precision,int) does NOT exist, cast ::numeric (bites on
-- percentile_cont). Modifier price column is price_adjustment, not price.
-- Do NOT try to inline this through ssh + docker exec sh -c, the quoting breaks.

\pset pager off
\pset border 2
\set cs '''8b2b6223-7db9-443b-8ace-34dd115a9275'''

-- The "real order" filter below is order_visibility.is_real_order() expressed in SQL,
-- plus rejected/voided removed. Keep it identical everywhere or the numbers drift.

\echo '=== 1. HEADLINE ==='
SELECT count(*) AS orders, min(created_at)::date AS first_order, max(created_at)::date AS last_order,
  round(sum(subtotal)/100.0,2) AS food_gbp, round(sum(delivery_fee)/100.0,2) AS delivery_gbp,
  round(sum(service_fee)/100.0,2) AS platform_gbp, round(sum(tip)/100.0,2) AS tips_gbp,
  round(avg(subtotal)/100.0,2) AS avg_order,
  round((percentile_cont(0.5)  WITHIN GROUP (ORDER BY subtotal))::numeric/100.0,2) AS median,
  round((percentile_cont(0.75) WITHIN GROUP (ORDER BY subtotal))::numeric/100.0,2) AS p75,
  round((percentile_cont(0.9)  WITHIN GROUP (ORDER BY subtotal))::numeric/100.0,2) AS p90
FROM orders
WHERE tenant_id=:cs
  AND (stripe_checkout_session_id IS NULL OR payment_authorized_at IS NOT NULL
       OR accepted_at IS NOT NULL OR rejected_at IS NOT NULL)
  AND rejected_at IS NULL AND status<>'voided';

\echo ''
\echo '=== 2. BANDS ==='
SELECT band, count(*) AS orders,
  round(100.0*count(*)/sum(count(*)) OVER (),1) AS pct_orders,
  round(sum(subtotal)/100.0,2) AS food_gbp,
  round(100.0*sum(subtotal)/sum(sum(subtotal)) OVER (),1) AS pct_money,
  round(avg(subtotal)/100.0,2) AS avg_in_band
FROM (
  SELECT subtotal,
    CASE WHEN subtotal<2500 THEN 'A. under £25'
         WHEN subtotal<3800 THEN 'B. £25 to £38'
         WHEN subtotal<5000 THEN 'C. £38 to £50'
         ELSE                    'D. £50 and over' END AS band
  FROM orders
  WHERE tenant_id=:cs
    AND (stripe_checkout_session_id IS NULL OR payment_authorized_at IS NOT NULL
         OR accepted_at IS NOT NULL OR rejected_at IS NOT NULL)
    AND rejected_at IS NULL AND status<>'voided'
) x GROUP BY band ORDER BY band;

\echo ''
\echo '=== 3. NUDGE EFFICIENCY BY THRESHOLD (the key table) ==='
\echo '    already_above = pure giveaway.  pool_within_8 = who you can actually move.'
SELECT t.thr AS threshold,
  count(*) FILTER (WHERE o.subtotal >= t.thr*100)                                AS already_above,
  round(0.10*sum(o.subtotal) FILTER (WHERE o.subtotal >= t.thr*100)/100.0,2)     AS cost_10pct,
  count(*) FILTER (WHERE o.subtotal >= (t.thr-5)*100 AND o.subtotal < t.thr*100) AS pool_within_5,
  count(*) FILTER (WHERE o.subtotal >= (t.thr-8)*100 AND o.subtotal < t.thr*100) AS pool_within_8,
  round(count(*) FILTER (WHERE o.subtotal >= (t.thr-8)*100 AND o.subtotal < t.thr*100)::numeric
        / nullif(count(*) FILTER (WHERE o.subtotal >= t.thr*100),0), 2)          AS pool_per_giveaway
FROM orders o
CROSS JOIN (VALUES (20),(22),(25),(28),(30),(32),(35),(40),(45),(50)) AS t(thr)
WHERE o.tenant_id=:cs
  AND (o.stripe_checkout_session_id IS NULL OR o.payment_authorized_at IS NOT NULL
       OR o.accepted_at IS NOT NULL OR o.rejected_at IS NOT NULL)
  AND o.rejected_at IS NULL AND o.status<>'voided'
GROUP BY t.thr ORDER BY t.thr;

\echo ''
\echo '=== 4. COST OF EACH CANDIDATE OFFER ==='
WITH r AS (
  SELECT * FROM orders WHERE tenant_id=:cs
    AND (stripe_checkout_session_id IS NULL OR payment_authorized_at IS NOT NULL
         OR accepted_at IS NOT NULL OR rejected_at IS NOT NULL)
    AND rejected_at IS NULL AND status<>'voided')
SELECT
  round(0.10*sum(subtotal) FILTER (WHERE subtotal>=5000)/100.0,2) AS "10pct_over_50",
  round(0.10*sum(subtotal) FILTER (WHERE subtotal>=4000)/100.0,2) AS "10pct_over_40",
  round(0.10*sum(subtotal) FILTER (WHERE subtotal>=3500)/100.0,2) AS "10pct_over_35",
  round(0.05*sum(subtotal) FILTER (WHERE subtotal>=5000)/100.0,2) AS "5pct_over_50",
  round(sum(delivery_fee) FILTER (WHERE subtotal>=4000 AND service_type='delivery')/100.0,2) AS "free_del_over_40",
  round(sum(least(delivery_fee,450)) FILTER (WHERE subtotal>=3500 AND service_type='delivery')/100.0,2) AS "free_del_over_35_cap450",
  round(3.00*count(*) FILTER (WHERE subtotal>=3500),2) AS "3gbp_off_over_35",
  count(*) FILTER (WHERE subtotal>=3500) AS n_over_35
FROM r \gx

\echo ''
\echo '=== 5. ITEMS PER ORDER (the real opportunity) ==='
SELECT lines, count(*) AS orders, round(100.0*count(*)/sum(count(*)) OVER (),1) AS pct,
  round(avg(subtotal)/100.0,2) AS avg_order
FROM (
  SELECT o.id, o.subtotal, count(oi.id) AS lines
  FROM orders o JOIN order_items oi ON oi.order_id=o.id
  WHERE o.tenant_id=:cs
    AND (o.stripe_checkout_session_id IS NULL OR o.payment_authorized_at IS NOT NULL
         OR o.accepted_at IS NOT NULL OR o.rejected_at IS NOT NULL)
    AND o.rejected_at IS NULL AND o.status<>'voided'
  GROUP BY o.id, o.subtotal
) x GROUP BY lines ORDER BY lines;

\echo ''
\echo '=== 6. ATTACH GAPS BY BAND ==='
WITH t AS (
  SELECT o.id,
    CASE WHEN o.subtotal<2500 THEN 'A. under 25' WHEN o.subtotal<3800 THEN 'B. 25-38'
         WHEN o.subtotal<5000 THEN 'C. 38-50' ELSE 'D. 50+' END AS band,
    bool_or(c.name='Sides') AS side, bool_or(c.name='Drinks') AS drink, bool_or(c.name='Dips') AS dip
  FROM orders o JOIN order_items oi ON oi.order_id=o.id
  LEFT JOIN menu_items mi ON mi.id=oi.menu_item_id
  LEFT JOIN categories c ON c.id=mi.category_id
  WHERE o.tenant_id=:cs
    AND (o.stripe_checkout_session_id IS NULL OR o.payment_authorized_at IS NOT NULL
         OR o.accepted_at IS NOT NULL OR o.rejected_at IS NOT NULL)
    AND o.rejected_at IS NULL AND o.status<>'voided'
  GROUP BY o.id, o.subtotal)
SELECT band, count(*) AS orders,
  count(*) FILTER (WHERE NOT side) AS no_side,
  count(*) FILTER (WHERE NOT drink) AS no_drink,
  count(*) FILTER (WHERE NOT dip) AS no_dip,
  count(*) FILTER (WHERE NOT side AND NOT drink AND NOT dip) AS none_of_three
FROM t GROUP BY band ORDER BY band;

\echo ''
\echo '=== 7. REPEAT BEHAVIOUR ==='
WITH c AS (
  SELECT customer_phone, count(*) n, round(sum(subtotal)/100.0,2) spend
  FROM orders WHERE tenant_id=:cs
    AND (stripe_checkout_session_id IS NULL OR payment_authorized_at IS NOT NULL
         OR accepted_at IS NOT NULL OR rejected_at IS NOT NULL)
    AND rejected_at IS NULL AND status<>'voided' AND customer_phone IS NOT NULL
  GROUP BY 1)
SELECT n AS orders_placed, count(*) AS customers, round(sum(spend),2) AS total_spend,
       round(avg(spend),2) AS avg_lifetime
FROM c GROUP BY n ORDER BY n;

\echo ''
\echo '=== 8. TOP ITEMS ==='
SELECT oi.name, sum(oi.quantity) AS units, round(sum(oi.total)/100.0,2) AS rev,
       count(DISTINCT oi.order_id) AS in_orders
FROM order_items oi JOIN orders o ON o.id=oi.order_id
WHERE o.tenant_id=:cs
  AND (o.stripe_checkout_session_id IS NULL OR o.payment_authorized_at IS NOT NULL
       OR o.accepted_at IS NOT NULL OR o.rejected_at IS NOT NULL)
  AND o.rejected_at IS NULL AND o.status<>'voided'
GROUP BY 1 ORDER BY rev DESC LIMIT 20;

\echo ''
\echo '=== 9. PAID MODIFIER UPSELLS (proof upselling already works here) ==='
SELECT m.name, count(*) AS times, round(sum(m.price_adjustment)/100.0,2) AS rev
FROM order_item_modifiers m
JOIN order_items oi ON oi.id=m.order_item_id
JOIN orders o ON o.id=oi.order_id
WHERE o.tenant_id=:cs
  AND (o.stripe_checkout_session_id IS NULL OR o.payment_authorized_at IS NOT NULL
       OR o.accepted_at IS NOT NULL OR o.rejected_at IS NOT NULL)
  AND o.rejected_at IS NULL AND o.status<>'voided' AND m.price_adjustment>0
GROUP BY 1 ORDER BY rev DESC LIMIT 15;

\echo ''
\echo '=== 10. SANITY: what the real-order filter excluded ==='
SELECT count(*) FILTER (WHERE stripe_checkout_session_id IS NOT NULL AND payment_authorized_at IS NULL
                          AND accepted_at IS NULL AND rejected_at IS NULL) AS abandoned_or_declined,
       count(*) FILTER (WHERE rejected_at IS NOT NULL) AS rejected,
       count(*) FILTER (WHERE status='voided') AS voided,
       count(*) AS all_rows
FROM orders WHERE tenant_id=:cs;
