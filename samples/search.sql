    SELECT 'region' AS table_name,
       region.code AS code,
       region.name AS name,
       '' AS indicator,
       '' AS street,
       '' AS locality_name,
       '' AS admin_area,
       '' AS admin_area_name
  FROM region
 WHERE to_tsvector('english', region.name) @@ to_tsquery('english', :'query')
UNION
SELECT 'admin_area' AS table_name,
       admin_area.code AS code,
       admin_area.name AS name,
       '' AS indicator,
       '' AS street,
       '' AS locality_name,
       admin_area.code AS admin_area,
       admin_area.name AS admin_area_name
  FROM admin_area
 WHERE to_tsvector('english', admin_area.name) @@ to_tsquery('english', :'query')
UNION
SELECT 'district' AS table_name,
       district.code AS code,
       district.name AS name,
       '' AS indicator,
       '' AS street,
       '' AS locality_name,
       admin_area.code AS admin_area,
       admin_area.name AS admin_area_name
  FROM district
       INNER JOIN admin_area
               ON admin_area.code = district.admin_area_code
 WHERE to_tsvector('english', district.name) @@ to_tsquery('english', :'query')
UNION
SELECT 'locality' AS table_name,
       locality.code AS code,
       locality.name AS name,
       '' AS indicator,
       '' AS street,
       '' AS locality_name,
       admin_area.code AS admin_area,
       admin_area.name AS admin_area_name
  FROM locality
       INNER JOIN admin_area
               ON admin_area.code = locality.admin_area_code
       LEFT OUTER JOIN stop_point
                    ON locality.code = stop_point.locality_code
 WHERE to_tsvector('english', locality.name) @@ to_tsquery('english', :'query')
       AND stop_point.atco_code IS NOT NULL
UNION
SELECT 'stop_area' AS table_name,
       stop_area.code AS code,
       stop_area.name AS name,
       '' AS indicator,
       '' AS street,
       locality.name AS locality_name,
       admin_area.code AS admin_area,
       admin_area.name AS admin_area_name
  FROM stop_area
       INNER JOIN locality
               ON locality.code = stop_area.locality_code
       INNER JOIN admin_area
               ON admin_area.code = locality.admin_area_code
 WHERE to_tsvector('english', stop_area.name) @@ to_tsquery('english', :'query')
UNION
SELECT 'stop_point' AS table_name,
       stop_point.atco_code AS code,
       stop_point.common_name AS name,
       stop_point.short_ind AS indicator,
       stop_point.street AS street,
       locality.name AS locality_name,
       admin_area.code AS admin_area,
       admin_area.name AS admin_area_name
  FROM stop_point
       INNER JOIN locality
               ON locality.code = stop_point.locality_code
       INNER JOIN admin_area
               ON admin_area.code = locality.admin_area_code
 WHERE to_tsvector('english', stop_point.common_name || ' ' || stop_point.street)
       @@ to_tsquery('english', :'query')
