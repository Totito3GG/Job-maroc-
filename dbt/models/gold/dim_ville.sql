-- Dimension ville : une ligne par ville normalisée
select distinct
    md5(ville)  as ville_key,
    ville,
    est_maroc
from {{ source('silver', 'offres') }}
where ville is not null
