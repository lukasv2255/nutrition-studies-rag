"""
download_studies.py — Automatické stažení studií

Zdroje (v pořadí priority):
1. Semantic Scholar — nejlepší pokrytí volných PDF
2. PubMed Central — volná PDF z NIH
3. Unpaywall — hledá volná PDF podle DOI
4. Abstrakt — záloha když PDF není dostupné

Použití:
    python download_studies.py
"""

import time
import json
import requests
from pathlib import Path

# ─── Nastavení ────────────────────────────────────────────────────────────────

TOPICS = [
    # Základní výživa
    "nutrition diet health",
    "creatine supplementation",
    "omega-3 fatty acids health",
    "carbohydrates metabolism",
    "vitamin D deficiency",
    "protein intake muscle",
    "magnesium supplementation",
    "gut microbiome diet",
    "intermittent fasting",
    "iron deficiency nutrition",
    "zinc supplementation immunity",
    "vitamin B12 deficiency",
    "fiber diet health",
    "antioxidants nutrition",
    "calcium bone health",
    "weight loss diet intervention",
    "insulin resistance nutrition",
    "cholesterol diet treatment",
    "sleep quality nutrition",
    "inflammation diet",
    "probiotics gut health",
    "caffeine performance",
    "hydration electrolytes sport",
    "vegetarian vegan nutrition",
    "food allergy intolerance",

    # Fitness007
    "gut microbiome dysbiosis restoration",
    "intuitive eating evidence",
    "ultra processed food health effects",
    "histamine intolerance diet",
    "FODMAP diet irritable bowel",
    "antibiotics gut microbiome recovery",
    "athlete mental health performance",
    "sport psychology burnout",
    "stress cortisol nutrition",
    "testosterone nutrition natural",
    "muscle loss aging sarcopenia",
    "sleep deprivation performance recovery",
    "alcohol muscle recovery",
    "fasting autophagy health",
    "insulin sensitivity diet exercise",
    "thyroid nutrition diet",
    "joint health collagen supplementation",
    "breathing techniques performance",
    "cold exposure ice bath recovery",
    "seed oils inflammation health",

    # Institut Moderní Výživy
    "beta-alanine supplementation exercise",
    "citrulline malate performance",
    "carnitine supplementation fat metabolism",
    "BCAA leucine muscle protein synthesis",
    "ketogenic diet weight loss health",
    "glycemic index glycemic load diet",
    "fructose sugar health effects",
    "protein foods satiety weight management",
    "spirulina chlorella health benefits evidence",
    "green foods supplements evidence",
    "lactose intolerance dairy nutrition",
    "food processing health effects",
    "travel nutrition jet lag",
    "nutrition myths evidence based",
    "fat burner supplements weight loss",
    "LDL cholesterol diet intervention",
    "vitamin D3 K2 supplementation",
    "fish omega-3 contamination mercury",
    "creatine loading maintenance protocol",
    "caffeine timing performance dosage",

    # Klinická praxe
    "polycystic ovary syndrome PCOS nutrition",
    "hypothyroidism diet nutrition",
    "non-alcoholic fatty liver disease diet",
    "irritable bowel syndrome diet treatment",
    "acne diet nutrition evidence",
    "hair loss nutrition deficiency",
    "energy levels fatigue nutrition",
    "brain fog cognitive function nutrition",
    "menopause nutrition hormones",
    "testosterone low diet lifestyle",
    "estrogen dominance nutrition",
    "adrenal fatigue cortisol nutrition",

    # Diety a přístupy
    "mediterranean diet health outcomes",
    "low carb diet metabolic health",
    "plant based diet health risks benefits",
    "carnivore diet evidence",
    "paleo diet health evidence",
    "caloric restriction longevity",
    "meal timing chrononutrition",
    "breakfast skipping health effects",

    # Sport a výkon
    "pre workout nutrition timing",
    "post workout recovery nutrition",
    "endurance sport nutrition carbohydrates",
    "strength training nutrition requirements",
    "female athlete nutrition",
    "overtraining syndrome nutrition recovery",
    "VO2 max nutrition improvement",

    # Specifické potraviny a látky
    "gluten sensitivity non celiac",
    "dairy milk health effects",
    "red meat health cardiovascular",
    "eggs cholesterol cardiovascular",
    "coffee health effects",
    "alcohol moderate consumption health",
    "artificial sweeteners health effects",
    "whey protein vs plant protein",
    "collagen peptides skin joints",
    "ashwagandha stress cortisol",
    "berberine blood sugar",
    "NAD NMN longevity supplementation",
]

STUDIES_PER_TOPIC = 10
MAX_TOTAL = 1000
STUDIES_DIR = Path("studies")
ABSTRACTS_DIR = STUDIES_DIR / "abstracts"
PROGRESS_FILE = Path("download_progress.json")

S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
PMC_PDF = "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/"
UNPAYWALL = "https://api.unpaywall.org/v2/{doi}?email=nutrition.rag@example.com"
PUBMED_FETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
HEADERS = {"User-Agent": "NutritionRAG/1.0 (research tool)"}

# ─── Progress ─────────────────────────────────────────────────────────────────

def load_progress():
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"downloaded": [], "abstracts": [], "failed": []}

def save_progress(p):
    PROGRESS_FILE.write_text(json.dumps(p, indent=2, ensure_ascii=False))

def already_have(filename, p):
    return filename in p["downloaded"] or filename in p["abstracts"]

def safe_filename(text):
    keep = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    return "".join(c if c in keep else "_" for c in text)[:80]

# ─── Semantic Scholar ──────────────────────────────────────────────────────────

def search_s2(query, limit, only_open=False):
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,year,externalIds,openAccessPdf,abstract",
    }
    if only_open:
        params["openAccessPdf"] = ""
    try:
        r = requests.get(S2_SEARCH, params=params, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        results = []
        for p in r.json().get("data", []):
            pdf_url = None
            if p.get("openAccessPdf"):
                pdf_url = p["openAccessPdf"].get("url")
            ids = p.get("externalIds") or {}
            results.append({
                "title": p.get("title", ""),
                "year": str(p.get("year") or "0000"),
                "doi": ids.get("DOI", ""),
                "pmc": ids.get("PubMedCentral", ""),
                "pmid": ids.get("PubMed", ""),
                "pdf_url": pdf_url,
                "abstract": p.get("abstract") or "",
            })
        return results
    except Exception as e:
        print(f"    S2 chyba: {e}")
        return []

# ─── Stahování PDF ────────────────────────────────────────────────────────────

def download_pdf(url, filepath):
    if not url:
        return False
    try:
        r = requests.get(url, timeout=25, allow_redirects=True, headers=HEADERS)
        if r.status_code == 200 and b"%PDF" in r.content[:10]:
            filepath.write_bytes(r.content)
            return True
    except:
        pass
    return False

def try_pmc(pmc_id, filepath):
    if not pmc_id:
        return False
    return download_pdf(PMC_PDF.format(pmc_id=pmc_id), filepath)

def try_unpaywall(doi, filepath):
    if not doi:
        return False
    try:
        r = requests.get(UNPAYWALL.format(doi=doi), timeout=10, headers=HEADERS)
        if r.status_code != 200:
            return False
        data = r.json()
        pdf_url = None
        best = data.get("best_oa_location") or {}
        if best.get("url_for_pdf"):
            pdf_url = best["url_for_pdf"]
        if not pdf_url:
            for loc in data.get("oa_locations", []):
                if loc.get("url_for_pdf"):
                    pdf_url = loc["url_for_pdf"]
                    break
        return download_pdf(pdf_url, filepath) if pdf_url else False
    except:
        return False

def fetch_pubmed_abstract(pmid):
    if not pmid:
        return ""
    try:
        r = requests.get(PUBMED_FETCH, params={
            "db": "pubmed", "id": pmid,
            "retmode": "text", "rettype": "abstract"
        }, timeout=15)
        return r.text.strip()
    except:
        return ""

# ─── Zpracování studie ────────────────────────────────────────────────────────

def process_paper(paper, progress):
    if not paper["title"]:
        return "fail"

    base = f"{paper['year']}_{safe_filename(paper['title'])}"
    pdf_name = f"{base}.pdf"
    txt_name = f"{base}.txt"

    if already_have(pdf_name, progress) or already_have(txt_name, progress):
        return "skip"

    pdf_path = STUDIES_DIR / pdf_name

    # 1. Přímý odkaz ze Semantic Scholar
    if download_pdf(paper.get("pdf_url"), pdf_path):
        progress["downloaded"].append(pdf_name)
        return "pdf"
    time.sleep(0.3)

    # 2. PubMed Central
    if try_pmc(paper["pmc"], pdf_path):
        progress["downloaded"].append(pdf_name)
        return "pdf"
    time.sleep(0.3)

    # 3. Unpaywall
    if try_unpaywall(paper["doi"], pdf_path):
        progress["downloaded"].append(pdf_name)
        return "pdf"

    # 4. Abstrakt jako záloha
    abstract = paper.get("abstract", "")
    if not abstract and paper.get("pmid"):
        abstract = fetch_pubmed_abstract(paper["pmid"])

    if abstract and len(abstract) > 100:
        txt_path = ABSTRACTS_DIR / txt_name
        txt_path.write_text(
            f"Title: {paper['title']}\nYear: {paper['year']}\nDOI: {paper['doi']}\n\nABSTRACT:\n{abstract}\n",
            encoding="utf-8"
        )
        progress["abstracts"].append(txt_name)
        return "abstract"

    progress["failed"].append(paper["title"][:40])
    return "fail"

# ─── Hlavní smyčka ────────────────────────────────────────────────────────────

def main():
    STUDIES_DIR.mkdir(exist_ok=True)
    ABSTRACTS_DIR.mkdir(exist_ok=True)

    progress = load_progress()
    total = len(progress["downloaded"]) + len(progress["abstracts"])

    print("Nutriční databáze — stahování studií")
    print(f"Aktuálně: {len(progress['downloaded'])} PDF, {len(progress['abstracts'])} abstraktů")
    print(f"Cíl: {MAX_TOTAL} studií\n")

    if total >= MAX_TOTAL:
        print("Databáze je plná.")
        return

    for topic in TOPICS:
        if total >= MAX_TOTAL:
            break

        print(f"── {topic}")

        # Nejdřív zkus pouze open access
        papers = search_s2(topic, STUDIES_PER_TOPIC, only_open=True)
        time.sleep(1)

        # Pokud málo výsledků, přidej i ostatní (abstrakty)
        if len(papers) < STUDIES_PER_TOPIC // 2:
            papers = search_s2(topic, STUDIES_PER_TOPIC, only_open=False)
            time.sleep(1)

        if not papers:
            print("   Žádné výsledky.\n")
            continue

        pdfs = abstracts = 0
        for paper in papers:
            if total >= MAX_TOTAL:
                break
            result = process_paper(paper, progress)
            if result == "pdf":
                print(f"   ✓ PDF:      {paper['year']}  {paper['title'][:65]}")
                pdfs += 1; total += 1
            elif result == "abstract":
                print(f"   ~ Abstrakt: {paper['year']}  {paper['title'][:65]}")
                abstracts += 1; total += 1
            elif result == "skip":
                print(f"   ↷ Přeskakuji")
            save_progress(progress)
            time.sleep(0.4)

        print(f"   → {pdfs} PDF, {abstracts} abstraktů (celkem: {total})\n")

    save_progress(progress)
    print("─" * 60)
    print(f"Hotovo! PDF: {len(progress['downloaded'])}, Abstrakty: {len(progress['abstracts'])}")
    print("Další krok: python ingest.py")

if __name__ == "__main__":
    main()