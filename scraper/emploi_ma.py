"""
Scraper Emploi.ma -> couche Bronze (PostgreSQL).

Fonctionnement :
  1. Lit les pages liste /recherche-jobs-maroc?page=N et en extrait les cartes d'offres.
  2. Pour chaque offre absente de bronze.offres, ouvre la page détail (critères,
     description, profil recherché).
  3. Insère l'offre brute (JSONB) dans bronze.offres ; l'URL unique empêche les doublons.

Respect du robots.txt : vérification de chaque URL et Crawl-delay (10 s) entre requêtes.

Usage :
  python scraper/emploi_ma.py --max-pages 1      # test (~25 offres, ~5 min)
  python scraper/emploi_ma.py --max-pages 25     # collecte complète
"""
import argparse
import json
import logging
import os
import time
from urllib import robotparser
from urllib.parse import urljoin

import psycopg2
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

BASE_URL = "https://www.emploi.ma"
LIST_PATH = "/recherche-jobs-maroc"
SOURCE = "emploi_ma"
USER_AGENT = "JobScopeMaroc/0.1 (projet étudiant; contact: mostapha.hamdaoui.alaoui@gmail.com)"
MIN_DELAY = 10  # secondes, Crawl-delay du robots.txt

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("emploi_ma")


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------
def clean(text):
    """Supprime les espaces multiples et les espaces en début/fin."""
    return " ".join(text.split()) if text else None


class PoliteSession:
    """Session HTTP qui respecte le robots.txt et attend entre chaque requête."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        # Le robots.txt est téléchargé avec notre propre User-Agent : le lecteur
        # intégré de Python utilise "Python-urllib", que certains sites refusent.
        robots_url = BASE_URL + "/robots.txt"
        response = self.session.get(robots_url, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"robots.txt illisible ({response.status_code}) : collecte annulée par prudence")
        self.robots = robotparser.RobotFileParser(robots_url)
        self.robots.parse(response.text.splitlines())
        self.delay = max(MIN_DELAY, self.robots.crawl_delay(USER_AGENT) or 0)
        self.last_request = 0.0
        log.info("robots.txt chargé, délai entre requêtes : %s s", self.delay)

    def get(self, url):
        if not self.robots.can_fetch(USER_AGENT, url):
            raise PermissionError(f"Interdit par robots.txt : {url}")
        wait = self.delay - (time.time() - self.last_request)
        if wait > 0:
            time.sleep(wait)
        response = self.session.get(url, timeout=30)
        self.last_request = time.time()
        response.raise_for_status()
        return response.text


# ---------------------------------------------------------------------------
# Parsing (fonctions pures, testables sans réseau)
# ---------------------------------------------------------------------------
LIST_FIELDS = {
    "Niveau d´études requis": "niveau_etudes",
    "Niveau d'expérience": "niveau_experience",
    "Contrat proposé": "type_contrat",
    "Région de": "region",
    "Compétences clés": "competences",
}


def parse_list_page(html):
    """Retourne la liste des offres (dict) présentes sur une page liste."""
    soup = BeautifulSoup(html, "lxml")
    offers = []
    for card in soup.select("div.card-job"):
        link = card.select_one("h3 a")
        if not link:
            continue
        offer = {
            "url": urljoin(BASE_URL, link["href"]),
            "titre": clean(link.get_text()),
            "entreprise": clean(card.select_one(".card-job-company").get_text())
            if card.select_one(".card-job-company") else None,
            "date_publication": card.select_one("time")["datetime"]
            if card.select_one("time[datetime]") else None,
            "resume": clean(card.select_one(".card-job-description p").get_text())
            if card.select_one(".card-job-description p") else None,
        }
        for li in card.select("ul li"):
            strong = li.find("strong")
            if not strong:
                continue
            label = clean(li.get_text().replace(strong.get_text(), "")).rstrip(" :").strip()
            key = LIST_FIELDS.get(label)
            if key:
                offer[key] = clean(strong.get_text())
        offers.append(offer)
    return offers


DETAIL_FIELDS = {
    "Métier": "metier",
    "Secteur d´activité": "secteur",
    "Type de contrat": "type_contrat",
    "Région": "region",
    "Ville": "ville",
    "Travail à distance": "teletravail",
    "Niveau d'expérience": "niveau_experience",
    "Niveau d'études": "niveau_etudes",
    "Nombre de poste(s)": "nombre_postes",
    "Management d'équipe": "management",
}


def parse_offer_page(html):
    """Retourne les détails d'une offre à partir de sa page."""
    soup = BeautifulSoup(html, "lxml")
    details = {}

    h1 = soup.find("h1")
    details["titre"] = clean(h1.get_text()) if h1 else None

    company = soup.select_one(".card-block-company a[href*='/recruteur/']")
    details["entreprise"] = clean(company.get_text()) if company else None

    for li in soup.select("ul.arrow-list li"):
        label, value = li.find("strong"), li.find("span")
        if label and value:
            key = DETAIL_FIELDS.get(clean(label.get_text()))
            if key:
                details[key] = clean(value.get_text())

    content = soup.select_one("article.page-application-content")
    if content:
        desc = content.select_one(".job-description")
        qualif = content.select_one(".job-qualifications")
        details["description"] = desc.get_text("\n", strip=True) if desc else None
        details["profil_recherche"] = qualif.get_text("\n", strip=True) if qualif else None
    return details


# ---------------------------------------------------------------------------
# Base de données
# ---------------------------------------------------------------------------
def get_connection():
    load_dotenv()
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5433"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def existing_urls(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT url FROM bronze.offres WHERE source = %s", (SOURCE,))
        return {row[0] for row in cur.fetchall()}


def insert_offer(conn, offer):
    """Insère une offre ; retourne True si elle était nouvelle."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO bronze.offres (source, url, payload)
               VALUES (%s, %s, %s)
               ON CONFLICT (url) DO NOTHING""",
            (SOURCE, offer["url"], json.dumps(offer, ensure_ascii=False)),
        )
        inserted = cur.rowcount == 1
    conn.commit()
    return inserted


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def run(max_pages):
    http = PoliteSession()
    conn = get_connection()
    known = existing_urls(conn)
    log.info("%d offres déjà présentes dans bronze.offres", len(known))

    stats = {"vues": 0, "nouvelles": 0, "deja_connues": 0, "erreurs": 0}
    for page in range(max_pages):
        list_url = f"{BASE_URL}{LIST_PATH}" + (f"?page={page}" if page else "")
        log.info("Page liste %d : %s", page + 1, list_url)
        offers = parse_list_page(http.get(list_url))
        if not offers:
            log.info("Aucune offre trouvée, fin de la pagination.")
            break

        for offer in offers:
            stats["vues"] += 1
            if offer["url"] in known:
                stats["deja_connues"] += 1
                continue
            try:
                details = parse_offer_page(http.get(offer["url"]))
                # Les champs de la page détail complètent ceux de la carte.
                offer.update({k: v for k, v in details.items() if v})
                if insert_offer(conn, offer):
                    stats["nouvelles"] += 1
                    known.add(offer["url"])
                    log.info("  + %s | %s", offer.get("titre"), offer.get("ville"))
            except Exception as exc:  # une offre en échec ne bloque pas les autres
                stats["erreurs"] += 1
                log.warning("  ! Échec pour %s : %s", offer["url"], exc)

    conn.close()
    log.info("Terminé : %s", stats)
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scraper Emploi.ma -> bronze.offres")
    parser.add_argument("--max-pages", type=int, default=1, help="nombre de pages liste à parcourir")
    run(parser.parse_args().max_pages)