-- Dimension entreprise
select distinct
    md5(entreprise) as entreprise_key,
    entreprise,
    entreprise = 'CONFIDENTIEL' as est_confidentielle
from {{ source('silver', 'offres') }}
