-- Dimension métier (famille de poste)
select distinct
    md5(metier) as metier_key,
    metier
from {{ source('silver', 'offres') }}
where metier is not null
