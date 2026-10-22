-- Dimension secteur d'activité
select distinct
    md5(secteur) as secteur_key,
    secteur
from {{ source('silver', 'offres') }}
where secteur is not null
