# -*- coding: utf-8 -*-
"""
============================================================================
 GESTIONNAIRE STRATÉGIQUE DE SINISTRES — Plateforme SaaS de chiffrage BTP
============================================================================
Workflow en 3 étapes :
    Étape 1 : Import / Admin      -> Dépôt du rapport PDF + saisie entité & dossier
    Étape 2 : Chiffrage par lots  -> Un expander par corps de métier, lignes dynamiques
    Étape 3 : Génération & Dashboard -> KPI de marge, conformité expert, export PDF

Principes d'implémentation :
    - Tout est piloté par st.session_state : aucune donnée n'est perdue lors d'un
      téléchargement (Streamlit relance le script à chaque clic).
    - Le chiffrage est volontairement HORS st.form pour permettre :
        * l'ajout / suppression de lignes via boutons "+"/"corbeille"
        * la mise à jour des totaux EN TEMPS RÉEL
    - Mobile-friendly : st.columns s'empile proprement sur petit écran.
============================================================================
"""

import io
import re
import datetime

import streamlit as st
import streamlit.components.v1 as components

# Dépendances PDF (génération + extraction)
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib import colors

try:
    import pdfplumber  # Extraction optionnelle du rapport d'expertise
    PDFPLUMBER_OK = True
except Exception:  # L'app reste fonctionnelle même sans pdfplumber installé
    PDFPLUMBER_OK = False


# ============================================================================
# 1. CONFIGURATION DE LA PAGE & CHARTE GRAPHIQUE (CSS)
# ============================================================================
st.set_page_config(
    page_title="Gestionnaire Stratégique de Sinistres",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Palette high-tech
NAVY = "#0F2A4A"        # Bleu marine profond — chrome sombre
ANTHRACITE = "#1E293B"  # Gris anthracite — surfaces sombres
ACCENT = "#3B82F6"      # Bleu électrique — accents / boutons
ACCENT2 = "#22D3EE"     # Cyan — dégradés / glow
SUCCESS = "#22C55E"     # Vert — statut conforme
WARNING = "#F59E0B"     # Orange — vigilance
DANGER = "#EF4444"      # Rouge — hors budget
SURFACE = "#FFFFFF"     # Cartes (espace de travail clair)
BG = "#EEF2F7"          # Fond général

INK = "#0F1B2D"   # Encre principale (texte sur fond clair) — contraste fort
MUTED = "#5B6B7B"  # Texte secondaire / captions

# Injection CSS : design high-tech (chrome sombre + workspace clair), animations
# et effets. On force EXPLICITEMENT les couleurs pour éliminer tout problème de
# contraste (jamais de texte foncé sur fond foncé, ni clair sur clair).
st.markdown(f"""
<style>
    /* ====================== BASE & FOND ====================== */
    .stApp {{ background:
        radial-gradient(1200px 600px at 110% -10%, rgba(59,130,246,.10), transparent 60%),
        radial-gradient(900px 500px at -10% 10%, rgba(34,211,238,.08), transparent 55%),
        {BG} !important; }}
    [data-testid="stHeader"] {{ background: transparent; }}
    .block-container {{ padding-top: 2rem; padding-bottom: 5rem; max-width: 1180px; }}

    /* ====================== TEXTE (workspace clair) ====================== */
    .stApp, .stApp p, .stApp li, .stApp label, .stApp span,
    [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li,
    [data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label,
    .stRadio label, .stSelectbox label, .stTextInput label,
    .stNumberInput label, .stSlider label, .stFileUploader label {{
        color: {INK} !important; }}
    [data-testid="stCaptionContainer"], .stCaption, small {{ color: {MUTED} !important; }}
    h1, h2, h3, h4, h5, h6 {{ color: {NAVY} !important; letter-spacing:.2px; }}

    /* Champs de saisie clairs et nets */
    .stTextInput input, .stNumberInput input,
    .stSelectbox div[data-baseweb="select"] > div, textarea {{
        background:#FFFFFF !important; color:{INK} !important;
        border-radius:10px !important; border:1px solid #D7DEE8 !important; }}
    .stTextInput input:focus, .stNumberInput input:focus {{
        border-color:{ACCENT} !important; box-shadow:0 0 0 3px rgba(59,130,246,.18) !important; }}
    input::placeholder, textarea::placeholder {{ color:#9AA7B4 !important; opacity:1; }}

    /* Menus déroulants : fond blanc + texte foncé (corrige le foncé-sur-foncé) */
    [data-baseweb="popover"], [data-baseweb="menu"], ul[role="listbox"] {{
        background:#FFFFFF !important; }}
    li[role="option"], [data-baseweb="menu"] * {{ color:{INK} !important; }}
    li[role="option"]:hover {{ background:#EEF4FF !important; }}

    /* Dataframe lisible */
    [data-testid="stDataFrame"] {{ background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; }}
    [data-testid="stDataFrame"] * {{ color:{INK} !important; }}

    /* ====================== ANIMATIONS ====================== */
    @keyframes shift {{ 0%{{background-position:0% 50%}} 50%{{background-position:100% 50%}}
                        100%{{background-position:0% 50%}} }}
    @keyframes fadeInUp {{ from{{opacity:0; transform:translateY(10px)}} to{{opacity:1; transform:none}} }}
    @keyframes pulse {{ 0%{{box-shadow:0 0 0 0 rgba(34,211,238,.55)}}
                        70%{{box-shadow:0 0 0 9px rgba(34,211,238,0)}}
                        100%{{box-shadow:0 0 0 0 rgba(34,211,238,0)}} }}

    /* ====================== BANDEAU (HERO) ====================== */
    .hero {{ position:relative; overflow:hidden; border-radius:18px; padding:30px 32px;
        margin-bottom:18px; color:#fff;
        background: linear-gradient(120deg, {NAVY}, #15356b, {ACCENT}, #15356b, {NAVY});
        background-size:300% 300%; animation:shift 14s ease infinite;
        box-shadow:0 18px 50px rgba(15,42,74,.35);
        border:1px solid rgba(255,255,255,.10); }}
    .hero::after {{ content:""; position:absolute; inset:0; pointer-events:none;
        background-image:linear-gradient(rgba(255,255,255,.06) 1px, transparent 1px),
                         linear-gradient(90deg, rgba(255,255,255,.06) 1px, transparent 1px);
        background-size:26px 26px; mask:radial-gradient(60% 120% at 80% 0%, #000, transparent 70%); }}
    .hero h1 {{ color:#fff !important; margin:0; font-size:1.6rem; letter-spacing:.3px;
        position:relative; z-index:1; }}
    .hero p {{ color:#C7D6EC !important; margin:.4rem 0 0 0; font-size:.95rem;
        position:relative; z-index:1; }}
    .hero .live {{ position:relative; z-index:1; display:inline-flex; align-items:center; gap:8px;
        margin-bottom:10px; padding:5px 12px; border-radius:999px; font-size:.72rem; font-weight:700;
        letter-spacing:.6px; color:#E0F2FE !important; background:rgba(255,255,255,.10);
        border:1px solid rgba(255,255,255,.18); }}
    .hero .dot {{ width:8px; height:8px; border-radius:50%; background:{ACCENT2};
        animation:pulse 1.8s infinite; }}

    /* ====================== BARRE DE PROGRESSION ====================== */
    .tech-progress {{ height:6px; border-radius:999px; background:#DCE3EC; overflow:hidden; margin:0 2px 18px 2px; }}
    .tech-progress > span {{ display:block; height:100%; border-radius:999px;
        background:linear-gradient(90deg, {ACCENT2}, {ACCENT}); transition:width .5s cubic-bezier(.4,0,.2,1);
        box-shadow:0 0 12px rgba(59,130,246,.6); }}

    /* ====================== FIL D'ARIANE ====================== */
    .crumbs {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:8px; }}
    .crumb {{ flex:1; min-width:150px; background:rgba(255,255,255,.75); backdrop-filter:blur(8px);
        border:1px solid #E2E8F0; border-radius:12px; padding:11px 14px;
        box-shadow:0 2px 10px rgba(0,0,0,.04); transition:all .25s ease; }}
    .crumb .n {{ display:inline-block; width:24px; height:24px; border-radius:50%; background:#E2E8F0;
        color:{MUTED} !important; text-align:center; line-height:24px; font-weight:700;
        font-size:.8rem; margin-right:9px; transition:all .25s ease; }}
    .crumb .t {{ color:{MUTED} !important; font-weight:600; font-size:.86rem; }}
    .crumb.active {{ border-color:transparent;
        background:linear-gradient(120deg, {NAVY}, {ACCENT}); box-shadow:0 8px 22px rgba(59,130,246,.35); }}
    .crumb.active .n {{ background:#fff; color:{ACCENT} !important; }}
    .crumb.active .t {{ color:#fff !important; }}
    .crumb.done .n {{ background:{SUCCESS}; color:#fff !important; }}

    /* ====================== CARTES ====================== */
    .card {{ background:{SURFACE}; border:1px solid #E6EBF2; border-radius:16px; padding:18px 20px;
        box-shadow:0 6px 22px rgba(15,27,45,.05); margin-bottom:16px; animation:fadeInUp .45s ease both; }}

    /* ====================== KPI ====================== */
    .kpi {{ position:relative; background:{SURFACE}; border:1px solid #E6EBF2; border-radius:16px;
        padding:18px 18px 16px; height:100%; overflow:hidden;
        box-shadow:0 6px 22px rgba(15,27,45,.06); animation:fadeInUp .45s ease both;
        transition:transform .2s ease, box-shadow .2s ease; }}
    .kpi::before {{ content:""; position:absolute; top:0; left:0; right:0; height:4px;
        background:var(--kpi-accent, linear-gradient(90deg, {ACCENT2}, {ACCENT})); }}
    .kpi:hover {{ transform:translateY(-3px); box-shadow:0 16px 34px rgba(15,27,45,.12); }}
    .kpi .label {{ color:{MUTED} !important; font-size:.74rem; text-transform:uppercase;
        letter-spacing:.7px; font-weight:700; }}
    .kpi .value {{ color:{NAVY} !important; font-size:1.55rem; font-weight:800; margin-top:6px;
        font-feature-settings:"tnum"; }}
    .kpi .sub {{ color:#94A3B8 !important; font-size:.8rem; margin-top:3px; }}

    /* ====================== STATUT ====================== */
    .status-box {{ border-radius:14px; padding:16px 20px; margin:6px 0 18px 0; font-weight:500;
        animation:fadeInUp .4s ease both; }}
    .status-box h4 {{ margin:0 0 4px 0; font-size:1.05rem; }}
    .status-box p {{ margin:0; color:#334155 !important; }}

    .col-head {{ color:{MUTED} !important; font-size:.72rem; text-transform:uppercase;
        letter-spacing:.5px; font-weight:700; padding-bottom:2px; }}

    /* ====================== BOUTONS ====================== */
    .stButton > button, .stDownloadButton > button {{ border-radius:12px; font-weight:700;
        border:1px solid #CBD5E0; color:{INK}; background:#FFFFFF; transition:all .18s ease; }}
    .stButton > button:hover, .stDownloadButton > button:hover {{ transform:translateY(-2px);
        box-shadow:0 10px 22px rgba(59,130,246,.18); border-color:{ACCENT}; color:{NAVY}; }}
    .stButton > button[kind="primary"], .stDownloadButton > button {{
        background:linear-gradient(120deg, {ACCENT}, {NAVY}) !important; color:#fff !important;
        border:none !important; box-shadow:0 8px 20px rgba(59,130,246,.30) !important; }}
    .stButton > button[kind="primary"]:hover, .stDownloadButton > button:hover {{
        box-shadow:0 12px 28px rgba(59,130,246,.45) !important; color:#fff !important; }}
    .stButton > button[kind="primary"]:disabled {{ opacity:.45; box-shadow:none !important; }}

    /* ====================== EXPANDERS ====================== */
    div[data-testid="stExpander"] {{ border-radius:14px; border:1px solid #E6EBF2; background:#FFFFFF;
        box-shadow:0 4px 16px rgba(15,27,45,.04); transition:box-shadow .2s ease; }}
    div[data-testid="stExpander"]:hover {{ box-shadow:0 10px 26px rgba(15,27,45,.08); }}
    div[data-testid="stExpander"] summary p {{ color:{NAVY} !important; font-weight:700; }}

    div[data-testid="stAlert"] p {{ color:{INK} !important; }}
    hr {{ border-color:#E2E8F0 !important; }}

    /* ====================== SIDEBAR SOMBRE ====================== */
    section[data-testid="stSidebar"] > div {{
        background:linear-gradient(180deg, #0B1F38 0%, {NAVY} 100%) !important;
        border-right:1px solid rgba(255,255,255,.06); }}
    section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span, section[data-testid="stSidebar"] div,
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {{ color:#E2E8F0 !important; }}
    section[data-testid="stSidebar"] h3 {{ color:#FFFFFF !important; }}
    section[data-testid="stSidebar"] [data-testid="stMetricValue"] {{ color:#FFFFFF !important; }}
    section[data-testid="stSidebar"] [data-testid="stMetricLabel"] * {{ color:#9FB3CC !important; }}
    section[data-testid="stSidebar"] [data-testid="stMetricDelta"] * {{ color:{ACCENT2} !important; }}
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{ color:#8FA3BD !important; }}
</style>
""", unsafe_allow_html=True)


# ============================================================================
# 2. CONSTANTES MÉTIER
# ============================================================================
# Liste exhaustive des corps d'état. Chacun est facultatif : il n'apparaît dans
# les calculs et les PDF que si l'utilisateur y ajoute au moins une ligne.
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

# Unités proposées par défaut pour chaque ligne
UNITES = ["m²", "ml", "u", "h", "forfait", "kg", "L"]

# Coefficients de majoration géographique
ZONES = {
    "Zone A  (×1,00)": 1.00,
    "Zone B  (×1,15)": 1.15,
    "Zone C  (×1,25)": 1.25,
}

TVA_RATE = 0.10  # TVA travaux de rénovation après sinistre


# ============================================================================
# 3. FONCTIONS UTILITAIRES
# ============================================================================
def format_currency(value):
    """Formatage monétaire aux standards français : 1 234,56 €."""
    if value is None:
        value = 0.0
    return f"{value:,.2f}".replace(",", " ").replace(".", ",") + " €"


def validate_siret(siret):
    """Un SIRET valide comporte exactement 14 chiffres."""
    return len(re.sub(r"\D", "", str(siret))) == 14


def _parse_amount(raw):
    """Convertit '7 500,00' ou '7.500,00' ou '7500.00' en float. None si invalide."""
    s = re.sub(r"[^\d,.\s]", "", raw).strip()
    s = s.replace(" ", "")
    # Si la virgule est le séparateur décimal (format FR) : retirer les points
    # de milliers puis transformer la virgule en point.
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def extract_data_from_pdf(pdf_file):
    """
    Pré-remplissage automatique : lit le rapport d'expertise (PDF) et tente
    d'en extraire un maximum de champs (n° sinistre, compagnie, expert,
    référence, assuré, adresse, plafond HT).
    Tolérant : retourne uniquement ce qui a pu être trouvé avec confiance.
    Chaque libellé ci-dessous accepte de nombreuses variantes rencontrées dans
    les rapports réels (« N° de sinistre », « Réf. dossier », « Cabinet », …).
    """
    found = {}
    if not PDFPLUMBER_OK:
        return found
    try:
        with pdfplumber.open(pdf_file) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception as exc:
        st.warning(f"Lecture du PDF impossible : {exc}")
        return found

    # Normalisation légère pour fiabiliser les expressions régulières
    text = text.replace("\xa0", " ")

    def grab(patterns, group=1):
        """Renvoie la 1re capture non vide parmi une liste de motifs."""
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m and m.group(group).strip():
                return m.group(group).strip()
        return None

    # --- N° de sinistre / dossier (alphanumérique avec tirets) ---
    claim = grab([
        r"(?:n[°o]\s*(?:de\s*)?sinistre|sinistre\s*n[°o]?)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/]{4,20})",
        r"(?:r[ée]f(?:[ée]rence)?\.?\s*(?:dossier)?|dossier)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/]{4,20})",
    ])
    if claim:
        found["claim_number"] = claim

    # --- Référence du rapport d'expertise ---
    ref = grab([
        r"(?:r[ée]f\.?\s*(?:expert|rapport)|n[°o]\s*rapport)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/]{3,20})",
    ])
    if ref:
        found["expert_ref"] = ref

    # --- Cabinet d'expertise (séparateur obligatoire pour éviter « EXPERTISE ») ---
    expert = grab([
        r"(?:cabinet|expert(?:\s*missionn[ée])?)\b\s*[:\-]\s*([A-Za-zÀ-ÿ0-9'’&\.\- ]{4,40})",
    ])
    if expert:
        # On coupe à un éventuel saut de ligne capturé
        found["expert_name"] = re.split(r"\s{2,}|\n", expert)[0].strip()

    # --- Compagnie d'assurance ---
    insurer = grab([
        r"(?:compagnie|assureur|assurance)\b\s*[:\-]\s*([A-Za-zÀ-ÿ0-9'’&\.\- ]{3,40})",
    ])
    if insurer:
        found["insurance_name"] = re.split(r"\s{2,}|\n", insurer)[0].strip()

    # --- Assuré ---
    client = grab([
        r"(?:assur[ée]|client|b[ée]n[ée]ficiaire)\b\s*[:\-]\s*([A-Za-zÀ-ÿ0-9'’&\.\- ]{3,40})",
    ])
    if client:
        found["client_name"] = re.split(r"\s{2,}|\n", client)[0].strip()

    # --- Adresse du chantier / du bien ---
    address = grab([
        r"(?:adresse\s*(?:du\s*(?:chantier|bien|sinistre))?|lieu\s*du\s*sinistre)\s*[:\-]?\s*"
        r"([0-9].{6,60}?\d{5}\s+[A-Za-zÀ-ÿ\- ]{2,30})",
    ])
    if address:
        found["address"] = re.split(r"\n", address)[0].strip()

    # --- Plafond / montant HT estimé par l'expert ---
    raw_amount = grab([
        r"(?:total|montant|estimation|plafond)\s*(?:g[ée]n[ée]ral\s*)?HT\s*[:\-]?\s*"
        r"([\d][\d\s. ]*[.,]\d{2})",
        r"HT\s*[:\-]?\s*([\d][\d\s. ]*[.,]\d{2})\s*€?",
    ])
    if raw_amount:
        amount = _parse_amount(raw_amount)
        if amount and amount > 0:
            found["expert_ht"] = amount

    return found


# ============================================================================
# 4. ÉTAT DE SESSION (persistance des saisies)
# ============================================================================
# 4.a — Exemples affichés en GRIS (placeholder) dans chaque champ texte.
# Ce ne sont PAS des valeurs réelles : ils guident la saisie et disparaissent
# dès que l'utilisateur tape — rien à effacer. Si un champ reste vide, son
# exemple est repris tel quel dans les PDF générés (pour une démo cohérente).
PLACEHOLDERS = {
    # Entité émettrice (entreprise)
    "company_name": "SMARTSITE RÉFECTION SAS",
    "company_address": "75 Avenue des Champs-Élysées, 75008 Paris",
    "company_siret": "12345678901234",
    "company_tva": "FR12123456789",
    # Dossier / sinistre
    "client_name": "Société Immobilière Horizon",
    "address": "14 Avenue de la République, 75011 Paris",
    "insurance_name": "Allianz France",
    "claim_number": "ALZ-2026-9941X",
    "expert_name": "Cabinet Texa Évolution",
    "expert_ref": "EXP-55214-REV",
}
# Les champs texte démarrent VIDES → l'exemple gris (placeholder) s'affiche.
for _k in PLACEHOLDERS:
    st.session_state.setdefault(_k, "")

# 4.a bis — Vraies valeurs par défaut des widgets non-texte (pas de placeholder
# possible sur un selectbox / slider, donc on garde une valeur initiale).
ADMIN_DEFAULTS = {
    "zone_select": list(ZONES.keys())[1],   # Zone B par défaut
    "expert_ht": 7500.0,
    "target_margin": 35.0,
}
for _k, _v in ADMIN_DEFAULTS.items():
    st.session_state.setdefault(_k, _v)

# 4.b — Structure des lignes de chiffrage : { code_corps: [id_ligne, ...] }
if "lots" not in st.session_state:
    st.session_state.lots = {code: [] for _, code in CORPS_METIER}
if "line_counter" not in st.session_state:
    st.session_state.line_counter = 0

# 4.c — Navigation & documents générés
st.session_state.setdefault("nav_step", "Étape 1 · Import / Admin")
st.session_state.setdefault("generated", None)   # {fiche, devis, lettre, metrics}
st.session_state.setdefault("pdf_parsed", False)


def add_line(code, desc="", unite="m²", qte=None, achat=None, vente=None):
    """Ajoute une ligne à un corps de métier et initialise ses widgets.
    Par défaut les valeurs numériques sont None : les champs s'affichent VIDES
    (avec un placeholder gris), donc rien à effacer avant de saisir."""
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
    """Supprime une ligne et nettoie ses clés de session."""
    if lid in st.session_state.lots[code]:
        st.session_state.lots[code].remove(lid)
    for suffix in ("desc", "unite", "qte", "achat", "vente"):
        st.session_state.pop(f"{code}_{lid}_{suffix}", None)


# 4.d — Au tout premier lancement : une seule ligne VIERGE pour montrer la
# structure (placeholders gris). Aucune valeur pré-remplie à effacer.
if "seeded" not in st.session_state:
    add_line("Platrerie")
    st.session_state.seeded = True


# ============================================================================
# 5. MOTEUR DE CALCUL
# ============================================================================
def collect_lines():
    """Reconstruit la liste à plat de toutes les lignes saisies (qte > 0)."""
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
                "corps": label_by_code[code].split(" ", 1)[-1],  # libellé lisible
                "desc": desc or label_by_code[code],
                "unite": unite,
                "qte": qte,
                "achat": achat,
                "vente": vente,
                "total_achat": qte * achat,
                "total_vente": qte * vente,
            })
    return rows


def compute(rows, zone_coeff, expert_ht, target_margin):
    """Agrège les totaux, la marge réelle et l'écart avec le plafond expert."""
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

    # Statut de conformité vis-à-vis du plafond expert
    if variance_pct <= 5.0:
        status, color = "CONFORME", SUCCESS
        msg = "Le devis respecte parfaitement le plafond de l'expert. Prêt à l'envoi."
    elif variance_pct <= 15.0:
        status, color = "VIGILANCE", WARNING
        msg = "Léger dépassement de l'enveloppe expert : une justification sera incluse dans la lettre."
    else:
        status, color = "HORS BUDGET", DANGER
        msg = "Écart critique : risque de refus de l'assurance. Ajustez la marge ou vérifiez les métrés."

    return {
        "subtotal_vente": subtotal_vente, "final_ht": final_ht, "tva": tva, "ttc": ttc,
        "total_achat": total_achat, "cost_total": cost_total,
        "margin_eur": margin_eur, "margin_pct": margin_pct,
        "variance_eur": variance_eur, "variance_pct": variance_pct,
        "status": status, "color": color, "msg": msg,
        "zone_coeff": zone_coeff, "expert_ht": expert_ht, "target_margin": target_margin,
    }


# ============================================================================
# 6. GÉNÉRATION DES PDF (ReportLab)
# ============================================================================
def get_pdf_styles():
    """Feuille de styles ReportLab cohérente avec la charte écran."""
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("DocTitle", parent=styles["Heading1"],
               fontName="Helvetica-Bold", fontSize=17, leading=21,
               textColor=colors.HexColor(NAVY), alignment=TA_CENTER, spaceAfter=14))
    styles.add(ParagraphStyle("SectionHeader", parent=styles["Heading2"],
               fontName="Helvetica-Bold", fontSize=12, leading=16,
               textColor=colors.HexColor(ANTHRACITE), spaceBefore=12, spaceAfter=8))
    styles.add(ParagraphStyle("Body", parent=styles["Normal"],
               fontName="Helvetica", fontSize=10, leading=14,
               textColor=colors.HexColor("#333333"), alignment=TA_JUSTIFY, spaceAfter=10))
    styles.add(ParagraphStyle("BodyBold", parent=styles["Body"], fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle("Right", parent=styles["Normal"],
               fontName="Helvetica", fontSize=10, leading=14, alignment=TA_RIGHT))
    styles.add(ParagraphStyle("Confidential", parent=styles["Normal"],
               fontName="Helvetica-Bold", fontSize=11, leading=14,
               textColor=colors.HexColor(DANGER), alignment=TA_CENTER, spaceAfter=10))
    return styles


def _company_header_paragraph(d, styles):
    """En-tête entreprise réutilisable, alimenté dynamiquement par le SIRET saisi."""
    return Paragraph(
        f"<b>{d['company_name']}</b><br/>{d['company_address']}<br/>"
        f"SIRET : {d['company_siret']} &nbsp;|&nbsp; TVA : {d['company_tva']}",
        styles["Body"],
    )


def build_fiche_interne(d, rows, calc):
    """PDF 1 — Fiche interne confidentielle : coûts de revient vs barème, marge."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=45, rightMargin=45,
                            topMargin=45, bottomMargin=45)
    s = get_pdf_styles()
    story = [
        Paragraph("DOCUMENT INTERNE STRICTEMENT CONFIDENTIEL", s["Confidential"]),
        Paragraph("FICHE DE PRÉPARATION & ANALYSE DE RENTABILITÉ CHANTIER", s["DocTitle"]),
        Spacer(1, 12),
    ]

    info = [
        [Paragraph("<b>PROJET & CLIENT</b>", s["BodyBold"]),
         Paragraph("<b>RÉFÉRENCES SINISTRE</b>", s["BodyBold"])],
        [Paragraph(f"Assuré : {d['client_name']}<br/>Adresse : {d['address']}", s["Body"]),
         Paragraph(f"Compagnie : {d['insurance_name']}<br/>N° Sinistre : {d['claim_number']}"
                   f"<br/>Expert : {d['expert_name']} ({d['expert_ref']})", s["Body"])],
    ]
    t = Table(info, colWidths=[250, 250])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAEDED")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ("PADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story += [t, Spacer(1, 18),
              Paragraph("Analyse financière détaillée et coûts de revient", s["SectionHeader"])]

    data = [["Poste", "Qté", "Revient unit.", "Total revient", "Revente unit.", "Total revente"]]
    for r in rows:
        data.append([
            r["desc"], f"{r['qte']:g} {r['unite']}",
            format_currency(r["achat"]), format_currency(r["total_achat"]),
            format_currency(r["vente"]), format_currency(r["total_vente"]),
        ])
    data.append(["SOUS-TOTAL (barème)", "", "", format_currency(calc["total_achat"]),
                 "", format_currency(calc["subtotal_vente"])])
    data.append([f"Ajustement zone (×{calc['zone_coeff']:g})", "", "",
                 format_currency(calc["cost_total"]), "",
                 format_currency(calc["final_ht"])])
    data.append(["TOTAL GÉNÉRAL HT", "", "", format_currency(calc["cost_total"]),
                 "", format_currency(calc["final_ht"])])

    t = Table(data, colWidths=[150, 55, 75, 75, 75, 75])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(ANTHRACITE)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ("FONTNAME", (0, -3), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F2F4F4")),
        ("PADDING", (0, 0), (-1, -1), 6), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
    ]))
    story += [t, Spacer(1, 18),
              Paragraph("Indicateurs de rentabilité stratégique", s["SectionHeader"])]

    perf = (
        f"<b>Coût de revient total brut :</b> {format_currency(calc['cost_total'])}<br/>"
        f"<b>Chiffre d'affaires prévisionnel HT :</b> {format_currency(calc['final_ht'])}<br/>"
        f"<b>Marge commerciale réelle dégagée :</b> {format_currency(calc['margin_eur'])}<br/>"
        f"<b>Taux de marge réelle :</b> {calc['margin_pct']:.2f} % "
        f"<i>(objectif cible : {calc['target_margin']:.2f} %)</i>"
    )
    story.append(Paragraph(perf, s["Body"]))
    if calc["margin_pct"] < calc["target_margin"]:
        story += [Spacer(1, 8), Paragraph(
            "⚠️ ALERTE RENTABILITÉ : la marge réelle est inférieure à votre objectif cible. "
            "Surveillez attentivement les coûts d'exécution sur le chantier.", s["Confidential"])]

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def build_devis_conforme(d, rows, calc):
    """PDF 2 — Devis officiel conforme, en-tête entité (SIRET dynamique)."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=45, rightMargin=45,
                            topMargin=45, bottomMargin=45)
    s = get_pdf_styles()
    story = []

    head = [[_company_header_paragraph(d, s),
             Paragraph(f"<b>DEVIS OFFICIEL</b><br/>N° DEV-{datetime.date.today():%Y%m}-01"
                       f"<br/>Date : {datetime.date.today():%d/%m/%Y}<br/>Validité : 90 jours",
                       s["Right"])]]
    story += [Table(head, colWidths=[300, 200]), Spacer(1, 16),
              Paragraph("DEVIS DE RÉFECTION CONFORME APRÈS SINISTRE", s["DocTitle"]), Spacer(1, 8)]

    client = [
        [Paragraph("<b>DESTINATAIRE / ASSURÉ</b>", s["BodyBold"]),
         Paragraph("<b>CONTEXTE SINISTRE & EXPERTISE</b>", s["BodyBold"])],
        [Paragraph(f"{d['client_name']}<br/>{d['address']}", s["Body"]),
         Paragraph(f"Compagnie : {d['insurance_name']}<br/>N° Sinistre : {d['claim_number']}"
                   f"<br/>Cabinet : {d['expert_name']}<br/>Réf. expert : {d['expert_ref']}", s["Body"])],
    ]
    t = Table(client, colWidths=[250, 250])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(ANTHRACITE)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ("PADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story += [t, Spacer(1, 18),
              Paragraph("Désignation des travaux de réfection", s["SectionHeader"])]

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

    t = Table(data, colWidths=[270, 70, 80, 80])
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(ANTHRACITE)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"), ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ("PADDING", (0, 0), (-1, -1), 6), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EAECEE")),
    ]
    for i in range(len(data) - 5, len(data)):  # gras sur les lignes de totaux
        style.append(("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"))
    t.setStyle(TableStyle(style))
    story += [t, Spacer(1, 36)]

    sig = [[Paragraph("<b>Cadre réservé à l'entreprise</b><br/>Pour la direction technique<br/>"
                      "Bon pour exécution", s["Body"]),
            Paragraph("<b>Bon pour accord client / compagnie</b><br/>Date, signature et mention<br/>"
                      "« Lu et approuvé – Bon pour accord »", s["Body"])]]
    t = Table(sig, colWidths=[250, 250])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.HexColor("#7F8C8D")),
                           ("PADDING", (0, 0), (-1, -1), 10), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(t)

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def build_lettre_expert(d, rows, calc):
    """PDF 3 — Lettre d'accompagnement à l'expert, paragraphe conditionnel par statut."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=50, rightMargin=50,
                            topMargin=50, bottomMargin=50)
    s = get_pdf_styles()
    story = [_company_header_paragraph(d, s), Spacer(1, 14)]

    dest = (f"<b>Cabinet d'expertise :</b> {d['expert_name']}<br/>"
            f"À l'attention de l'expert en charge<br/>"
            f"<b>Réf. dossier :</b> {d['expert_ref']}")
    story += [Table([[Spacer(1, 1), Paragraph(dest, s["Body"])]], colWidths=[250, 250]),
              Spacer(1, 18),
              Paragraph(f"Fait à Paris, le {datetime.date.today():%d/%m/%Y}", s["Right"]),
              Spacer(1, 12)]

    obj = (f"<b>Objet :</b> Proposition de chiffrage de réfection suite à sinistre<br/>"
           f"<b>N° de sinistre :</b> {d['claim_number']}<br/>"
           f"<b>Assuré :</b> {d['client_name']}<br/>"
           f"<b>Adresse :</b> {d['address']}")
    story += [Paragraph(obj, s["Body"]), Spacer(1, 12),
              Paragraph("Madame, Monsieur l'Expert,", s["Body"]), Spacer(1, 6)]

    story.append(Paragraph(
        "Dans le cadre du dossier référencé ci-dessus, nous avons l'honneur de vous soumettre "
        "notre proposition de chiffrage pour les travaux de remise en état. Notre étude a été "
        "dressée en respectant les métrés et volumes d'intervention validés lors de votre expertise.",
        s["Body"]))
    story.append(Paragraph(
        f"Notre devis s'établit à un montant total de <b>{format_currency(calc['final_ht'])} HT</b>, "
        f"soit <b>{format_currency(calc['ttc'])} TTC</b> après application de la TVA réglementaire "
        f"de {TVA_RATE*100:.0f} % dédiée aux travaux de rénovation après sinistre.", s["Body"]))

    # Paragraphe conditionnel selon la conformité budgétaire
    if calc["status"] == "VIGILANCE":
        cond = ("<b>Note de justification technique :</b> ce chiffrage présente un léger ajustement "
                "par rapport à votre première enveloppe estimative, motivé par les spécificités des "
                "supports identifiés et par les contraintes géographiques et logistiques du chantier, "
                "justifiant l'application de notre barème actualisé de zone.")
    elif calc["status"] == "HORS BUDGET":
        cond = ("<b>Note d'analyse de conformité budgétaire :</b> constatant un écart significatif avec "
                "l'évaluation initiale, nous précisons que les contraintes d'exécution réelles et les "
                "exigences de mise en œuvre imposent cette réévaluation. Nous sollicitons une révision "
                "bienveillante du dossier afin de permettre un démarrage rapide des travaux dans "
                "l'intérêt de l'assuré.")
    else:
        cond = ("Nous constatons avec satisfaction que notre proposition s'inscrit en parfaite adéquation "
                "avec vos évaluations initiales, ce qui démontre la stricte conformité technique de notre "
                "offre par rapport aux attendus de votre cabinet.")
    story += [Spacer(1, 4), Paragraph(cond, s["Body"]), Spacer(1, 8)]

    story += [
        Paragraph("Nous restons à votre entière disposition pour tout justificatif complémentaire "
                  "nécessaire à la validation définitive de ce dossier d'indemnisation.", s["Body"]),
        Spacer(1, 6),
        Paragraph("Veuillez agréer, Madame, Monsieur l'Expert, l'expression de nos salutations "
                  "distinguées.", s["Body"]),
        Spacer(1, 28),
        Paragraph(f"<b>{d['company_name']}</b><br/>Département de réhabilitation après sinistre", s["Body"]),
    ]

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


# ============================================================================
# 7. COMPOSANTS D'INTERFACE RÉUTILISABLES
# ============================================================================
def kpi_card(label, value, sub="", accent=None):
    """Carte KPI high-tech. `accent` (optionnel) colore le liseré supérieur."""
    style = f"--kpi-accent:{accent};" if accent else ""
    return f"""
    <div class="kpi" style="{style}">
        <div class="label">{label}</div>
        <div class="value">{value}</div>
        <div class="sub">{sub}</div>
    </div>"""


def status_banner(calc):
    """Bandeau de statut de conformité coloré."""
    st.markdown(f"""
    <div class="status-box" style="background:{calc['color']}1A; border-left:6px solid {calc['color']};">
        <h4 style="color:{calc['color']};">Statut du dossier : {calc['status']}</h4>
        <p>{calc['msg']}</p>
    </div>""", unsafe_allow_html=True)


# --- Définition des étapes du workflow (ordre = navigation) ---
STEPS = [
    "Étape 1 · Import / Admin",
    "Étape 2 · Chiffrage par lots",
    "Étape 3 · Génération & Dashboard",
]
STEP_TITLES = ["Import / Admin", "Chiffrage par lots", "Génération & Dashboard"]


def _goto_step(target):
    """Callback de navigation : change l'étape et demande un défilement en haut."""
    st.session_state.nav_step = target
    st.session_state._scroll_top = True


def render_breadcrumb(active_index):
    """Fil d'Ariane visuel 1 → 2 → 3 + barre de progression animée."""
    # Barre de progression (proportionnelle à l'étape courante)
    pct = int((active_index + 1) / len(STEPS) * 100)
    st.markdown(f"<div class='tech-progress'><span style='width:{pct}%'></span></div>",
                unsafe_allow_html=True)
    items = ""
    for i, title in enumerate(STEP_TITLES):
        if i == active_index:
            cls = "crumb active"
        elif i < active_index:
            cls = "crumb done"
        else:
            cls = "crumb"
        mark = "✓" if i < active_index else str(i + 1)
        items += f"<div class='{cls}'><span class='n'>{mark}</span><span class='t'>{title}</span></div>"
    st.markdown(f"<div class='crumbs'>{items}</div>", unsafe_allow_html=True)


def render_nav_buttons(active_index):
    """Boutons « Précédent » / « Suivant » en bas de chaque étape."""
    st.divider()
    prev_c, mid_c, next_c = st.columns([1, 2, 1])
    if active_index > 0:
        prev_c.button("← Étape précédente", width="stretch",
                      on_click=_goto_step, args=(STEPS[active_index - 1],),
                      key=f"prev_{active_index}")
    if active_index < len(STEPS) - 1:
        next_c.button("Étape suivante →", type="primary", width="stretch",
                      on_click=_goto_step, args=(STEPS[active_index + 1],),
                      key=f"next_{active_index}")


def scroll_to_top_if_needed():
    """Fait défiler la page en haut juste après un changement d'étape."""
    if st.session_state.pop("_scroll_top", False):
        components.html(
            """
            <script>
                const doc = window.parent.document;
                const target = doc.querySelector('section.main')
                            || doc.querySelector('[data-testid="stMain"]')
                            || doc.scrollingElement || doc.documentElement;
                if (target) { target.scrollTo({top: 0, behavior: 'smooth'}); }
                window.parent.scrollTo({top: 0, behavior: 'smooth'});
            </script>
            """,
            height=0,
        )


# ============================================================================
# 8. EN-TÊTE & NAVIGATION (SIDEBAR)
# ============================================================================
st.markdown(f"""
<div class="hero">
    <span class="live"><span class="dot"></span> SYSTÈME OPÉRATIONNEL</span>
    <h1>🏛️ Gestionnaire Stratégique de Sinistres</h1>
    <p>Chiffrage par corps de métier · Analyse de marge · Conformité expert · Génération documentaire</p>
</div>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🧭 Navigation")
    st.radio("Étapes du workflow", STEPS, key="nav_step", label_visibility="collapsed")

    st.divider()

    # Récapitulatif live (mis à jour à chaque interaction)
    _rows = collect_lines()
    _zc = ZONES[st.session_state["zone_select"]]
    _calc = compute(_rows, _zc, st.session_state["expert_ht"], st.session_state["target_margin"])
    st.markdown("### 📊 Récapitulatif live")
    st.metric("Total HT proposé", format_currency(_calc["final_ht"]))
    st.metric("Marge réelle", f"{_calc['margin_pct']:.1f} %",
              f"{format_currency(_calc['margin_eur'])}")
    st.caption(f"{len(_rows)} ligne(s) active(s) · Zone ×{_zc:g}")


# ============================================================================
# 9. ÉTAPE 1 — IMPORT / ADMIN
# ============================================================================
def render_step1():
    st.subheader("Étape 1 — Import du rapport & informations administratives")

    # --- Bloc import PDF (extraction automatique) ---
    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("##### 📂 Import du rapport d'expertise (optionnel)")
        if not PDFPLUMBER_OK:
            st.caption("Module d'extraction PDF indisponible (pdfplumber non installé) — "
                       "la saisie manuelle ci-dessous reste pleinement opérationnelle.")
        up = st.file_uploader("Déposez le rapport PDF pour pré-remplir les champs", type=["pdf"])
        if up is not None and not st.session_state.pdf_parsed:
            with st.spinner("Analyse du document et extraction des données clés…"):
                info = extract_data_from_pdf(up)
            # On remplit TOUS les champs reconnus (pas seulement 3).
            fillable = ("claim_number", "expert_ref", "expert_name",
                        "insurance_name", "client_name", "address", "expert_ht")
            applied = []
            labels = {
                "claim_number": "N° sinistre", "expert_ref": "Réf. expert",
                "expert_name": "Cabinet d'expertise", "insurance_name": "Compagnie",
                "client_name": "Assuré", "address": "Adresse", "expert_ht": "Plafond HT",
            }
            for key in fillable:
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
                st.info("Aucune donnée exploitable détectée automatiquement. "
                        "Complétez les champs manuellement ci-dessous.")
            if st.button("↻ Réinitialiser l'import PDF"):
                st.session_state.pdf_parsed = False
                st.session_state.pop("pdf_applied", None)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # --- Bloc entité émettrice (le SIRET alimente l'en-tête des PDF) ---
    st.markdown("##### 🏢 Entité émettrice (conformité légale du devis)")
    c1, c2 = st.columns(2)
    with c1:
        st.text_input("Raison sociale", key="company_name",
                      placeholder=PLACEHOLDERS["company_name"])
        st.text_input("Adresse du siège", key="company_address",
                      placeholder=PLACEHOLDERS["company_address"])
    with c2:
        st.text_input("Numéro SIRET", key="company_siret", max_chars=20,
                      placeholder=PLACEHOLDERS["company_siret"],
                      help="14 chiffres. Les espaces et tirets sont acceptés.")
        st.text_input("N° TVA intracommunautaire", key="company_tva",
                      placeholder=PLACEHOLDERS["company_tva"])

    # Le SIRET accepte espaces et tirets (max_chars élargi). La validation est
    # purement INDICATIVE : elle n'empêche jamais la génération des documents.
    if st.session_state["company_siret"].strip() == "":
        st.caption("Le SIRET sera repris tel quel dans l'en-tête des documents.")
    elif validate_siret(st.session_state["company_siret"]):
        st.caption("✅ SIRET valide — repris automatiquement dans l'en-tête de chaque document.")
    else:
        st.info("ℹ️ Format SIRET inhabituel (14 chiffres attendus). "
                "Vous pouvez tout de même générer vos documents.")

    st.divider()

    # --- Bloc dossier / sinistre / expert ---
    st.markdown("##### 📁 Dossier client & sinistre")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.text_input("Nom de l'assuré *", key="client_name",
                      placeholder=PLACEHOLDERS["client_name"])
        st.text_input("Adresse du chantier *", key="address",
                      placeholder=PLACEHOLDERS["address"])
    with c2:
        st.text_input("Compagnie d'assurance *", key="insurance_name",
                      placeholder=PLACEHOLDERS["insurance_name"])
        st.text_input("Numéro de sinistre *", key="claim_number",
                      placeholder=PLACEHOLDERS["claim_number"])
    with c3:
        st.text_input("Cabinet d'expertise *", key="expert_name",
                      placeholder=PLACEHOLDERS["expert_name"])
        st.text_input("Référence rapport expert *", key="expert_ref",
                      placeholder=PLACEHOLDERS["expert_ref"])

    st.markdown("##### 🌍 Zone géographique")
    zc1, _ = st.columns([1, 2])
    with zc1:
        st.selectbox("Coefficient géographique", list(ZONES.keys()), key="zone_select",
                     help="Zone A ×1,00 · Zone B ×1,15 · Zone C ×1,25")

    st.info("Passez à l'**Étape 2** (menu de gauche) pour chiffrer les travaux par corps de métier.")


# ============================================================================
# 10. ÉTAPE 2 — CHIFFRAGE PAR LOTS (dynamique, temps réel)
# ============================================================================
def render_step2():
    st.subheader("Étape 2 — Chiffrage par corps de métier")
    st.caption("Chaque lot est facultatif. Dépliez un corps de métier et cliquez sur "
               "« ➕ Ajouter une ligne » pour le chiffrer. Les totaux se recalculent en temps réel.")

    label_by_code = {code: label for label, code in CORPS_METIER}

    for label, code in CORPS_METIER:
        ids = st.session_state.lots[code]
        # Total du lot pour l'afficher dans le titre de l'expander
        lot_total = sum(
            float(st.session_state.get(f"{code}_{i}_qte", 0) or 0)
            * float(st.session_state.get(f"{code}_{i}_vente", 0) or 0)
            for i in ids
        )
        suffix = f"  —  {len(ids)} ligne(s) · {format_currency(lot_total)}" if ids else "  —  vide"
        with st.expander(label + suffix, expanded=bool(ids)):

            # En-tête de colonnes (affiché seulement s'il y a des lignes)
            if ids:
                h = st.columns([3, 1.1, 1, 1.3, 1.3, 1.5, 0.6])
                for col, name in zip(h, ["Description", "Qté", "Unité", "Prix achat",
                                         "Prix vente", "Total vente", ""]):
                    col.markdown(f"<div class='col-head'>{name}</div>", unsafe_allow_html=True)

            # Lignes dynamiques
            for lid in list(ids):
                c = st.columns([3, 1.1, 1, 1.3, 1.3, 1.5, 0.6])
                c[0].text_input("Description", key=f"{code}_{lid}_desc",
                                label_visibility="collapsed",
                                placeholder="Ex : Reprise plâtrerie et enduits…")
                qte = c[1].number_input("Qté", min_value=0.0, step=1.0,
                                        key=f"{code}_{lid}_qte", label_visibility="collapsed",
                                        placeholder="0")
                c[2].selectbox("Unité", UNITES, key=f"{code}_{lid}_unite",
                               label_visibility="collapsed")
                c[3].number_input("Achat", min_value=0.0, step=0.5,
                                  key=f"{code}_{lid}_achat", label_visibility="collapsed",
                                  placeholder="0,00")
                vente = c[4].number_input("Vente", min_value=0.0, step=0.5,
                                          key=f"{code}_{lid}_vente", label_visibility="collapsed",
                                          placeholder="0,00")
                # Total de la ligne (les champs vides valent 0 sans erreur)
                ligne_total = (qte or 0) * (vente or 0)
                c[5].markdown(
                    f"<div style='padding-top:6px;font-weight:700;color:{NAVY};'>"
                    f"{format_currency(ligne_total)}</div>", unsafe_allow_html=True)
                if c[6].button("🗑", key=f"{code}_{lid}_del", help="Supprimer la ligne"):
                    remove_line(code, lid)
                    st.rerun()

            # Bouton d'ajout
            if st.button(f"➕ Ajouter une ligne", key=f"add_{code}"):
                add_line(code, desc="", unite="m²")
                st.rerun()

    st.divider()

    # Total général live
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
# 11. ÉTAPE 3 — GÉNÉRATION & DASHBOARD
# ============================================================================
def render_step3():
    st.subheader("Étape 3 — Génération & tableau de bord")

    rows = collect_lines()

    # --- Paramètres d'analyse (impactent le dashboard en temps réel) ---
    st.markdown("##### 🎯 Paramètres d'analyse")
    p1, p2 = st.columns(2)
    with p1:
        st.number_input("Plafond estimé par l'expert (HT en €) *", min_value=0.0,
                        step=50.0, key="expert_ht")
    with p2:
        st.slider("Objectif de marge commerciale (%)", min_value=10.0, max_value=60.0,
                  step=0.5, key="target_margin")

    zc = ZONES[st.session_state["zone_select"]]
    calc = compute(rows, zc, st.session_state["expert_ht"], st.session_state["target_margin"])

    st.divider()
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

    # --- Tableau récapitulatif des lignes ---
    if rows:
        st.markdown("##### 📋 Détail du chiffrage retenu")
        st.dataframe(
            [{"Corps de métier": r["corps"], "Description": r["desc"],
              "Qté": f"{r['qte']:g} {r['unite']}",
              "PU vente": format_currency(r["vente"]),
              "Total HT": format_currency(r["total_vente"])} for r in rows],
            width="stretch", hide_index=True,
        )
    else:
        st.warning("Aucune ligne chiffrée. Revenez à l'**Étape 2** pour ajouter des travaux.")

    st.divider()

    # --- Génération des documents ---
    st.markdown("### 🗂️ Génération du dossier")
    # Le SIRET n'est PLUS bloquant : seuls les champs réellement indispensables
    # à un dossier exploitable conditionnent la génération.
    blocking = (not rows
                or not st.session_state["client_name"].strip()
                or not st.session_state["claim_number"].strip()
                or st.session_state["expert_ht"] <= 0)

    if blocking:
        st.error("❌ Génération impossible : il faut au moins une ligne chiffrée, "
                 "un nom d'assuré, un numéro de sinistre et un plafond expert > 0.")

    if st.button("🔥 Générer le dossier complet (3 PDF)", type="primary", disabled=blocking):
        # Un champ laissé vide reprend son exemple gris (placeholder) pour que
        # l'en-tête des PDF ne comporte jamais de trou.
        d = {k: (st.session_state[k].strip() or PLACEHOLDERS.get(k, ""))
             for k in
             ("company_name", "company_address", "company_siret", "company_tva",
              "client_name", "address", "insurance_name", "claim_number",
              "expert_name", "expert_ref")}
        with st.spinner("Compilation des documents conformes…"):
            st.session_state.generated = {
                "fiche": build_fiche_interne(d, rows, calc),
                "devis": build_devis_conforme(d, rows, calc),
                "lettre": build_lettre_expert(d, rows, calc),
                "claim": st.session_state["claim_number"],
            }
        st.success("🎉 Les 3 documents ont été générés. Téléchargez-les ci-dessous.")

    # --- Zone de téléchargement (persistante après chaque clic) ---
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
# 12. ROUTAGE DU WORKFLOW
# ============================================================================
scroll_to_top_if_needed()                       # Défilement en haut après navigation

active_index = STEPS.index(st.session_state["nav_step"])
render_breadcrumb(active_index)                  # Fil d'Ariane 1 → 2 → 3

if active_index == 0:
    render_step1()
elif active_index == 1:
    render_step2()
else:
    render_step3()

render_nav_buttons(active_index)                 # Boutons Précédent / Suivant
