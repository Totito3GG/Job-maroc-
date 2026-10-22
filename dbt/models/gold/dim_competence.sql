-- Dimension compétence : une ligne par compétence (clé normalisée sans accents)
select
    md5(competence_cle)         as competence_key,
    competence_cle,
    min(competence)             as competence,
    bool_or(origine = 'texte_offre') as est_technique
from {{ source('silver', 'offre_competences') }}
group by competence_cle
