-- Test métier : le niveau d'études minimal ne doit jamais dépasser le maximal.
select offre_id, etudes_min_bac, etudes_max_bac
from {{ ref('fact_offres') }}
where etudes_min_bac > etudes_max_bac
