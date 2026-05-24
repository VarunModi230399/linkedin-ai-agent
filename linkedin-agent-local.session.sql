SELECT 
    p.id,
    p.status,
    p.pillar,
    c.score_json,
    p.created_at
FROM posts p
LEFT JOIN critiques c ON p.id = c.post_id
ORDER BY p.created_at DESC;