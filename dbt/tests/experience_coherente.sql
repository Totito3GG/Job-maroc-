-- Test métier : l'expérience minimale ne doit jamais dépasser l'expérience maximale.
-- Le test échoue s'il retourne au moins une ligne.
select offre_id, experience_min_ans, experience_max_ans
from {{ ref('fact_offres') }}
where experience_max_ans is not null
  and experience_min_ans > experience_max_ans
