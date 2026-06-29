# -*- coding: utf-8 -*-
"""
============================================================================
 GESTIONNAIRE STRATÉGIQUE DE SINISTRES — Plateforme de chiffrage BTP
============================================================================
Réécriture complète (architecture senior) :
    • Workflow 3 étapes piloté par st.session_state (aucune perte à chaque rerun)
    • Extraction PDF robuste (libellés sur 2 colonnes + tableaux + synonymes)
    • Persistance disque par identifiant d'URL (?sid) → survit refresh / retour
    • Génération PDF blindée (try/except, jamais de crash silencieux)
    • UI moderne et animée, cartes natives st.container(border=True)
============================================================================
"""

import io
import re
import json
import gzip
import base64
import datetime
import unicodedata
import traceback

import streamlit as st
import streamlit.components.v1 as components

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib import colors

try:
    import pdfplumber
    PDFPLUMBER_OK = True
except Exception:
    PDFPLUMBER_OK = False


# ============================================================================
# 1. CONFIGURATION & CHARTE GRAPHIQUE
# ============================================================================
st.set_page_config(
    page_title="Gestionnaire Stratégique de Sinistres",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Palette « premium »
NAVY = "#0F2A4A"
INK = "#0F1B2D"
MUTED = "#5B6B7B"
ACCENT = "#4F46E5"      # indigo
ACCENT2 = "#06B6D4"     # cyan
VIOLET = "#7C3AED"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
DANGER = "#EF4444"
SURFACE = "#FFFFFF"
BG = "#EEF2F9"

# Variables CSS (petit f-string) — le gros bloc CSS reste un string brut pour
# éviter tout échappement d'accolades.
_ROOT_VARS = f""":root {{
    --navy:{NAVY}; --ink:{INK}; --muted:{MUTED};
    --accent:{ACCENT}; --accent2:{ACCENT2}; --violet:{VIOLET};
    --success:{SUCCESS}; --warning:{WARNING}; --danger:{DANGER};
    --surface:{SURFACE}; --bg:{BG};
}}"""

_MAIN_CSS = """
/* ====================== BASE ====================== */
.stApp {
    background:
        radial-gradient(1100px 600px at 110% -8%, rgba(79,70,229,.12), transparent 60%),
        radial-gradient(900px 520px at -10% 8%, rgba(6,182,212,.10), transparent 55%),
        var(--bg) !important;
}
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1.6rem; padding-bottom: 5rem; max-width: 1180px; }

/* ====================== TYPO ====================== */
.stApp, .stApp p, .stApp li, .stApp label, .stApp span,
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li,
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label {
    color: var(--ink) !important;
}
[data-testid="stCaptionContainer"], small { color: var(--muted) !important; }
h1, h2, h3, h4, h5, h6 { color: var(--navy) !important; letter-spacing:.2px; }

/* ====================== CHAMPS ====================== */
.stTextInput input, .stNumberInput input,
.stSelectbox div[data-baseweb="select"] > div, textarea {
    background:#FFFFFF !important; color:var(--ink) !important;
    border-radius:11px !important; border:1px solid #D7DEE8 !important;
    transition:border-color .15s ease, box-shadow .15s ease;
}
.stTextInput input:focus, .stNumberInput input:focus {
    border-color:var(--accent) !important; box-shadow:0 0 0 3px rgba(79,70,229,.16) !important;
}
input::placeholder, textarea::placeholder { color:#9AA7B4 !important; opacity:1; font-style:italic; }
[data-baseweb="popover"], [data-baseweb="menu"], ul[role="listbox"] { background:#FFFFFF !important; }
li[role="option"], [data-baseweb="menu"] * { color:var(--ink) !important; }
li[role="option"]:hover { background:#EEF0FF !important; }
[data-testid="stDataFrame"] * { color:var(--ink) !important; }

/* ====================== ANIMATIONS ====================== */
@keyframes shift { 0%{background-position:0% 50%} 50%{background-position:100% 50%} 100%{background-position:0% 50%} }
@keyframes fadeInUp { from{opacity:0; transform:translateY(12px)} to{opacity:1; transform:none} }
@keyframes pulse { 0%{box-shadow:0 0 0 0 rgba(6,182,212,.55)} 70%{box-shadow:0 0 0 10px rgba(6,182,212,0)} 100%{box-shadow:0 0 0 0 rgba(6,182,212,0)} }
@keyframes floaty { 0%{transform:translateY(0)} 50%{transform:translateY(-14px)} 100%{transform:translateY(0)} }
@keyframes shimmer { 0%{background-position:-200% 0} 100%{background-position:200% 0} }

/* ====================== HERO ====================== */
.hero { position:relative; overflow:hidden; border-radius:22px; padding:30px 34px;
    margin-bottom:16px; color:#fff;
    background:linear-gradient(120deg, #0B1F38, #15356b, #4F46E5, #15356b, #0B1F38);
    background-size:300% 300%; animation:shift 16s ease infinite;
    box-shadow:0 22px 60px rgba(15,42,74,.38); border:1px solid rgba(255,255,255,.10); }
.hero::after { content:""; position:absolute; inset:0; pointer-events:none;
    background-image:linear-gradient(rgba(255,255,255,.06) 1px, transparent 1px),
                     linear-gradient(90deg, rgba(255,255,255,.06) 1px, transparent 1px);
    background-size:30px 30px; mask:radial-gradient(60% 120% at 82% 0%, #000, transparent 70%); }
.hero .orb { position:absolute; border-radius:50%; filter:blur(8px); opacity:.55; animation:floaty 7s ease-in-out infinite; }
.hero .orb.a { width:120px; height:120px; right:60px; top:-30px; background:rgba(6,182,212,.45); }
.hero .orb.b { width:80px; height:80px; right:180px; bottom:-20px; background:rgba(124,58,237,.45); animation-delay:1.5s; }
.hero h1 { color:#fff !important; margin:0; font-size:1.65rem; position:relative; z-index:1; }
.hero p { color:#C7D6EC !important; margin:.45rem 0 0 0; font-size:.95rem; position:relative; z-index:1; }
.hero .live { position:relative; z-index:1; display:inline-flex; align-items:center; gap:8px;
    margin-bottom:10px; padding:5px 13px; border-radius:999px; font-size:.72rem; font-weight:700;
    letter-spacing:.6px; color:#E0F2FE !important; background:rgba(255,255,255,.10);
    border:1px solid rgba(255,255,255,.20); }
.hero .dot { width:8px; height:8px; border-radius:50%; background:var(--accent2); animation:pulse 1.8s infinite; }

/* ====================== STEPPER ====================== */
.tech-progress { height:7px; border-radius:999px; background:#DCE3EC; overflow:hidden; margin:4px 2px 16px; }
.tech-progress > span { display:block; height:100%; border-radius:999px;
    background:linear-gradient(90deg, var(--accent2), var(--accent), var(--violet));
    background-size:200% 100%; animation:shimmer 2.4s linear infinite;
    transition:width .6s cubic-bezier(.4,0,.2,1); }
.crumbs { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:10px; }
.crumb { flex:1; min-width:150px; background:rgba(255,255,255,.78); backdrop-filter:blur(8px);
    border:1px solid #E2E8F0; border-radius:14px; padding:11px 14px;
    box-shadow:0 2px 10px rgba(0,0,0,.04); transition:transform .2s ease, box-shadow .2s ease; }
.crumb:hover { transform:translateY(-2px); box-shadow:0 10px 24px rgba(15,27,45,.10); }
.crumb .n { display:inline-flex; align-items:center; justify-content:center; width:25px; height:25px;
    border-radius:50%; background:#E2E8F0; color:var(--muted) !important; font-weight:800;
    font-size:.8rem; margin-right:9px; transition:all .25s ease; }
.crumb .t { color:var(--muted) !important; font-weight:700; font-size:.86rem; }
.crumb.active { border-color:transparent; background:linear-gradient(120deg, var(--navy), var(--accent)); }
.crumb.active .n { background:#fff; color:var(--accent) !important; }
.crumb.active .t { color:#fff !important; }
.crumb.done .n { background:var(--success); color:#fff !important; }

/* ====================== KPI ====================== */
.kpi { position:relative; background:var(--surface); border:1px solid #E6EBF2; border-radius:16px;
    padding:18px; height:100%; overflow:hidden; box-shadow:0 6px 22px rgba(15,27,45,.06);
    animation:fadeInUp .45s ease both; transition:transform .2s ease, box-shadow .2s ease; }
.kpi::before { content:""; position:absolute; top:0; left:0; right:0; height:4px;
    background:var(--kpi-accent, linear-gradient(90deg, var(--accent2), var(--accent))); }
.kpi:hover { transform:translateY(-4px); box-shadow:0 18px 36px rgba(15,27,45,.13); }
.kpi .label { color:var(--muted) !important; font-size:.72rem; text-transform:uppercase; letter-spacing:.7px; font-weight:800; }
.kpi .value { color:var(--navy) !important; font-size:1.55rem; font-weight:800; margin-top:6px; font-feature-settings:"tnum"; }
.kpi .sub { color:#94A3B8 !important; font-size:.8rem; margin-top:3px; }

/* ====================== STATUT ====================== */
.status-box { border-radius:14px; padding:16px 20px; margin:6px 0 14px; animation:fadeInUp .4s ease both; }
.status-box h4 { margin:0 0 4px; font-size:1.05rem; }
.status-box p { margin:0; color:#334155 !important; }

/* ====================== CHECKLIST ====================== */
.check { display:flex; align-items:center; gap:10px; padding:7px 12px; border-radius:10px;
    margin-bottom:6px; font-size:.9rem; font-weight:600; }
.check.ok { background:rgba(16,185,129,.10); color:#0F766E !important; }
.check.ko { background:rgba(239,68,68,.10); color:#B91C1C !important; }
.check .ic { font-size:1rem; }

.col-head { color:var(--muted) !important; font-size:.72rem; text-transform:uppercase; letter-spacing:.5px; font-weight:800; }

/* ====================== BOUTONS ====================== */
.stButton > button, .stDownloadButton > button { border-radius:12px; font-weight:700;
    border:1px solid #CBD5E0; color:var(--ink); background:#FFFFFF; transition:all .18s ease; }
.stButton > button:hover, .stDownloadButton > button:hover { transform:translateY(-2px);
    box-shadow:0 10px 22px rgba(79,70,229,.18); border-color:var(--accent); color:var(--navy); }
.stButton > button[kind="primary"], .stDownloadButton > button {
    background:linear-gradient(120deg, var(--accent), var(--navy)) !important; color:#fff !important;
    border:none !important; box-shadow:0 8px 20px rgba(79,70,229,.30) !important; }
.stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover {
    box-shadow:0 12px 30px rgba(79,70,229,.45) !important; color:#fff !important; }
.stButton > button[kind="primary"]:disabled { opacity:.45; box-shadow:none !important; }

/* ====================== CARTES / CONTENEURS ====================== */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background:#FFFFFF; border-radius:16px !important; box-shadow:0 6px 22px rgba(15,27,45,.05);
    animation:fadeInUp .4s ease both; }
div[data-testid="stExpander"] { border-radius:14px; border:1px solid #E6EBF2; background:#FFFFFF;
    box-shadow:0 4px 16px rgba(15,27,45,.04); transition:box-shadow .2s ease; }
div[data-testid="stExpander"]:hover { box-shadow:0 10px 26px rgba(15,27,45,.08); }
div[data-testid="stExpander"] summary p { color:var(--navy) !important; font-weight:700; }
div[data-testid="stAlert"] p { color:var(--ink) !important; }
hr { border-color:#E2E8F0 !important; }

/* ====================== SIDEBAR ====================== */
section[data-testid="stSidebar"] > div {
    background:linear-gradient(180deg, #0B1F38 0%, var(--navy) 100%) !important;
    border-right:1px solid rgba(255,255,255,.06); }
section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span, section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color:#E2E8F0 !important; }
section[data-testid="stSidebar"] h3 { color:#FFFFFF !important; }
section[data-testid="stSidebar"] [data-testid="stMetricValue"] { color:#FFFFFF !important; }
section[data-testid="stSidebar"] [data-testid="stMetricLabel"] * { color:#9FB3CC !important; }
section[data-testid="stSidebar"] [data-testid="stMetricDelta"] * { color:var(--accent2) !important; }
"""

st.markdown(f"<style>{_ROOT_VARS}{_MAIN_CSS}</style>", unsafe_allow_html=True)


# ============================================================================
# 2. CONSTANTES MÉTIER
# ============================================================================
CORPS_METIER = [
    ("🏠 Toiture / Couverture", "Toiture"),
    ("🚿 Plomberie", "Plomberie"),
    ("⚡ Électricité", "Electricite"),
    ("🧱 Maçonnerie / Gros œuvre", "Maconnerie"),
    ("🪟 Menuiserie", "Menuiserie"),
    ("🎨 Plâtrerie / Peinture", "Platrerie"),
    ("🟫 Revêtement de sol", "Sol"),
    ("👷 Main d'œuvre", "MainOeuvre"),
]
UNITES = ["m²", "ml", "u", "h", "forfait", "kg", "L"]
ZONES = {"Zone A  (×1,00)": 1.00, "Zone B  (×1,15)": 1.15, "Zone C  (×1,25)": 1.25}
TVA_RATE = 0.10

PLACEHOLDERS = {
    "company_name": "SMARTSITE RÉFECTION SAS",
    "company_address": "75 Avenue des Champs-Élysées, 75008 Paris",
    "company_siret": "12345678901234",
    "company_tva": "FR12123456789",
    "client_name": "Société Immobilière Horizon",
    "address": "14 Avenue de la République, 75011 Paris",
    "insurance_name": "Allianz France",
    "claim_number": "ALZ-2026-9941X",
    "expert_name": "Cabinet Texa Évolution",
    "expert_ref": "EXP-55214-REV",
}


# ============================================================================
# 3. UTILITAIRES
# ============================================================================
def format_currency(value):
    """Format français : 1 234,56 €. Tolère None / chaînes."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + " €"


def validate_siret(siret):
    return len(re.sub(r"\D", "", str(siret))) == 14


def _parse_amount(raw):
    """'7 500,00' / '7.500,00' / '7500.00' → float ; None si invalide."""
    s = re.sub(r"[^\d,.\s]", "", str(raw)).strip().replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


# ============================================================================
# 4. MOTEUR D'EXTRACTION PDF
# ============================================================================
def _norm_label(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    return re.sub(r"\s+", " ", s)


FIELD_SYNONYMS = {
    "claim_number": ["n de sinistre", "no de sinistre", "numero de sinistre", "n sinistre",
                     "reference du sinistre", "reference sinistre", "ref sinistre", "sinistre",
                     "n de dossier", "numero de dossier", "reference dossier", "ref dossier", "dossier"],
    "expert_ref": ["numero d expert", "n d expert", "no d expert", "numero expert",
                   "reference du rapport", "reference rapport", "ref rapport", "n de rapport",
                   "numero de rapport", "reference expert", "ref expert", "reference de l expertise"],
    "expert_name": ["cabinet d expertise", "cabinet d expert", "cabinet", "expert missionne",
                    "nom de l expert", "expertise par", "expertise realisee par", "expert assure", "expert"],
    "insurance_name": ["compagnie d assurance", "compagnie", "assureur", "nom de l assureur", "assurance"],
    "client_name": ["nom et prenom", "nom prenom", "nom de l assure", "assure", "assuree",
                    "client", "beneficiaire", "souscripteur"],
    "address": ["adresse du chantier", "adresse du bien", "adresse du sinistre", "adresse des travaux",
                "lieu du sinistre", "lieu des travaux", "adresse", "lieu"],
    "expert_ht": ["montant total ht", "total general ht", "total ht", "montant ht",
                  "estimation ht", "evaluation ht", "plafond ht", "cout ht", "montant des travaux ht"],
}


def _match_field(label_norm):
    for field, syns in FIELD_SYNONYMS.items():
        for syn in syns:
            if label_norm == syn or label_norm.startswith(syn + " "):
                return field
    return None


def _clean_client(value):
    """Retire les civilités de tête (Monsieur/Madame…) sans rogner un prénom."""
    return re.sub(r"^(?:(?:monsieur|madame|mademoiselle|mlle|mme|mr)[\s./]+)+",
                  "", value, flags=re.IGNORECASE).strip()


def extract_data_from_pdf(pdf_file):
    """
    Extraction fiable : paires (libellé, valeur) issues de
      1) lignes « Libellé : valeur » (valeur éventuellement sur la ligne suivante)
      2) tableaux du PDF
    puis association via synonymes normalisés. Retourne les champs sûrs.
    """
    found = {}
    if not PDFPLUMBER_OK:
        return found

    full_text = ""
    table_pairs = []
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                full_text += (page.extract_text() or "") + "\n"
                for table in (page.extract_tables() or []):
                    for row in table:
                        cells = [str(c).strip() for c in row if c and str(c).strip()]
                        if len(cells) >= 2:
                            table_pairs.append((cells[0], cells[1]))
    except Exception as exc:
        st.warning(f"Lecture du PDF partielle : {exc}")

    full_text = full_text.replace("\xa0", " ")
    lines = [ln.strip() for ln in full_text.splitlines()]
    n = len(lines)

    def next_value(i):
        j = i + 1
        while j < n:
            cand = lines[j].strip()
            if cand and not cand.endswith(":"):
                return cand
            j += 1
        return ""

    pairs = []
    for i, line in enumerate(lines):
        if ":" not in line:
            continue
        label, _, value = line.partition(":")
        value = value.strip()
        if not value:
            value = next_value(i)
        pairs.append((label, value))
    pairs.extend(table_pairs)

    for raw_label, raw_value in pairs:
        field = _match_field(_norm_label(raw_label))
        if not field or field in found:
            continue
        value = str(raw_value).replace("\xa0", " ").strip()
        if not value:
            continue
        if field == "expert_ht":
            amount = _parse_amount(value)
            if amount and amount > 0:
                found[field] = amount
        elif field in ("claim_number", "expert_ref"):
            m = re.search(r"[A-Za-z0-9][A-Za-z0-9\-/]{3,20}", value)
            if m:
                found[field] = m.group(0)
        elif field == "client_name":
            found[field] = _clean_client(re.split(r"\s{2,}", value)[0])[:60]
        else:
            found[field] = re.split(r"\s{2,}", value)[0].strip()[:60]

    if "expert_ht" not in found:
        m = re.search(r"(?:total|montant|estimation|plafond)[^\n]{0,30}?HT[\s:]*"
                      r"([\d][\d\s.]*[.,]\d{2})", full_text, re.IGNORECASE)
        if m:
            amount = _parse_amount(m.group(1))
            if amount and amount > 0:
                found["expert_ht"] = amount

    if "claim_number" not in found:
        m = re.search(r"sinistre[\s:n°o]*([A-Z]{2,}[0-9][A-Z0-9\-/]{3,18})", full_text, re.IGNORECASE)
        if m:
            found["claim_number"] = m.group(1)

    if "insurance_name" not in found:
        m = re.search(r"([A-ZÉÈÀÂÎÔÛÇ][A-ZÉÈÀÂÎÔÛÇ'’\- ]{2,40}ASSURANCES?[A-ZÉÈÀÂÎÔÛÇ'’\- ]{0,40}"
                      r"|ASSURANCES?[A-ZÉÈÀÂÎÔÛÇ'’\- ]{2,40})", full_text)
        if m:
            found["insurance_name"] = re.sub(r"\s+", " ", m.group(1)).strip()[:60]

    return found


# ============================================================================
# 5. ÉTAT DE SESSION
# ============================================================================
for _k in PLACEHOLDERS:
    st.session_state.setdefault(_k, "")
for _k, _v in {"zone_select": list(ZONES.keys())[1], "expert_ht": 7500.0,
               "target_margin": 35.0}.items():
    st.session_state.setdefault(_k, _v)

if "lots" not in st.session_state:
    st.session_state.lots = {code: [] for _, code in CORPS_METIER}
st.session_state.setdefault("line_counter", 0)
st.session_state.setdefault("nav_step", "Étape 1 · Import / Admin")
st.session_state.setdefault("generated", None)
st.session_state.setdefault("pdf_parsed", False)
st.session_state.setdefault("pdf_applied", [])
st.session_state.setdefault("gen_error", None)


def add_line(code, desc="", unite="m²", qte=None, achat=None, vente=None):
    st.session_state.line_counter += 1
    lid = st.session_state.line_counter
    st.session_state.lots[code].append(lid)
    st.session_state[f"{code}_{lid}_desc"] = desc
    st.session_state[f"{code}_{lid}_unite"] = unite
    st.session_state[f"{code}_{lid}_qte"] = qte
    st.session_state[f"{code}_{lid}_achat"] = achat
    st.session_state[f"{code}_{lid}_vente"] = vente
    return lid


def remove_line(code, lid):
    if lid in st.session_state.lots[code]:
        st.session_state.lots[code].remove(lid)
    for suffix in ("desc", "unite", "qte", "achat", "vente"):
        st.session_state.pop(f"{code}_{lid}_{suffix}", None)


def clear_all_lines():
    for code in list(st.session_state.lots):
        for lid in list(st.session_state.lots[code]):
            remove_line(code, lid)


# ============================================================================
# 6. PERSISTANCE (mémoire) — tout l'état vit dans l'URL (?d=…)
# ============================================================================
# Choix d'architecture : sur Streamlit Cloud le disque est éphémère (instance
# recyclée, parfois plusieurs workers) → un fichier serveur n'est PAS fiable.
# On encode donc l'intégralité de l'état (admin + lignes) dans un paramètre
# d'URL compressé. Conséquence : la sauvegarde survit au rafraîchissement, au
# bouton « retour » du navigateur ET au recyclage de l'instance. L'URL devient
# un véritable signet du dossier.
_PERSIST_KEYS = (list(PLACEHOLDERS.keys())
                 + ["zone_select", "expert_ht", "target_margin", "nav_step",
                    "pdf_parsed", "pdf_applied"])


def _build_snapshot():
    data = {k: st.session_state.get(k) for k in _PERSIST_KEYS}
    data["lots"] = {code: list(ids) for code, ids in st.session_state.lots.items()}
    data["line_counter"] = st.session_state.line_counter
    lines = {}
    for code, ids in st.session_state.lots.items():
        for lid in ids:
            for suf in ("desc", "unite", "qte", "achat", "vente"):
                key = f"{code}_{lid}_{suf}"
                if key in st.session_state:
                    lines[key] = st.session_state[key]
    data["lines"] = lines
    return data


def _apply_snapshot(data):
    for k in _PERSIST_KEYS:
        if k in data and data[k] is not None:
            st.session_state[k] = data[k]
    if isinstance(data.get("lots"), dict):
        st.session_state.lots = {code: list(data["lots"].get(code, []))
                                 for _, code in CORPS_METIER}
    if isinstance(data.get("line_counter"), int):
        st.session_state.line_counter = data["line_counter"]
    for key, val in (data.get("lines") or {}).items():
        st.session_state[key] = val


def _encode_state():
    raw = json.dumps(_build_snapshot(), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(gzip.compress(raw, 6)).decode("ascii")


def _decode_state(blob):
    raw = gzip.decompress(base64.urlsafe_b64decode(blob.encode("ascii")))
    return json.loads(raw.decode("utf-8"))


def persist_state():
    """Écrit l'état courant dans l'URL — seulement s'il a changé (anti-boucle)."""
    try:
        blob = _encode_state()
        if st.query_params.get("d") != blob:
            st.query_params["d"] = blob
    except Exception:
        pass


# Hydratation : une seule fois par session Streamlit (donc rejouée à chaque
# rafraîchissement, qui recrée une session côté serveur).
if not st.session_state.get("_hydrated"):
    st.session_state["_hydrated"] = True
    _blob = st.query_params.get("d")
    if _blob:
        try:
            _apply_snapshot(_decode_state(_blob))
            st.session_state.seeded = True
        except Exception:
            pass

# Première visite : une ligne vierge pour montrer la structure.
if "seeded" not in st.session_state:
    add_line("Platrerie")
    st.session_state.seeded = True


# ============================================================================
# 7. CALLBACKS (exécutés AVANT le rendu des widgets → modifs sûres)
# ============================================================================
def cb_fill_demo():
    for k, v in PLACEHOLDERS.items():
        st.session_state[k] = v
    st.session_state["zone_select"] = list(ZONES.keys())[1]
    st.session_state["expert_ht"] = 7500.0
    st.session_state["target_margin"] = 35.0
    clear_all_lines()
    add_line("Platrerie", "Reprise plâtrerie et enduits muraux", "m²", 25.0, 18.0, 32.0)
    add_line("Plomberie", "Remplacement réseau eau froide", "ml", 12.0, 22.0, 45.0)
    add_line("Sol", "Pose revêtement de sol PVC", "m²", 20.0, 15.0, 28.0)
    st.session_state.seeded = True
    st.toast("Données d'exemple chargées — vous pouvez générer le dossier.", icon="✨")


def cb_reset_all():
    for k in PLACEHOLDERS:
        st.session_state[k] = ""
    clear_all_lines()
    st.session_state["expert_ht"] = 0.0
    st.session_state.generated = None
    st.session_state.pdf_parsed = False
    st.session_state.pdf_applied = []
    st.session_state.seeded = True
    st.toast("Dossier réinitialisé.", icon="🧹")


def cb_goto(target):
    st.session_state.nav_step = target
    st.session_state._scroll_top = True


# ============================================================================
# 8. MOTEUR DE CALCUL
# ============================================================================
def collect_lines():
    rows = []
    label_by_code = {code: label for label, code in CORPS_METIER}
    for _, code in CORPS_METIER:
        for lid in st.session_state.lots[code]:
            qte = float(st.session_state.get(f"{code}_{lid}_qte", 0.0) or 0.0)
            if qte <= 0:
                continue
            achat = float(st.session_state.get(f"{code}_{lid}_achat", 0.0) or 0.0)
            vente = float(st.session_state.get(f"{code}_{lid}_vente", 0.0) or 0.0)
            desc = st.session_state.get(f"{code}_{lid}_desc", "").strip()
            unite = st.session_state.get(f"{code}_{lid}_unite", "u")
            rows.append({
                "corps": label_by_code[code].split(" ", 1)[-1],
                "desc": desc or label_by_code[code],
                "unite": unite, "qte": qte, "achat": achat, "vente": vente,
                "total_achat": qte * achat, "total_vente": qte * vente,
            })
    return rows


def compute(rows, zone_coeff, expert_ht, target_margin):
    subtotal_vente = sum(r["total_vente"] for r in rows)
    total_achat = sum(r["total_achat"] for r in rows)
    final_ht = subtotal_vente * zone_coeff
    tva = final_ht * TVA_RATE
    ttc = final_ht + tva
    cost_total = total_achat * zone_coeff
    margin_eur = final_ht - cost_total
    margin_pct = (margin_eur / final_ht * 100.0) if final_ht > 0 else 0.0
    variance_eur = final_ht - expert_ht
    variance_pct = (variance_eur / expert_ht * 100.0) if expert_ht > 0 else 0.0

    if variance_pct <= 5.0:
        status, color = "CONFORME", SUCCESS
        msg = "Le devis respecte le plafond de l'expert. Prêt à l'envoi."
    elif variance_pct <= 15.0:
        status, color = "VIGILANCE", WARNING
        msg = "Léger dépassement de l'enveloppe expert : une justification sera incluse dans la lettre."
    else:
        status, color = "HORS BUDGET", DANGER
        msg = "Écart critique : risque de refus. Ajustez la marge ou vérifiez les métrés."

    return {
        "subtotal_vente": subtotal_vente, "final_ht": final_ht, "tva": tva, "ttc": ttc,
        "total_achat": total_achat, "cost_total": cost_total,
        "margin_eur": margin_eur, "margin_pct": margin_pct,
        "variance_eur": variance_eur, "variance_pct": variance_pct,
        "status": status, "color": color, "msg": msg,
        "zone_coeff": zone_coeff, "expert_ht": expert_ht, "target_margin": target_margin,
    }


# ============================================================================
# 9. GÉNÉRATION DES PDF
# ============================================================================
def get_pdf_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("DocTitle", parent=styles["Heading1"], fontName="Helvetica-Bold",
               fontSize=17, leading=21, textColor=colors.HexColor(NAVY), alignment=TA_CENTER, spaceAfter=14))
    styles.add(ParagraphStyle("SectionHeader", parent=styles["Heading2"], fontName="Helvetica-Bold",
               fontSize=12, leading=16, textColor=colors.HexColor("#1E293B"), spaceBefore=12, spaceAfter=8))
    styles.add(ParagraphStyle("Body", parent=styles["Normal"], fontName="Helvetica", fontSize=10,
               leading=14, textColor=colors.HexColor("#333333"), alignment=TA_JUSTIFY, spaceAfter=10))
    styles.add(ParagraphStyle("BodyBold", parent=styles["Body"], fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle("Right", parent=styles["Normal"], fontName="Helvetica", fontSize=10,
               leading=14, alignment=TA_RIGHT))
    styles.add(ParagraphStyle("Confidential", parent=styles["Normal"], fontName="Helvetica-Bold",
               fontSize=11, leading=14, textColor=colors.HexColor(DANGER), alignment=TA_CENTER, spaceAfter=10))
    return styles


def _company_header(d, s):
    return Paragraph(
        f"<b>{d['company_name']}</b><br/>{d['company_address']}<br/>"
        f"SIRET : {d['company_siret']} &nbsp;|&nbsp; TVA : {d['company_tva']}", s["Body"])


def build_fiche_interne(d, rows, calc):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=45, bottomMargin=45)
    s = get_pdf_styles()
    story = [
        Paragraph("DOCUMENT INTERNE STRICTEMENT CONFIDENTIEL", s["Confidential"]),
        Paragraph("FICHE DE PRÉPARATION & ANALYSE DE RENTABILITÉ CHANTIER", s["DocTitle"]),
        Spacer(1, 12),
    ]
    info = [
        [Paragraph("<b>PROJET & CLIENT</b>", s["BodyBold"]), Paragraph("<b>RÉFÉRENCES SINISTRE</b>", s["BodyBold"])],
        [Paragraph(f"Assuré : {d['client_name']}<br/>Adresse : {d['address']}", s["Body"]),
         Paragraph(f"Compagnie : {d['insurance_name']}<br/>N° Sinistre : {d['claim_number']}"
                   f"<br/>Expert : {d['expert_name']} ({d['expert_ref']})", s["Body"])],
    ]
    t = Table(info, colWidths=[257, 258])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAEDED")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ("PADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story += [t, Spacer(1, 18), Paragraph("Analyse financière détaillée et coûts de revient", s["SectionHeader"])]

    data = [["Poste", "Qté", "Revient unit.", "Total revient", "Revente unit.", "Total revente"]]
    for r in rows:
        data.append([r["desc"], f"{r['qte']:g} {r['unite']}",
                     format_currency(r["achat"]), format_currency(r["total_achat"]),
                     format_currency(r["vente"]), format_currency(r["total_vente"])])
    data.append(["SOUS-TOTAL (barème)", "", "", format_currency(calc["total_achat"]),
                 "", format_currency(calc["subtotal_vente"])])
    data.append([f"Ajustement zone (×{calc['zone_coeff']:g})", "", "",
                 format_currency(calc["cost_total"]), "", format_currency(calc["final_ht"])])
    data.append(["TOTAL GÉNÉRAL HT", "", "", format_currency(calc["cost_total"]),
                 "", format_currency(calc["final_ht"])])
    t = Table(data, colWidths=[150, 50, 78, 78, 78, 81])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"), ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ("FONTNAME", (0, -3), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F2F4F4")),
        ("PADDING", (0, 0), (-1, -1), 6), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
    ]))
    story += [t, Spacer(1, 18), Paragraph("Indicateurs de rentabilité stratégique", s["SectionHeader"])]
    perf = (f"<b>Coût de revient total brut :</b> {format_currency(calc['cost_total'])}<br/>"
            f"<b>Chiffre d'affaires prévisionnel HT :</b> {format_currency(calc['final_ht'])}<br/>"
            f"<b>Marge commerciale réelle dégagée :</b> {format_currency(calc['margin_eur'])}<br/>"
            f"<b>Taux de marge réelle :</b> {calc['margin_pct']:.2f} % "
            f"<i>(objectif cible : {calc['target_margin']:.2f} %)</i>")
    story.append(Paragraph(perf, s["Body"]))
    if calc["margin_pct"] < calc["target_margin"]:
        story += [Spacer(1, 8), Paragraph(
            "⚠️ ALERTE RENTABILITÉ : la marge réelle est inférieure à votre objectif cible.", s["Confidential"])]
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def build_devis_conforme(d, rows, calc):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=45, bottomMargin=45)
    s = get_pdf_styles()
    head = [[_company_header(d, s),
             Paragraph(f"<b>DEVIS OFFICIEL</b><br/>N° DEV-{datetime.date.today():%Y%m}-01"
                       f"<br/>Date : {datetime.date.today():%d/%m/%Y}<br/>Validité : 90 jours", s["Right"])]]
    story = [Table(head, colWidths=[315, 200]), Spacer(1, 16),
             Paragraph("DEVIS DE RÉFECTION CONFORME APRÈS SINISTRE", s["DocTitle"]), Spacer(1, 8)]
    client = [
        [Paragraph("<b>DESTINATAIRE / ASSURÉ</b>", s["BodyBold"]),
         Paragraph("<b>CONTEXTE SINISTRE & EXPERTISE</b>", s["BodyBold"])],
        [Paragraph(f"{d['client_name']}<br/>{d['address']}", s["Body"]),
         Paragraph(f"Compagnie : {d['insurance_name']}<br/>N° Sinistre : {d['claim_number']}"
                   f"<br/>Cabinet : {d['expert_name']}<br/>Réf. expert : {d['expert_ref']}", s["Body"])],
    ]
    t = Table(client, colWidths=[257, 258])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ("PADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story += [t, Spacer(1, 18), Paragraph("Désignation des travaux de réfection", s["SectionHeader"])]
    data = [["Désignation des travaux", "Quantité", "Prix unitaire HT", "Montant HT"]]
    for r in rows:
        data.append([f"[{r['corps']}] {r['desc']}", f"{r['qte']:g} {r['unite']}",
                     format_currency(r["vente"]), format_currency(r["total_vente"])])
    maj_pct = int(round((calc["zone_coeff"] - 1) * 100))
    zone_txt = (f"Ajustement géographique (+{maj_pct} %)" if maj_pct > 0
                else "Ajustement géographique (sans majoration)")
    data += [
        ["Sous-total HT (barème standard)", "", "", format_currency(calc["subtotal_vente"])],
        [zone_txt, "", "", format_currency(calc["final_ht"] - calc["subtotal_vente"])],
        ["TOTAL NET HORS TAXES", "", "", format_currency(calc["final_ht"])],
        [f"TVA ({TVA_RATE*100:.2f} %)", "", "", format_currency(calc["tva"])],
        ["TOTAL TTC", "", "", format_currency(calc["ttc"])],
    ]
    t = Table(data, colWidths=[275, 70, 85, 85])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"), ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ("PADDING", (0, 0), (-1, -1), 6), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EAECEE")),
    ]
    for i in range(len(data) - 5, len(data)):
        style.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
    t.setStyle(TableStyle(style))
    story += [t, Spacer(1, 30)]
    sig = [[Paragraph("<b>Cadre réservé à l'entreprise</b><br/>Pour la direction technique<br/>Bon pour exécution", s["Body"]),
            Paragraph("<b>Bon pour accord client / compagnie</b><br/>Date, signature et mention<br/>« Lu et approuvé – Bon pour accord »", s["Body"])]]
    t = Table(sig, colWidths=[257, 258])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.HexColor("#7F8C8D")),
                           ("PADDING", (0, 0), (-1, -1), 10), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(t)
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def build_lettre_expert(d, rows, calc):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50)
    s = get_pdf_styles()
    story = [_company_header(d, s), Spacer(1, 14)]
    dest = (f"<b>Cabinet d'expertise :</b> {d['expert_name']}<br/>À l'attention de l'expert en charge"
            f"<br/><b>Réf. dossier :</b> {d['expert_ref']}")
    story += [Table([[Spacer(1, 1), Paragraph(dest, s["Body"])]], colWidths=[245, 250]), Spacer(1, 18),
              Paragraph(f"Fait à Paris, le {datetime.date.today():%d/%m/%Y}", s["Right"]), Spacer(1, 12)]
    obj = (f"<b>Objet :</b> Proposition de chiffrage de réfection suite à sinistre<br/>"
           f"<b>N° de sinistre :</b> {d['claim_number']}<br/><b>Assuré :</b> {d['client_name']}<br/>"
           f"<b>Adresse :</b> {d['address']}")
    story += [Paragraph(obj, s["Body"]), Spacer(1, 12),
              Paragraph("Madame, Monsieur l'Expert,", s["Body"]), Spacer(1, 6)]
    story.append(Paragraph(
        "Dans le cadre du dossier référencé ci-dessus, nous avons l'honneur de vous soumettre notre "
        "proposition de chiffrage pour les travaux de remise en état, dressée en respectant les métrés "
        "et volumes validés lors de votre expertise.", s["Body"]))
    story.append(Paragraph(
        f"Notre devis s'établit à un montant total de <b>{format_currency(calc['final_ht'])} HT</b>, "
        f"soit <b>{format_currency(calc['ttc'])} TTC</b> après application de la TVA réglementaire de "
        f"{TVA_RATE*100:.0f} % dédiée aux travaux de rénovation après sinistre.", s["Body"]))
    if calc["status"] == "VIGILANCE":
        cond = ("<b>Note de justification technique :</b> ce chiffrage présente un léger ajustement par "
                "rapport à votre première enveloppe, motivé par les spécificités des supports identifiés "
                "et les contraintes géographiques du chantier.")
    elif calc["status"] == "HORS BUDGET":
        cond = ("<b>Note d'analyse de conformité budgétaire :</b> constatant un écart significatif avec "
                "l'évaluation initiale, les contraintes d'exécution réelles imposent cette réévaluation. "
                "Nous sollicitons une révision bienveillante du dossier dans l'intérêt de l'assuré.")
    else:
        cond = ("Nous constatons avec satisfaction que notre proposition s'inscrit en parfaite adéquation "
                "avec vos évaluations initiales, démontrant la stricte conformité technique de notre offre.")
    story += [Spacer(1, 4), Paragraph(cond, s["Body"]), Spacer(1, 8),
              Paragraph("Nous restons à votre disposition pour tout justificatif complémentaire nécessaire "
                        "à la validation de ce dossier d'indemnisation.", s["Body"]), Spacer(1, 6),
              Paragraph("Veuillez agréer, Madame, Monsieur l'Expert, l'expression de nos salutations "
                        "distinguées.", s["Body"]), Spacer(1, 28),
              Paragraph(f"<b>{d['company_name']}</b><br/>Département de réhabilitation après sinistre", s["Body"])]
    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def generate_all(rows, calc):
    """Génère les 3 PDF. Renseigne gen_error en cas d'échec (jamais de crash)."""
    d = {k: (st.session_state[k].strip() or PLACEHOLDERS.get(k, ""))
         for k in ("company_name", "company_address", "company_siret", "company_tva",
                   "client_name", "address", "insurance_name", "claim_number",
                   "expert_name", "expert_ref")}
    try:
        st.session_state.generated = {
            "fiche": build_fiche_interne(d, rows, calc),
            "devis": build_devis_conforme(d, rows, calc),
            "lettre": build_lettre_expert(d, rows, calc),
            "claim": d["claim_number"] or "dossier",
        }
        st.session_state.gen_error = None
        return True
    except Exception:
        st.session_state.generated = None
        st.session_state.gen_error = traceback.format_exc(limit=3)
        return False


# ============================================================================
# 10. COMPOSANTS UI
# ============================================================================
def kpi_card(label, value, sub="", accent=None):
    style = f"--kpi-accent:{accent};" if accent else ""
    return (f'<div class="kpi" style="{style}"><div class="label">{label}</div>'
            f'<div class="value">{value}</div><div class="sub">{sub}</div></div>')


def status_banner(calc):
    st.markdown(
        f'<div class="status-box" style="background:{calc["color"]}1A; border-left:6px solid {calc["color"]};">'
        f'<h4 style="color:{calc["color"]};">Statut du dossier : {calc["status"]}</h4>'
        f'<p>{calc["msg"]}</p></div>', unsafe_allow_html=True)


STEPS = ["Étape 1 · Import / Admin", "Étape 2 · Chiffrage par lots", "Étape 3 · Génération & Dashboard"]
STEP_TITLES = ["Import / Admin", "Chiffrage par lots", "Génération & Dashboard"]


def render_stepper(active_index):
    """Stepper CLIQUABLE : un clic sur une étape y navigue directement."""
    pct = int((active_index + 1) / len(STEPS) * 100)
    st.markdown(f"<div class='tech-progress'><span style='width:{pct}%'></span></div>",
                unsafe_allow_html=True)
    cols = st.columns(len(STEPS))
    for i, (col, title) in enumerate(zip(cols, STEP_TITLES)):
        mark = "✓" if i < active_index else str(i + 1)
        col.button(f"{mark}  {title}", key=f"step_{i}", width="stretch",
                   type=("primary" if i == active_index else "secondary"),
                   on_click=cb_goto, args=(STEPS[i],))


def render_nav_buttons(active_index):
    st.divider()
    prev_c, _, next_c = st.columns([1, 2, 1])
    if active_index > 0:
        prev_c.button("← Étape précédente", width="stretch", on_click=cb_goto,
                      args=(STEPS[active_index - 1],), key=f"prev_{active_index}")
    if active_index < len(STEPS) - 1:
        next_c.button("Étape suivante →", type="primary", width="stretch", on_click=cb_goto,
                      args=(STEPS[active_index + 1],), key=f"next_{active_index}")


def scroll_to_top_if_needed():
    if st.session_state.pop("_scroll_top", False):
        components.html(
            "<script>const d=window.parent.document;"
            "const t=d.querySelector('section.main')||d.querySelector('[data-testid=\"stMain\"]')"
            "||d.scrollingElement||d.documentElement;"
            "if(t){t.scrollTo({top:0,behavior:'smooth'});}"
            "window.parent.scrollTo({top:0,behavior:'smooth'});</script>", height=0)


# ============================================================================
# 11. EN-TÊTE & SIDEBAR
# ============================================================================
st.markdown(
    '<div class="hero"><span class="orb a"></span><span class="orb b"></span>'
    '<span class="live"><span class="dot"></span> SYSTÈME OPÉRATIONNEL</span>'
    '<h1>🏛️ Gestionnaire Stratégique de Sinistres</h1>'
    '<p>Chiffrage par corps de métier · Analyse de marge · Conformité expert · Génération documentaire</p>'
    '</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🧭 Navigation")
    st.radio("Étapes du workflow", STEPS, key="nav_step", label_visibility="collapsed")
    st.divider()
    _rows = collect_lines()
    _zc = ZONES[st.session_state["zone_select"]]
    _calc = compute(_rows, _zc, st.session_state["expert_ht"], st.session_state["target_margin"])
    st.markdown("### 📊 Récapitulatif live")
    st.metric("Total HT proposé", format_currency(_calc["final_ht"]))
    st.metric("Marge réelle", f"{_calc['margin_pct']:.1f} %", f"{format_currency(_calc['margin_eur'])}")
    st.caption(f"{len(_rows)} ligne(s) active(s) · Zone ×{_zc:g}")
    st.divider()
    st.button("✨ Charger un exemple complet", on_click=cb_fill_demo, width="stretch", key="demo_btn")
    st.button("🧹 Réinitialiser le dossier", on_click=cb_reset_all, width="stretch", key="reset_btn")


# ============================================================================
# 12. ÉTAPE 1 — IMPORT / ADMIN
# ============================================================================
def render_step1():
    st.subheader("Étape 1 — Import du rapport & informations administratives")

    with st.container(border=True):
        st.markdown("##### 📂 Import du rapport d'expertise (optionnel)")
        if not PDFPLUMBER_OK:
            st.caption("Module d'extraction PDF indisponible — la saisie manuelle reste opérationnelle.")
        up = st.file_uploader("Déposez le rapport PDF pour pré-remplir les champs", type=["pdf"])
        if up is not None and not st.session_state.pdf_parsed:
            with st.spinner("Analyse du document et extraction des données clés…"):
                info = extract_data_from_pdf(up)
            labels = {"claim_number": "N° sinistre", "expert_ref": "Réf. expert",
                      "expert_name": "Cabinet", "insurance_name": "Compagnie",
                      "client_name": "Assuré", "address": "Adresse", "expert_ht": "Plafond HT"}
            applied = []
            for key in ("claim_number", "expert_ref", "expert_name", "insurance_name",
                        "client_name", "address", "expert_ht"):
                if info.get(key):
                    st.session_state[key] = info[key]
                    applied.append(labels[key])
            st.session_state.pdf_parsed = True
            st.session_state.pdf_applied = applied
            st.rerun()
        if st.session_state.pdf_parsed:
            applied = st.session_state.get("pdf_applied", [])
            if applied:
                st.success("Champs pré-remplis depuis le PDF : " + ", ".join(applied) + " ✔")
            else:
                st.info("Aucune donnée exploitable détectée — complétez les champs manuellement.")
            if st.button("↻ Réinitialiser l'import PDF"):
                st.session_state.pdf_parsed = False
                st.session_state.pdf_applied = []
                st.rerun()

    with st.container(border=True):
        st.markdown("##### 🏢 Entité émettrice (conformité légale du devis)")
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("Raison sociale", key="company_name", placeholder=PLACEHOLDERS["company_name"])
            st.text_input("Adresse du siège", key="company_address", placeholder=PLACEHOLDERS["company_address"])
        with c2:
            st.text_input("Numéro SIRET", key="company_siret", max_chars=20,
                          placeholder=PLACEHOLDERS["company_siret"], help="14 chiffres ; espaces et tirets acceptés.")
            st.text_input("N° TVA intracommunautaire", key="company_tva", placeholder=PLACEHOLDERS["company_tva"])
        siret = st.session_state["company_siret"].strip()
        if siret == "":
            st.caption("Le SIRET sera repris tel quel dans l'en-tête des documents.")
        elif validate_siret(siret):
            st.caption("✅ SIRET valide — repris dans l'en-tête de chaque document.")
        else:
            st.info("ℹ️ Format SIRET inhabituel (14 chiffres attendus). La génération reste possible.")

    with st.container(border=True):
        st.markdown("##### 📁 Dossier client & sinistre")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.text_input("Nom de l'assuré *", key="client_name", placeholder=PLACEHOLDERS["client_name"])
            st.text_input("Adresse du chantier *", key="address", placeholder=PLACEHOLDERS["address"])
        with c2:
            st.text_input("Compagnie d'assurance *", key="insurance_name", placeholder=PLACEHOLDERS["insurance_name"])
            st.text_input("Numéro de sinistre *", key="claim_number", placeholder=PLACEHOLDERS["claim_number"])
        with c3:
            st.text_input("Cabinet d'expertise *", key="expert_name", placeholder=PLACEHOLDERS["expert_name"])
            st.text_input("Référence rapport expert *", key="expert_ref", placeholder=PLACEHOLDERS["expert_ref"])
        st.markdown("**🌍 Zone géographique**")
        zc1, _ = st.columns([1, 2])
        zc1.selectbox("Coefficient géographique", list(ZONES.keys()), key="zone_select",
                      help="Zone A ×1,00 · Zone B ×1,15 · Zone C ×1,25")

    st.info("Passez à l'**Étape 2** (menu de gauche) pour chiffrer les travaux par corps de métier.")


# ============================================================================
# 13. ÉTAPE 2 — CHIFFRAGE PAR LOTS
# ============================================================================
def render_step2():
    st.subheader("Étape 2 — Chiffrage par corps de métier")
    st.caption("Chaque lot est facultatif. Dépliez un corps de métier et ajoutez des lignes. "
               "Les totaux se recalculent en temps réel.")

    for label, code in CORPS_METIER:
        ids = st.session_state.lots[code]
        lot_total = sum(float(st.session_state.get(f"{code}_{i}_qte", 0) or 0)
                        * float(st.session_state.get(f"{code}_{i}_vente", 0) or 0) for i in ids)
        suffix = f"  —  {len(ids)} ligne(s) · {format_currency(lot_total)}" if ids else "  —  vide"
        with st.expander(label + suffix, expanded=bool(ids)):
            if ids:
                h = st.columns([3, 1.1, 1, 1.3, 1.3, 1.5, 0.6])
                for col, name in zip(h, ["Description", "Qté", "Unité", "Prix achat",
                                         "Prix vente", "Total vente", ""]):
                    col.markdown(f"<div class='col-head'>{name}</div>", unsafe_allow_html=True)
            for lid in list(ids):
                c = st.columns([3, 1.1, 1, 1.3, 1.3, 1.5, 0.6])
                c[0].text_input("Description", key=f"{code}_{lid}_desc", label_visibility="collapsed",
                                placeholder="Ex : Reprise plâtrerie et enduits…")
                qte = c[1].number_input("Qté", min_value=0.0, step=1.0, key=f"{code}_{lid}_qte",
                                        label_visibility="collapsed", placeholder="0")
                c[2].selectbox("Unité", UNITES, key=f"{code}_{lid}_unite", label_visibility="collapsed")
                c[3].number_input("Achat", min_value=0.0, step=0.5, key=f"{code}_{lid}_achat",
                                  label_visibility="collapsed", placeholder="0,00")
                vente = c[4].number_input("Vente", min_value=0.0, step=0.5, key=f"{code}_{lid}_vente",
                                          label_visibility="collapsed", placeholder="0,00")
                ligne_total = (qte or 0) * (vente or 0)
                c[5].markdown(f"<div style='padding-top:6px;font-weight:700;color:{NAVY};'>"
                              f"{format_currency(ligne_total)}</div>", unsafe_allow_html=True)
                if c[6].button("🗑", key=f"{code}_{lid}_del", help="Supprimer la ligne"):
                    remove_line(code, lid)
                    st.rerun()
            if st.button("➕ Ajouter une ligne", key=f"add_{code}"):
                add_line(code, desc="", unite="m²")
                st.rerun()

    st.divider()
    rows = collect_lines()
    zc = ZONES[st.session_state["zone_select"]]
    calc = compute(rows, zc, st.session_state["expert_ht"], st.session_state["target_margin"])
    g1, g2, g3 = st.columns(3)
    g1.markdown(kpi_card("Sous-total HT (barème)", format_currency(calc["subtotal_vente"]),
                         f"{len(rows)} ligne(s)"), unsafe_allow_html=True)
    g2.markdown(kpi_card("Total HT après zone", format_currency(calc["final_ht"]),
                         f"Coefficient ×{zc:g}"), unsafe_allow_html=True)
    g3.markdown(kpi_card("Coût de revient", format_currency(calc["cost_total"]),
                         "Achat × zone"), unsafe_allow_html=True)


# ============================================================================
# 14. ÉTAPE 3 — GÉNÉRATION & DASHBOARD
# ============================================================================
def render_step3():
    st.subheader("Étape 3 — Génération & tableau de bord")
    rows = collect_lines()

    with st.container(border=True):
        st.markdown("##### 🎯 Paramètres d'analyse")
        p1, p2 = st.columns(2)
        p1.number_input("Plafond estimé par l'expert (HT en €) *", min_value=0.0, step=50.0, key="expert_ht")
        p2.slider("Objectif de marge commerciale (%)", min_value=10.0, max_value=60.0,
                  step=0.5, key="target_margin")

    zc = ZONES[st.session_state["zone_select"]]
    calc = compute(rows, zc, st.session_state["expert_ht"], st.session_state["target_margin"])

    st.markdown("### 📈 Dashboard de compatibilité financière")
    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(kpi_card("Notre proposition HT", format_currency(calc["final_ht"]),
                         f"TTC : {format_currency(calc['ttc'])}"), unsafe_allow_html=True)
    m2.markdown(kpi_card("Plafond expert HT", format_currency(calc["expert_ht"]),
                         "Enveloppe assurance"), unsafe_allow_html=True)
    m3.markdown(kpi_card("Écart constaté", format_currency(calc["variance_eur"]),
                         f"{calc['variance_pct']:+.2f} %", calc["color"]), unsafe_allow_html=True)
    m4.markdown(kpi_card("Marge réelle", f"{calc['margin_pct']:.2f} %",
                         f"Cible : {calc['target_margin']:.0f} %",
                         SUCCESS if calc["margin_pct"] >= calc["target_margin"] else WARNING),
                unsafe_allow_html=True)
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    status_banner(calc)

    if rows:
        st.markdown("##### 📋 Détail du chiffrage retenu")
        st.dataframe(
            [{"Corps de métier": r["corps"], "Description": r["desc"],
              "Qté": f"{r['qte']:g} {r['unite']}", "PU vente": format_currency(r["vente"]),
              "Total HT": format_currency(r["total_vente"])} for r in rows],
            width="stretch", hide_index=True)
    else:
        st.warning("Aucune ligne chiffrée. Revenez à l'**Étape 2** pour ajouter des travaux.")

    st.divider()
    st.markdown("### 🗂️ Génération du dossier")

    # Liste de contrôle claire : on voit EXACTEMENT ce qui manque.
    checks = [
        ("Au moins une ligne chiffrée", bool(rows)),
        ("Nom de l'assuré renseigné", bool(st.session_state["client_name"].strip())),
        ("Numéro de sinistre renseigné", bool(st.session_state["claim_number"].strip())),
        ("Plafond expert supérieur à 0 €", st.session_state["expert_ht"] > 0),
    ]
    blocking = not all(ok for _, ok in checks)
    with st.container(border=True):
        st.markdown("**Conditions de génération**")
        for label, ok in checks:
            cls = "ok" if ok else "ko"
            ic = "✓" if ok else "✗"
            st.markdown(f"<div class='check {cls}'><span class='ic'>{ic}</span>{label}</div>",
                        unsafe_allow_html=True)
        if blocking:
            st.caption("Astuce : le bouton « ✨ Charger un exemple complet » (menu de gauche) "
                       "remplit tout instantanément pour tester la génération.")

    if st.button("🔥 Générer le dossier complet (3 PDF)", type="primary", disabled=blocking):
        with st.spinner("Compilation des documents conformes…"):
            ok = generate_all(rows, calc)
        if ok:
            st.toast("Les 3 documents ont été générés.", icon="🎉")
            st.success("🎉 Dossier généré. Téléchargez vos documents ci-dessous.")
        else:
            st.error("Une erreur est survenue pendant la génération. Détail technique ci-dessous.")
            st.code(st.session_state.gen_error or "Erreur inconnue")

    gen = st.session_state.generated
    if gen:
        st.markdown("##### 📥 Espace de téléchargement")
        d1, d2, d3 = st.columns(3)
        d1.download_button("📄 Fiche interne (confidentiel)", data=gen["fiche"],
                           file_name=f"fiche_interne_{gen['claim']}.pdf",
                           mime="application/pdf", width="stretch")
        d2.download_button("📑 Devis conforme (officiel)", data=gen["devis"],
                           file_name=f"devis_conforme_{gen['claim']}.pdf",
                           mime="application/pdf", width="stretch")
        d3.download_button("✉️ Lettre à l'expert", data=gen["lettre"],
                           file_name=f"lettre_expert_{gen['claim']}.pdf",
                           mime="application/pdf", width="stretch")
        st.caption("Vos saisies sont conservées : télécharger un document ne réinitialise rien.")


# ============================================================================
# 15. ROUTAGE
# ============================================================================
scroll_to_top_if_needed()
if st.session_state["nav_step"] not in STEPS:
    st.session_state["nav_step"] = STEPS[0]
active_index = STEPS.index(st.session_state["nav_step"])
render_stepper(active_index)

if active_index == 0:
    render_step1()
elif active_index == 1:
    render_step2()
else:
    render_step3()

render_nav_buttons(active_index)

# Sauvegarde automatique dans l'URL à la fin de CHAQUE exécution : à ce stade,
# toutes les saisies de la passe courante sont déjà dans st.session_state.
persist_state()
