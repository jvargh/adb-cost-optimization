SELECT *
FROM system.billing.list_prices
WHERE price_start_time < :end_utc
  AND COALESCE(price_end_time, :end_utc) >= :start_utc
ORDER BY price_start_time, sku_name
