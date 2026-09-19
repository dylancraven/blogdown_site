import json
import urllib.request
import urllib.parse
import time
import re
import html


# --------------------------------------------------
# Configuration
# --------------------------------------------------

ORCID = "0000-0003-3940-833X"
EMAIL = "dylan.craven@aya.yale.edu"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": f"AcademicWebsite/1.0 (mailto:{EMAIL})"
}

PREPRINT_SERVERS = [
    "biorxiv",
    "ecoevorxiv",
]


# --------------------------------------------------
# Helper functions
# --------------------------------------------------

def get_json(url):
    """Download JSON data from a URL."""
    request = urllib.request.Request(url, headers=HEADERS)

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def clean_text(text):
    """Remove HTML/XML tags and decode HTML entities."""
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)

    return text.strip()


# --------------------------------------------------
# 1. Get works from ORCID
# --------------------------------------------------

url = f"https://pub.orcid.org/v3.0/{ORCID}/works"
orcid_data = get_json(url)

publications = []

for group in orcid_data.get("group", []):

    summaries = group.get("work-summary", [])

    if not summaries:
        continue

    work = summaries[0]

    # Skip works classified by ORCID as preprints
    work_type = work.get("type", "")

    if work_type == "preprint":
        continue

    # Title
    title = (
        work.get("title", {})
        .get("title", {})
        .get("value", "")
    )

    title = clean_text(title)

    # Publication year
    year = (
        work.get("publication-date", {})
        .get("year", {})
        .get("value")
    )

    # Journal
    journal = (
        work.get("journal-title", {}) or {}
    ).get("value", "")

    journal = clean_text(journal)

    # Skip known preprint servers
    if any(server in journal.lower() for server in PREPRINT_SERVERS):
        continue

    # DOI
    doi = None

    for ext in work.get("external-ids", {}).get("external-id", []):

        if ext.get("external-id-type", "").lower() == "doi":
            doi = ext.get("external-id-value")
            break

    publication = {
        "title": title,
        "year": year,
        "journal": journal,
        "doi": doi,
        "authors": []
    }

    # --------------------------------------------------
    # 2. Enrich DOI records using Crossref
    # --------------------------------------------------

    if doi:

        try:
            encoded_doi = urllib.parse.quote(doi, safe="")

            crossref_url = (
                f"https://api.crossref.org/works/{encoded_doi}"
                f"?mailto={urllib.parse.quote(EMAIL)}"
            )

            cr = get_json(crossref_url)["message"]

            # Prefer Crossref title when available
            if cr.get("title"):
                publication["title"] = clean_text(
                    cr["title"][0]
                )

            # Prefer Crossref journal when available
            if cr.get("container-title"):
                publication["journal"] = clean_text(
                    cr["container-title"][0]
                )

            # Authors
            authors = []

            for author in cr.get("author", []):

                given = clean_text(author.get("given", ""))
                family = clean_text(author.get("family", ""))

                name = f"{given} {family}".strip()

                if name:
                    authors.append(name)

            publication["authors"] = authors

        except Exception as error:
            print(
                f"Crossref lookup failed for {doi}: {error}"
            )

        # Be polite to the Crossref API
        time.sleep(0.05)

    publications.append(publication)


# --------------------------------------------------
# 3. Sort newest → oldest
# --------------------------------------------------

publications.sort(
    key=lambda p: int(p["year"]) if p["year"] else 0,
    reverse=True
)


# --------------------------------------------------
# 4. Save data for Hugo
# --------------------------------------------------

with open(
    "data/publications.json",
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        publications,
        file,
        ensure_ascii=False,
        indent=2
    )


print(
    f"Saved {len(publications)} publications "
    "to data/publications.json"
)
