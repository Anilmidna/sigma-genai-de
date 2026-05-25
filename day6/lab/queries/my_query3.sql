SELECT customers.name, orders.order_date 
FROM customers, orders;
-- Problem: Without a 'WHERE' or 'ON' clause to link them, this pairs 
-- every single customer with every single order.