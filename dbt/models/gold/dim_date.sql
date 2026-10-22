-- Dimension date : un jour par ligne, de la première à la dernière publication
with bornes as (
    select min(date_publication) as debut, max(date_publication) as fin
    from {{ source('silver', 'offres') }}
)
select
    jour::date                          as date_key,
    extract(year from jour)::int        as annee,
    extract(month from jour)::int       as mois,
    extract(week from jour)::int        as semaine,
    extract(isodow from jour)::int      as jour_semaine,
    to_char(jour, 'YYYY-MM')            as annee_mois
from bornes, generate_series(bornes.debut, bornes.fin, interval '1 day') as jour
