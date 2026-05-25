SELECT u.name, u.email, o.order_id
FROM users u, orders o
WHERE u.user_id = o.user_id
AND o.amount > (
    SELECT AVG(amount)
    FROM orders
    WHERE user_id = u.user_id
); 