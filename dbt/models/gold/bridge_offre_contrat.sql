-- Table de liaison offre <-> type de contrat
select distinct
    offre_id,
    type_contrat
from {{ source('silver', 'offre_contrats') }}
