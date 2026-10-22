-- Table de liaison offre <-> compétence (relation plusieurs-à-plusieurs)
select distinct
    offre_id,
    md5(competence_cle) as competence_key,
    origine
from {{ source('silver', 'offre_competences') }}
