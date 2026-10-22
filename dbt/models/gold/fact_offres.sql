-- Table de faits : une ligne par offre d'emploi
select
    o.offre_id,
    md5(o.entreprise)            as entreprise_key,
    md5(o.ville)                 as ville_key,
    md5(o.secteur)               as secteur_key,
    md5(o.metier)                as metier_key,
    o.date_publication           as date_key,
    o.poste,
    o.contrat_principal,
    o.experience_min_ans,
    o.experience_max_ans,
    o.etudes_min_bac,
    o.etudes_max_bac,
    o.nombre_postes,
    o.teletravail,
    o.management,
    o.est_maroc,
    o.plusieurs_villes,
    o.url,
    o.scraped_at
from {{ source('silver', 'offres') }} as o
