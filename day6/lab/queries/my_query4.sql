SELECT name FROM students LIMIT 5;
-- Problem: Without an 'ORDER BY', the database doesn't guarantee which 5 
-- records you get; the results could change every time you run it.