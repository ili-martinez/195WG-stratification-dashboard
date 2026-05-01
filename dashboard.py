"""
pages/dashboard.py  —  Main career dashboard (Individual Profile, Squadron
                        Overview, Force Development).

Exported symbols used by app.py:
    run()         — renders the active page
    apply_theme() — injects CSS (must be called before any sidebar content)
    show_logo()   — renders the unit logo
"""

import streamlit as st
import streamlit.components.v1 as _components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────────────
DATA_FILE = "career_dashboard_data_latest.csv"  # kept for local fallback
LOGO_FILE  = "149_IS_logo.png"

RANK_ORDER = ["Amn", "A1C", "SrA", "SSgt", "TSgt", "MSgt", "SMSgt", "CMSgt"]
BOARD_RANKS = ["SSgt", "TSgt", "MSgt", "SMSgt"]

PME_FIELDS = [
    ("PME_ALS",    "ALS"),
    ("PME_NCOA",   "NCOA"),
    ("PME_SNCOA",  "SNCOA"),
    ("PME_EJPME1", "EJPME I"),
    ("PME_EJPME2", "EJPME II"),
    ("PME_SNCOE",  "SNCOE"),
    ("PME_EDO",    "EDO"),
    ("PME_CMSOC",  "CMSOC"),
    ("PME_CLC",    "CLC"),
    ("PME_DSCA1",  "DSCA I"),
    ("PME_DSCA2",  "DSCA II"),
]

EDU_FIELDS = [
    ("EDU_ASSOCIATES", "CCAF/Associates"),
    ("EDU_BACHELORS",  "Bachelors"),
    ("EDU_MASTERS",    "Masters"),
    ("EDU_DOCTORATE",  "Doctorate"),
]

ASSIGNMENT_OPTIONS = [
    "TDY/Exercise", "Deployment", "Mobilization",
    "Stat Tour", "ADOS", "WIT Team", "Group Staff", "Wing Staff", "Joint Tour",
]

AWARD_OPTIONS = [
    "NGB/MAJCOM Level Individual Award",
    "Federal/State Decoration",
    "Wing/Group/Squadron Airman of the Quarter or Year",
]

LEADERSHIP_OPTIONS = [
    "Supervisor", "Program Manager", "Flight Chief", "Senior Enlisted Leader",
]

ORG_FIELDS = [
    ("Booster Club",   ["Amn","A1C","SrA","SSgt","TSgt","MSgt","SMSgt","CMSgt"]),
    ("Rising 6",       ["Amn","A1C","SrA","SSgt","TSgt"]),
    ("Top 3",          ["MSgt","SMSgt","CMSgt"]),
    ("Chief's Council",["CMSgt"]),
    ("CAL EANGUS",     ["Amn","A1C","SrA","SSgt","TSgt","MSgt","SMSgt","CMSgt"]),
    ("Other",          ["Amn","A1C","SrA","SSgt","TSgt","MSgt","SMSgt","CMSgt"]),
]

SKILL_LABELS = {
    "1": "1 Skill Level - Trainee",
    "3": "3 Skill Level - Apprentice",
    "5": "5 Skill Level - Journeyman",
    "7": "7 Skill Level - Craftsman",
    "9": "9 Skill Level - Superintendent",
}

DISPLAY_MAP = {
    "Rank": "Rank", "FirstName": "First Name", "LastName": "Last Name",
    "_unit_name": "Unit",
    "Flight": "Flight", "LastEval": "Last Eval",
    "PromoRecomm": "Promotion Recommendation", "LastACA": "Last ACA",
    "DOE": "Date of Entry", "TIG": "Time in Grade", "DOR": "Date of Rank",
    "TIS": "Time in Service", "DAFSC": "AFSC", "SkillLevel": "Skill Level", "Fitness": "Fitness",
    "Assignments": "Assignments", "AssignmentsDate": "Assignment Dates",
    "AwardsDecs": "Awards/Decorations", "AwardsDecsDate": "Award/Dec Dates",
    "ProfOrgMbr": "Professional Organizations", "LeadershipRoles": "Leadership Roles",
    "SupervisorNotes": "Supervisor Notes", "RateeNotes": "Ratee Notes",
    "LastEdit": "Last Modified",
}

COLORS = ["#1F2A8A", "#F2C400", "#C91F2C", "#6E93B6", "#4A66AC", "#C5A100"]


# ── Utility helpers ───────────────────────────────────────────────────────────
def safe_text(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def yn(v) -> bool:
    return safe_text(v).lower() == "yes"


def parse_date(v):
    s = safe_text(v)
    if not s:
        return None
    try:
        return pd.to_datetime(s).date()
    except Exception:
        return None


def format_dt(v) -> str:
    s = safe_text(v)
    if not s:
        return ""
    try:
        return pd.to_datetime(s).strftime("%m/%d/%Y %I:%M %p")
    except Exception:
        return s


def months_since(d) -> int:
    if not d:
        return 0
    today = date.today()
    return max(0, (today.year - d.year) * 12 + (today.month - d.month) - (1 if today.day < d.day else 0))


def split_list_field(v):
    s = safe_text(v)
    return [x.strip() for x in s.split(";") if x.strip()]


def join_list_field(items):
    return "; ".join(items)


def parse_keyed_dates(v):
    out = {}
    for item in split_list_field(v):
        if ":" in item:
            k, val = item.split(":", 1)
            out[k.strip()] = val.strip()
    return out


def join_keyed_dates(mapping):
    return "; ".join([f"{k}: {v}" for k, v in mapping.items() if safe_text(v)])


def prof_org_options(rank):
    return [name for name, ranks in ORG_FIELDS if rank in ranks]


# ── Scoring helpers ───────────────────────────────────────────────────────────
def rank_gate_pme(rank):
    out = []
    if rank in ["SrA", "SSgt"]:
        out.append(("PME_ALS", "ALS"))
    if rank in ["SSgt", "TSgt"]:
        out.append(("PME_NCOA", "NCOA"))
    if rank in ["MSgt", "SMSgt"]:
        out.append(("PME_SNCOA", "SNCOA"))
    if rank in ["SSgt", "TSgt", "MSgt", "SMSgt", "CMSgt"]:
        out.append(("PME_EJPME1", "EJPME I"))
    if rank in ["MSgt", "SMSgt", "CMSgt"]:
        out.append(("PME_EJPME2", "EJPME II"))
    if rank in ["MSgt", "SMSgt"]:
        out.append(("PME_SNCOE", "SNCOE"))
    if rank in ["MSgt", "SMSgt", "CMSgt"]:
        out.append(("PME_EDO", "EDO"))
    if rank == "CMSgt":
        out.extend([("PME_CMSOC", "CMSOC"), ("PME_CLC", "CLC")])
    if rank in ["A1C", "SrA", "SSgt", "TSgt", "MSgt", "SMSgt", "CMSgt"]:
        out.extend([("PME_DSCA1", "DSCA I"), ("PME_DSCA2", "DSCA II")])
    return out


def chart_pme_fields(rank):
    if rank == "SrA":   return [("PME_ALS", "ALS")]
    if rank == "SSgt":  return [("PME_ALS", "ALS"), ("PME_EJPME1", "EJPME I"), ("PME_NCOA", "NCOA")]
    if rank == "TSgt":  return [("PME_NCOA", "NCOA"), ("PME_EJPME1", "EJPME I")]
    if rank == "MSgt":  return [("PME_SNCOA", "SNCOA"), ("PME_EJPME1", "EJPME I"), ("PME_EJPME2", "EJPME II")]
    if rank == "SMSgt": return [("PME_SNCOA", "SNCOA"), ("PME_EJPME1", "EJPME I"), ("PME_EJPME2", "EJPME II")]
    return []


def highest_degree_label(row):
    for field, label in [("EDU_DOCTORATE","Doctorate"),("EDU_MASTERS","Masters"),
                          ("EDU_BACHELORS","Bachelors"),("EDU_ASSOCIATES","CCAF/Associates")]:
        if yn(row.get(field, "No")):
            return label
    return "None"


def higher_education_points(row):
    label = highest_degree_label(row)
    return {"Doctorate":5,"Masters":4,"Bachelors":3,"CCAF/Associates":1}.get(label,0), label


def pme_points(row):
    done = [label for field, label in rank_gate_pme(row["Rank"]) if yn(row.get(field,"No"))]
    return min(len(done), 5), done


def leadership_points(row):
    items = split_list_field(row.get("LeadershipRoles",""))
    sup = pm = fc = sel = 0
    for item in items:
        low = item.lower()
        digits = "".join(ch for ch in item if ch.isdigit())
        yrs = int(digits) if digits else 0
        if "supervisor" in low:       sup = max(sup, yrs)
        if "program manager" in low:  pm  = max(pm,  yrs)
        if "flight chief" in low:     fc  = max(fc,  yrs)
        if "senior enlisted leader" in low: sel = max(sel, yrs)
    if sel >= 2 or fc >= 2:  return 5, "2+ years Flight Chief or Senior Enlisted Leader"
    if pm  >= 1:             return 2, "1+ year Program Manager"
    if sup >= 3:             return 1, "3+ years Supervisor"
    return 0, "No leadership threshold met"


def promo_points(row):
    value = safe_text(row.get("PromoRecomm","Promote")) or "Promote"
    return {"Promote":1,"Must Promote":3,"Promote Now":5}.get(value,0), value


def fitness_points(row):
    value = safe_text(row.get("Fitness","Satisfactory")) or "Satisfactory"
    if row["Rank"] == "SSgt":                    return (5 if value=="Excellent" else 3), value
    if row["Rank"] in ["TSgt","MSgt","SMSgt"]:   return (5 if value=="Excellent" else 0), value
    return 0, value


def awards_points(row):
    items = split_list_field(row.get("AwardsDecs",""))
    dates = parse_keyed_dates(row.get("AwardsDecsDate",""))
    pts, detail = 0, []
    if "NGB/MAJCOM Level Individual Award" in items:
        pts += 5; detail.append("NGB/MAJCOM Award")
    if "Federal/State Decoration" in items:
        d = parse_date(dates.get("Federal/State Decoration",""))
        cutoff = pd.Timestamp.today().date().replace(year=max(1, pd.Timestamp.today().date().year - 3))
        if d and d >= cutoff:
            pts += 3; detail.append("Decoration within 3 years")
    if "Wing/Group/Squadron Airman of the Quarter or Year" in items:
        d = parse_date(dates.get("Wing/Group/Squadron Airman of the Quarter or Year",""))
        if d and d.year >= pd.Timestamp.today().date().year - 1:
            pts += 2; detail.append("Quarter/Year award within 2 calendar years")
    return min(pts, 5), ", ".join(detail) if detail else "None"


def assignments_points(row):
    items = split_list_field(row.get("Assignments",""))
    dates = parse_keyed_dates(row.get("AssignmentsDate",""))
    pts, detail = 0, []
    for label in ["TDY/Exercise","Deployment","Mobilization"]:
        if label in items:
            d = parse_date(dates.get(label,""))
            cutoff = pd.Timestamp.today().date().replace(year=max(1, pd.Timestamp.today().date().year - 2))
            if d and d >= cutoff:
                pts += 1; detail.append(f"{label} within 2 years")
    for label in ["Stat Tour","ADOS","WIT Team","Group Staff","Wing Staff","Joint Tour"]:
        if label in items:
            pts += 1; detail.append(f"{label} (1+ year qualifying assignment)")
    return min(pts, 3), ", ".join(detail) if detail else "None"


def scorecard_summary(row):
    if row["Rank"] in ["SSgt", "TSgt", "MSgt", "SMSgt"]:
        e,ed = higher_education_points(row); p,pdone = pme_points(row)
        l,ld = leadership_points(row);       d,dd    = promo_points(row)
        a,ad = awards_points(row);           f,fd    = fitness_points(row)
        s,sd = assignments_points(row)
        rubric = "SSgt to TSgt" if row["Rank"] == "SSgt" else "TSgt and Above"
        return rubric, [
            ("Higher Education",                e, 5, ed),
            ("Professional Military Education", p, 5, ", ".join(pdone) if pdone else "None"),
            ("Leadership",                      l, 5, ld),
            ("Primary Duty Performance",        d, 5, dd),
            ("Awards and Decorations",          a, 5, ad),
            ("Fitness",                         f, 5, fd),
            ("Assignments",                     s, 3, sd),
        ]
    return "Not Applicable", []


def score_table_df(cats):
    total     = sum(x[1] for x in cats)
    total_max = sum(x[2] for x in cats)
    df = pd.DataFrame([{"Category":c[0],"Total Score":c[1],"Max Score":c[2],"Detail":c[3]} for c in cats])
    df.loc[len(df)] = ["Total", total, total_max, ""]
    return df, total, total_max


# ── Theme ─────────────────────────────────────────────────────────────────────
def apply_theme():
    st.session_state["profile_note"] = "#f0c030"
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800&family=Barlow:wght@300;400;500;600&display=swap');

        /* ── Sidebar always navy/gold regardless of light/dark ── */
        [data-testid="stSidebar"] {{
            background: linear-gradient(160deg, #1f3272 0%, #0e1a3d 100%) !important;
            border-right: 2px solid rgba(240,192,48,0.25) !important;
        }}
        [data-testid="stSidebar"] * {{ font-family:'Barlow',sans-serif !important; }}

        /* Sidebar nav buttons */
        .sidebar-nav button,
        [data-testid="stSidebar"] .stButton > button {{
            width:100%; margin-bottom:0.35rem;
            background: rgba(240,192,48,0.06) !important;
            border: 1px solid rgba(240,192,48,0.22) !important;
            color:#dde6f5 !important; -webkit-text-fill-color:#dde6f5 !important;
            font-family:'Barlow Condensed',sans-serif !important;
            font-weight:700 !important; letter-spacing:1px !important;
            text-transform:uppercase !important;
            transition: all 0.15s ease !important;
        }}
        .sidebar-nav button *,
        [data-testid="stSidebar"] .stButton > button * {{
            color:#dde6f5 !important; -webkit-text-fill-color:#dde6f5 !important; opacity:1 !important;
        }}
        .sidebar-nav button:hover,
        [data-testid="stSidebar"] .stButton > button:hover {{
            background-color:#f0c030 !important; border-color:#f0c030 !important;
            color:#0e1a3d !important; -webkit-text-fill-color:#0e1a3d !important;
            transform: scale(1.02);
            box-shadow: 0 4px 16px rgba(240,192,48,0.4) !important;
        }}
        .sidebar-nav button:hover *,
        [data-testid="stSidebar"] .stButton > button:hover * {{
            color:#0e1a3d !important; -webkit-text-fill-color:#0e1a3d !important;
        }}
        [data-testid="stSidebar"] .stButton > button *,
        [data-testid="stSidebar"] button[kind="secondary"],
        [data-testid="stSidebar"] button[kind="secondary"] * {{
            color:#dde6f5 !important; -webkit-text-fill-color:#dde6f5 !important; opacity:1 !important;
        }}
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] div,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] p {{
            color:#7a93c0 !important;
        }}

        /* ── Typography — respects light/dark ── */
        .title-main {{
            font-family:'Barlow Condensed',sans-serif !important;
            font-size:1.5rem; font-weight:800; letter-spacing:2px;
            text-transform:uppercase; color:#f0c030; margin:0; line-height:1.1;
        }}
        .title-sub {{
            font-family:'Barlow Condensed',sans-serif !important;
            font-size:1.7rem; font-weight:700; letter-spacing:1.5px;
            text-transform:uppercase; margin:0; line-height:1.1;
        }}
        .section-title {{
            font-family:'Barlow Condensed',sans-serif !important;
            font-size:0.85rem; font-weight:700; letter-spacing:1.5px;
            text-transform:uppercase; color:#7a93c0;
            margin-top:6px; margin-bottom:0.35rem;
            border-bottom: 1px solid rgba(240,192,48,0.22); padding-bottom:4px;
        }}
        .kv-wrap {{
            border: 1px solid rgba(0,0,0,0.12);
            border-radius: 4px;
            margin-bottom: 12px;
            overflow: hidden;
            height: calc(100% - 12px);
            display: flex;
            flex-direction: column;
        }}
        .kv-title {{
            font-family:'Barlow Condensed',sans-serif !important;
            font-size:0.72rem; font-weight:700; letter-spacing:1.5px;
            text-transform:uppercase; color:#555;
            background: rgba(0,0,0,0.05);
            padding: 6px 12px;
            border-bottom: 1px solid rgba(0,0,0,0.1);
            margin-bottom: 0;
            flex-shrink: 0;
        }}
        .kv-value {{
            font-family:'Barlow',sans-serif !important;
            font-size:0.92rem; font-weight:400;
            padding: 8px 12px;
            margin-bottom: 0;
            flex: 1;
        }}
        /* Make Streamlit columns stretch to equal height */
        div[data-testid="stHorizontalBlock"] > div[data-testid="stVerticalBlock"] {{
            height: 100%;
        }}
        .hint {{ font-size:0.88rem; color:#7a93c0; margin-top:-4px; margin-bottom:10px; }}
        .legend-wrap {{ display:flex; gap:18px; flex-wrap:wrap; margin-bottom:8px; }}
        .legend-item {{ display:flex; align-items:center; gap:8px; font-size:0.92rem; }}
        .legend-swatch {{ width:16px; height:16px; border-radius:3px; display:inline-block; }}

        h1, h2, h3 {{
            font-family:'Barlow Condensed',sans-serif !important;
            letter-spacing:1px !important;
        }}

        /* ── Metrics ── */
        [data-testid="stMetric"] {{
            border: 1px solid rgba(240,192,48,0.22) !important;
            border-radius: 8px !important; padding: 16px !important;
            border-top: 3px solid #f0c030 !important;
        }}
        [data-testid="stMetricLabel"] {{
            font-family:'Barlow Condensed',sans-serif !important;
            font-size:0.75rem !important; letter-spacing:1.5px !important;
            text-transform:uppercase !important; color:#7a93c0 !important;
        }}
        [data-testid="stMetricValue"] {{
            font-family:'Barlow Condensed',sans-serif !important;
            font-size:2.2rem !important; font-weight:800 !important;
        }}

        /* ── Tabs ── */
        .stTabs [data-baseweb="tab"] {{
            font-family:'Barlow Condensed',sans-serif !important;
            font-weight:700 !important; letter-spacing:1px !important;
            text-transform:uppercase !important; opacity:1 !important;
        }}
        .stTabs [data-baseweb="tab"][aria-selected="true"] {{
            color:#f0c030 !important; -webkit-text-fill-color:#f0c030 !important;
            border-bottom:2px solid #f0c030 !important;
        }}
        /* Remove default red/orange Streamlit tab indicator */
        .stTabs [data-baseweb="tab-highlight"] {{
            background-color: #f0c030 !important;
        }}
        .stTabs [data-baseweb="tab-border"] {{
            background-color: rgba(240,192,48,0.15) !important;
        }}

        /* ── Input labels — identical to kv-title ── */
        [data-testid="stTextInput"] label,
        [data-testid="stSelectbox"] label,
        [data-testid="stDateInput"] label,
        [data-testid="stNumberInput"] label,
        [data-testid="stMultiSelect"] label {{
            font-family:'Barlow Condensed',sans-serif !important;
            font-size:0.72rem !important; font-weight:700 !important;
            letter-spacing:1.5px !important; text-transform:uppercase !important;
            color:#555 !important; -webkit-text-fill-color:#555 !important;
            background:rgba(0,0,0,0.05) !important;
            padding:6px 12px !important; display:block !important;
            border-bottom:1px solid rgba(0,0,0,0.1) !important;
            margin-bottom:0 !important; width:100% !important;
            box-sizing:border-box !important;
        }}
        /* Card border around each Streamlit input widget */
        [data-testid="stTextInput"],
        [data-testid="stSelectbox"],
        [data-testid="stDateInput"],
        [data-testid="stNumberInput"],
        [data-testid="stMultiSelect"] {{
            border:1px solid rgba(0,0,0,0.12) !important;
            border-radius:4px !important;
            overflow:hidden !important;
            margin-bottom:12px !important;
        }}
        /* White input backgrounds */
        [data-testid="stTextInput"] input,
        [data-testid="stDateInput"] input,
        [data-testid="stNumberInput"] input {{
            background:white !important; border:none !important;
        }}
        [data-testid="stSelectbox"] [data-baseweb="select"] > div:first-child {{
            background:white !important; border:none !important;
        }}
        /* TextArea label */
        [data-testid="stTextArea"] label {{
            font-family:'Barlow Condensed',sans-serif !important;
            font-size:0.72rem !important; font-weight:700 !important;
            letter-spacing:1.5px !important; text-transform:uppercase !important;
            color:#555 !important; -webkit-text-fill-color:#555 !important;
            background:rgba(0,0,0,0.05) !important;
            padding:6px 12px !important; display:block !important;
            border-bottom:1px solid rgba(0,0,0,0.1) !important;
            margin-bottom:0 !important; width:100% !important;
        }}
        /* Hide empty text-area labels (we render our own kv-title above the textarea
           in the Notes sections, so the empty label was producing a stray gray bar). */
        [data-testid="stTextArea"] label:empty,
        [data-testid="stTextArea"] label:has(> div:empty),
        [data-testid="stTextArea"] label > div:empty {{
            display:none !important;
            padding:0 !important;
            margin:0 !important;
            border:0 !important;
            background:transparent !important;
        }}
        [data-baseweb="checkbox"] span, [data-baseweb="radio"] span,
        [data-testid="stCheckbox"] label, [data-testid="stCheckbox"] label p,
        [data-testid="stCheckbox"] label span,
        [data-testid="stCheckbox"] div[role="checkbox"] + div,
        [data-testid="stCheckbox"] div[role="checkbox"] + div p,
        [data-testid="stCheckbox"] div[role="checkbox"] + div span,
        [data-baseweb="checkbox"] label, [data-baseweb="checkbox"] label p,
        [data-baseweb="checkbox"] label span, [data-baseweb="checkbox"] > div:last-child,
        [data-baseweb="checkbox"] > div:last-child p, [data-baseweb="checkbox"] > div:last-child span,
        [data-testid="stRadio"] label, [data-testid="stRadio"] label p,
        [data-testid="stRadio"] label span, [data-baseweb="radio"] label,
        [data-baseweb="radio"] label p, [data-baseweb="radio"] label span {{
            opacity:1 !important;
        }}
        .stNumberInput input, .stNumberInput [data-baseweb="input"] input {{
            color:#000000 !important; -webkit-text-fill-color:#000000 !important;
        }}

        /* ── Primary buttons ── */
        button[kind="primary"], .stButton > button[kind="primary"] {{
            background:#f0c030 !important; border-color:#f0c030 !important;
            color:#0e1a3d !important; -webkit-text-fill-color:#0e1a3d !important;
            font-family:'Barlow Condensed',sans-serif !important;
            font-weight:700 !important; letter-spacing:1px !important;
            text-transform:uppercase !important; border-radius:5px !important;
            transition: all 0.15s ease !important;
        }}
        button[kind="primary"]:hover, .stButton > button[kind="primary"]:hover {{
            background:#f8d96a !important; border-color:#f8d96a !important;
            transform: scale(1.03);
            box-shadow: 0 4px 16px rgba(240,192,48,0.45) !important;
        }}


        /* ── Horizontal-block action buttons (Edit/Add Member, Save, Cancel) ──
           These should look and behave exactly like the top org bar buttons:
           dark blue at rest, yellow on hover with scale+glow. */
        div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button,
        div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[kind="primary"],
        div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[kind="secondary"],
        div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[kind="tertiary"] {{
            font-family:'Barlow Condensed',sans-serif !important;
            font-size:11px !important; font-weight:700 !important;
            letter-spacing:1px !important; text-transform:uppercase !important;
            padding: 4px 10px !important;
            border-radius:4px !important;
            border: 1px solid rgba(240,192,48,0.2) !important;
            background: #2a4090 !important;
            color:#dde6f5 !important; -webkit-text-fill-color:#dde6f5 !important;
            white-space: nowrap !important;
            min-height: 0 !important;
            line-height: 1.3 !important;
            transition: all .15s ease !important;
        }}
        div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button *,
        div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[kind="primary"] * {{
            color:#dde6f5 !important; -webkit-text-fill-color:#dde6f5 !important;
        }}
        /* Hover — yellow with scale and glow, matching sidebar/org-bar */
        div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button:hover,
        div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[kind="primary"]:hover,
        div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[kind="secondary"]:hover {{
            background:#f0c030 !important;
            border-color:#f0c030 !important;
            color:#0e1a3d !important; -webkit-text-fill-color:#0e1a3d !important;
            transform: scale(1.03) !important;
            box-shadow: 0 4px 16px rgba(240,192,48,0.4) !important;
        }}
        div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button:hover *,
        div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[kind="primary"]:hover * {{
            color:#0e1a3d !important; -webkit-text-fill-color:#0e1a3d !important;
        }}
        /* Strip the lingering focus ring ONLY on the four action buttons we
           care about (Save, Cancel, Edit Member, Add Member). Targeting them
           by their Streamlit keys via the .st-key-<key> wrapper class (and
           aria-label as a fallback) means the sidebar nav and any other
           focused button keeps its natural selected/active appearance. */
        .st-key-edit_member_btn button:focus:not(:hover),
        .st-key-add_member_btn button:focus:not(:hover),
        .st-key-edit_save button:focus:not(:hover),
        .st-key-edit_cancel button:focus:not(:hover),
        .st-key-add_save button:focus:not(:hover),
        .st-key-add_cancel button:focus:not(:hover),
        div[data-testid="stButton"]:has(button[aria-label="Edit Member"]) button:focus:not(:hover),
        div[data-testid="stButton"]:has(button[aria-label="✚  Add Member"]) button:focus:not(:hover),
        div[data-testid="stButton"]:has(button[aria-label="Save"]) button:focus:not(:hover),
        div[data-testid="stButton"]:has(button[aria-label="Cancel"]) button:focus:not(:hover) {{
            background: #2a4090 !important;
            color:#dde6f5 !important; -webkit-text-fill-color:#dde6f5 !important;
            border: 1px solid rgba(240,192,48,0.2) !important;
            outline: none !important;
            box-shadow: none !important;
            transform: none !important;
        }}
        .st-key-edit_member_btn button:focus:not(:hover) *,
        .st-key-add_member_btn button:focus:not(:hover) *,
        .st-key-edit_save button:focus:not(:hover) *,
        .st-key-edit_cancel button:focus:not(:hover) *,
        .st-key-add_save button:focus:not(:hover) *,
        .st-key-add_cancel button:focus:not(:hover) *,
        div[data-testid="stButton"]:has(button[aria-label="Edit Member"]) button:focus:not(:hover) *,
        div[data-testid="stButton"]:has(button[aria-label="✚  Add Member"]) button:focus:not(:hover) *,
        div[data-testid="stButton"]:has(button[aria-label="Save"]) button:focus:not(:hover) *,
        div[data-testid="stButton"]:has(button[aria-label="Cancel"]) button:focus:not(:hover) * {{
            color:#dde6f5 !important; -webkit-text-fill-color:#dde6f5 !important;
        }}
        /* Push content below banner */
        .block-container {{
            padding-top: 158px !important;
        }}

        /* ── index.html card/panel theme ── */
        .wg-stat-card {{
            background: #162050;
            border: 1px solid rgba(240,192,48,0.2);
            border-radius: 8px;
            padding: 18px 20px;
            position: relative;
            overflow: hidden;
            margin-bottom: 14px;
        }}
        .wg-stat-card::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 3px;
            background: #f0c030;
        }}
        .wg-stat-card.green::before {{ background: #22c55e; }}
        .wg-stat-card.red::before   {{ background: #c0283e; }}
        .wg-stat-card.blue::before  {{ background: #6aa3c8; }}
        .wg-stat-card .wg-lbl {{
            font-size: 10px; letter-spacing: 1.5px; text-transform: uppercase;
            color: #7a93c0; margin-bottom: 8px;
            font-family: 'Barlow Condensed', sans-serif;
        }}
        .wg-stat-card .wg-val {{
            font-family: 'Barlow Condensed', sans-serif;
            font-size: 38px; font-weight: 800; color: #ffffff; line-height: 1;
        }}
        .wg-stat-card .wg-sub {{
            font-size: 12px; color: #7a93c0; margin-top: 6px;
        }}

        /* Section headers matching index.html */
        .wg-sec-hdr {{
            display: flex; align-items: center; gap: 12px;
            margin-bottom: 14px; margin-top: 8px;
        }}

        /* Force breathing room above and below every Plotly chart so its
           dark paper background can't visually overlap the legend / subtitle
           that sits above it, or the next section that comes after it.
           Multiple selectors so we hit it whether Streamlit's class names
           change or not. */
        div[data-testid="stPlotlyChart"],
        div.stPlotlyChart,
        .stPlotlyChart,
        section[data-testid="stMain"] div[data-testid="stPlotlyChart"],
        section[data-testid="stMain"] div.stPlotlyChart {{
            margin-top: 18px !important;
            margin-bottom: 6px !important;
        }}
        /* Element-container wrapper that holds the Plotly chart. We DO NOT
           re-apply margin here — the chart itself already has 18px top.
           Stacking margin on both would double the visual gap. The wrapper
           still gets overflow:hidden so the dark paper background can't
           bleed past its container box. */
        div[data-testid="stElementContainer"]:has(> div[data-testid="stPlotlyChart"]),
        div[data-testid="stElementContainer"]:has(> .stPlotlyChart),
        div[data-testid="stElementContainer"]:has(div[data-testid="stPlotlyChart"]) {{
            margin-top: 0 !important;
            margin-bottom: 0 !important;
            padding-top: 0 !important;
            overflow: hidden !important;
        }}

        /* EXCEPTION: when a Plotly chart sits directly below a rank header,
           the two should be visually flush (one panel per rank). Strip the
           chart's top margin so the dark-blue header butts against the
           dark-blue chart paper as a single unified card. */
        div[data-testid="stElementContainer"]:has(.wg-rank-header)
            + div[data-testid="stElementContainer"]:has(div[data-testid="stPlotlyChart"]),
        div[data-testid="stElementContainer"]:has(.wg-rank-header) + div div[data-testid="stPlotlyChart"] {{
            margin-top: 0 !important;
            padding-top: 0 !important;
        }}
        /* Also: remove BOTTOM margin from the rank header wrapper so it
           sits flush against the chart below it. */
        div[data-testid="stElementContainer"]:has(.wg-rank-header) {{
            margin-bottom: 0 !important;
        }}

        /* Row-of-columns spacing: each row of rank charts is a horizontal
           block. Keep just enough room between rows to see a thin white
           gap. */
        div[data-testid="stHorizontalBlock"] {{
            margin-top: 3px !important;
            margin-bottom: 3px !important;
        }}

        /* Compact spacing around the "Total Personnel: N" caption that
           sits between the Member Information table and the Rank Distribution
           section that follows it. Streamlit wraps st.write() output in a
           paragraph; both p and its container collapse to tight margins. */
        div[data-testid="stMarkdownContainer"] p:has(strong):only-child {{
            margin-top: 4px !important;
            margin-bottom: 4px !important;
        }}
        .wg-sec-hdr h2 {{
            font-family: 'Barlow Condensed', sans-serif;
            font-size: 1.4rem; font-weight: 700; letter-spacing: 2px;
            text-transform: uppercase; color: #1a2a5e; white-space: nowrap;
            margin: 0;
        }}
        .wg-sec-hdr .wg-line {{
            flex: 1; height: 1px; background: rgba(240,192,48,0.2);
        }}
        .wg-sec-tag {{
            font-size: 10px; letter-spacing: 1px; text-transform: uppercase;
            background: rgba(240,192,48,0.08); color: #f0c030;
            border: 1px solid rgba(240,192,48,0.2);
            border-radius: 3px; padding: 2px 8px; white-space: nowrap;
        }}

        /* Chart panels matching index.html */
        .wg-chart-panel {{
            background: #162050;
            border: 1px solid rgba(240,192,48,0.2);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 16px;
        }}
        .wg-chart-panel h3 {{
            font-family: 'Barlow Condensed', sans-serif;
            font-size: 13px; font-weight: 700; letter-spacing: 1px;
            text-transform: uppercase; color: #9dc4db;
            margin-bottom: 14px;
        }}

        /* Streamlit metric cards — card-bg style */
        [data-testid="stMetric"] {{
            background: #162050 !important;
            border: 1px solid rgba(240,192,48,0.2) !important;
            border-radius: 8px !important;
            padding: 18px 20px !important;
            position: relative !important;
            overflow: hidden !important;
        }}
        [data-testid="stMetric"]::before {{
            content: '' !important;
            position: absolute !important;
            top: 0 !important; left: 0 !important; right: 0 !important;
            height: 3px !important;
            background: #f0c030 !important;
            display: block !important;
        }}
        [data-testid="stMetricLabel"] {{
            font-family: 'Barlow Condensed', sans-serif !important;
            font-size: 10px !important; letter-spacing: 1.5px !important;
            text-transform: uppercase !important; color: #7a93c0 !important;
        }}
        [data-testid="stMetricValue"] {{
            font-family: 'Barlow Condensed', sans-serif !important;
            font-size: 2.4rem !important; font-weight: 800 !important;
            color: #ffffff !important;
        }}

        /* Streamlit dataframe table styling */
        [data-testid="stDataFrame"] {{
            border: 1px solid rgba(240,192,48,0.2) !important;
            border-radius: 8px !important;
            overflow: hidden !important;
        }}
        [data-testid="stDataFrame"] th {{
            background: #1f3272 !important;
            color: #f0c030 !important;
            font-family: 'Barlow Condensed', sans-serif !important;
            font-size: 12px !important; letter-spacing: 1px !important;
            text-transform: uppercase !important;
            border-bottom: 1px solid rgba(240,192,48,0.2) !important;
        }}
        [data-testid="stDataFrame"] td {{
            color: #dde6f5 !important;
            border-bottom: 1px solid rgba(255,255,255,0.04) !important;
            font-size: 13px !important;
        }}
        [data-testid="stDataFrame"] tr:hover {{
            background: rgba(240,192,48,0.05) !important;
        }}

        /* Plotly chart background to match card-bg */
        .js-plotly-plot .plotly .bg {{
            fill: #162050 !important;
        }}

        hr {{ border-color: rgba(240,192,48,0.22) !important; }}
        [data-baseweb="select"] * {{ color:#000000 !important; }}
        </style>""", unsafe_allow_html=True)

    # ── Active-button highlight (sidebar nav, top org bar, Edit/Add Member) ───
    # Rather than relying on :has() / aria-label / .st-key-* selectors (which
    # vary across Streamlit versions), we tag the active buttons with a
    # `data-active="true"` attribute via the polling JS in app.py and target
    # that attribute from CSS. This is the single source of truth for the
    # "stays yellow when selected" behaviour across the whole app.
    st.markdown("""
    <style>
    /* Sidebar nav — active page stays yellow */
    [data-testid="stSidebar"] button[data-active="true"],
    [data-testid="stSidebar"] button[data-active="true"]:hover,
    [data-testid="stSidebar"] button[data-active="true"]:focus,
    [data-testid="stSidebar"] button[data-active="true"]:focus-visible,
    [data-testid="stSidebar"] button[data-active="true"]:active {
        background-color:#f0c030 !important;
        border-color:#f0c030 !important;
        color:#0e1a3d !important;
        -webkit-text-fill-color:#0e1a3d !important;
        box-shadow: 0 4px 16px rgba(240,192,48,0.4) !important;
    }
    [data-testid="stSidebar"] button[data-active="true"] * {
        color:#0e1a3d !important;
        -webkit-text-fill-color:#0e1a3d !important;
    }

    /* Top org bar — active org stays yellow.
       Scoped via the wg-org-bar-anchor sentinel injected in app.py. */
    #wg-org-bar-anchor ~ div[data-testid="stHorizontalBlock"] button[data-active="true"],
    #wg-org-bar-anchor ~ div[data-testid="stHorizontalBlock"] button[data-active="true"]:hover,
    #wg-org-bar-anchor ~ div[data-testid="stHorizontalBlock"] button[data-active="true"]:focus,
    #wg-org-bar-anchor ~ div[data-testid="stHorizontalBlock"] button[data-active="true"]:focus-visible,
    #wg-org-bar-anchor ~ div[data-testid="stHorizontalBlock"] button[data-active="true"]:active {
        background:#f0c030 !important;
        border-color:#f0c030 !important;
        color:#0e1a3d !important;
        -webkit-text-fill-color:#0e1a3d !important;
        box-shadow: 0 4px 16px rgba(240,192,48,0.4) !important;
    }
    #wg-org-bar-anchor ~ div[data-testid="stHorizontalBlock"] button[data-active="true"] * {
        color:#0e1a3d !important;
        -webkit-text-fill-color:#0e1a3d !important;
    }

    /* Edit Member / Add Member — active when their view is open */
    div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[data-active="true"],
    div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[data-active="true"]:hover,
    div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[data-active="true"]:focus,
    div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[data-active="true"]:focus-visible,
    div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[data-active="true"]:active {
        background:#f0c030 !important;
        border-color:#f0c030 !important;
        color:#0e1a3d !important;
        -webkit-text-fill-color:#0e1a3d !important;
        box-shadow: 0 4px 16px rgba(240,192,48,0.4) !important;
    }
    div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button[data-active="true"] * {
        color:#0e1a3d !important;
        -webkit-text-fill-color:#0e1a3d !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Hidden element exposing current state to the polling JS in app.py.
    _current_page = st.session_state.get("page", "")
    _sa_view_all  = st.session_state.get("sa_view_all", False)
    _sa_tenant_id = st.session_state.get("sa_tenant_id", None)
    _tenant_name  = st.session_state.get("tenant_name", "")
    _edit_open    = st.session_state.get("edit_open", False)
    _add_open     = st.session_state.get("add_open", False)
    _active_org_label = "All Units" if _sa_view_all else (_tenant_name or "")
    st.markdown(
        f'<div id="wg-active-state" style="display:none;"'
        f' data-page="{_current_page}"'
        f' data-org="{_active_org_label}"'
        f' data-edit-open="{str(_edit_open).lower()}"'
        f' data-add-open="{str(_add_open).lower()}"'
        f'></div>',
        unsafe_allow_html=True,
    )


# ── UI helpers ────────────────────────────────────────────────────────────────
def render_kv(label, value):
    st.markdown(
        f'<div class="kv-wrap">'
        f'<div class="kv-title">{label}</div>'
        f'<div class="kv-value">{safe_text(value) or "—"}</div>'
        f'</div>',
        unsafe_allow_html=True)



def sec_header(title, tag=None):
    """Render a section header matching index.html .sec-hdr style."""
    tag_html = f'<span class="wg-sec-tag">{tag}</span>' if tag else ""
    st.markdown(
        f'<div class="wg-sec-hdr"><h2>{title}</h2><div class="wg-line"></div>{tag_html}</div>',
        unsafe_allow_html=True
    )


def stat_card(label, value, sub=None, color="gold"):
    """Render a stat card matching index.html .stat-card style."""
    cls = {"gold": "", "green": " green", "red": " red", "blue": " blue"}.get(color, "")
    sub_html = f'<div class="wg-sub">{sub}</div>' if sub else ""
    st.markdown(
        f'<div class="wg-stat-card{cls}">' +
        f'<div class="wg-lbl">{label}</div>' +
        f'<div class="wg-val">{value}</div>' +
        f'{sub_html}</div>',
        unsafe_allow_html=True
    )



def chart_legend(title, items):
    html = [f'<div class="section-title">{title} Legend</div><div class="legend-wrap">']
    for color, txt in items:
        html.append(f'<div class="legend-item"><span class="legend-swatch" style="background:{color}"></span>{txt}</div>')
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def show_logo(width):
    p = Path(LOGO_FILE)
    if p.exists():
        st.image(str(p), width=width)


# ── Data I/O ──────────────────────────────────────────────────────────────────
from database import (
    get_members, get_all_members, create_member, update_member, delete_member,
    list_strat_uploads, get_latest_strat_upload, get_strat_records,
    create_strat_upload, delete_strat_upload,
    get_bench_layout, save_bench_layout, reset_bench_layout,
    get_bench_last_modified,
    get_user_by_id, get_all_tenants,
)

DB_COL_MAP = {
    "rank":"Rank","first_name":"FirstName","last_name":"LastName",
    "flight":"Flight","last_eval":"LastEval","promo_recomm":"PromoRecomm",
    "last_aca":"LastACA","doe":"DOE","tig":"TIG","dor":"DOR","tis":"TIS",
    "dafsc":"DAFSC","skill_level":"SkillLevel","fitness":"Fitness",
    "pme_als":"PME_ALS","pme_ncoa":"PME_NCOA","pme_sncoa":"PME_SNCOA",
    "pme_ejpme1":"PME_EJPME1","pme_ejpme2":"PME_EJPME2","pme_sncoe":"PME_SNCOE",
    "pme_edo":"PME_EDO","pme_cmsoc":"PME_CMSOC","pme_clc":"PME_CLC",
    "pme_dsca1":"PME_DSCA1","pme_dsca2":"PME_DSCA2",
    "edu_associates":"EDU_ASSOCIATES","edu_bachelors":"EDU_BACHELORS",
    "edu_masters":"EDU_MASTERS","edu_doctorate":"EDU_DOCTORATE",
    "assignments":"Assignments","assignments_date":"AssignmentsDate",
    "awards_decs":"AwardsDecs","awards_decs_date":"AwardsDecsDate",
    "prof_org_mbr":"ProfOrgMbr","leadership_roles":"LeadershipRoles",
    "supervisor_notes":"SupervisorNotes","ratee_notes":"RateeNotes",
    "last_edit":"LastEdit","id":"_db_id","tenant_id":"_tenant_id",
}

def rows_to_df(rows):
    """Convert Supabase rows to a DataFrame matching the existing column structure."""
    if not rows:
        return pd.DataFrame(columns=list(DB_COL_MAP.values()))
    records = []
    for row in rows:
        rec = {}
        for db_col, df_col in DB_COL_MAP.items():
            rec[df_col] = row.get(db_col, "")
            if rec[df_col] is None:
                rec[df_col] = ""
        records.append(rec)
    return pd.DataFrame(records)

def recompute_tenure(df):
    df = df.copy()
    def _ms(value):
        s = "" if value is None else str(value).strip()
        if not s or s.lower() == "nan":
            return 0
        try:
            d = pd.to_datetime(s).date()
        except Exception:
            return 0
        today = date.today()
        m = (today.year - d.year) * 12 + (today.month - d.month)
        if today.day < d.day:
            m -= 1
        return max(m, 0)
    df["TIG"] = df["DOR"].apply(_ms).apply(lambda m: f"{m//12}y {m%12}m")
    df["TIS"] = df["DOE"].apply(_ms).apply(lambda m: f"{m//12}y {m%12}m")
    return df

def load_data():
    """Load members from Supabase scoped to active tenant."""
    tenant_id = st.session_state.get("active_tenant_id")
    if tenant_id is None and st.session_state.get("role") == "super_admin" and st.session_state.get("sa_view_all"):
        rows = get_all_members()
    elif tenant_id:
        rows = get_members(tenant_id)
    else:
        rows = []
    df = rows_to_df(rows)
    return recompute_tenure(df)

def save_data(df):
    """Save all modified rows back to Supabase."""
    is_super_all = (
        st.session_state.get("role") == "super_admin"
        and st.session_state.get("sa_view_all", False)
    )
    if not is_super_all:
        tenant_id = st.session_state.get("active_tenant_id") or st.session_state.get("tenant_id")
        if not tenant_id:
            return
    # Build the field map. We normally exclude internal "_*" columns from the
    # write path, but we DO want _tenant_id to flow back to the tenant_id DB
    # column so super-admins can move members between squadrons via Edit Member.
    rev_map = {v: k for k, v in DB_COL_MAP.items() if not k.startswith("_")}
    rev_map["_tenant_id"] = "tenant_id"
    for _, row in df.iterrows():
        db_id = row.get("_db_id")
        if not db_id:
            continue
        data = {}
        for df_col, db_col in rev_map.items():
            if df_col in row:
                val = row[df_col]
                if db_col == "tenant_id":
                    # tenant_id must be int (or None) — never the empty string
                    if val is None or (isinstance(val, float) and pd.isna(val)) or val == "":
                        continue  # skip rather than send a bad value
                    try:
                        data[db_col] = int(val)
                    except (TypeError, ValueError):
                        continue
                else:
                    data[db_col] = "" if (val is None or (isinstance(val, float) and pd.isna(val))) else str(val)
        update_member(int(db_id), data)


# ── Chart helpers ─────────────────────────────────────────────────────────────
CARD_BG   = "#162050"
NAVY_MID  = "#1f3272"
GOLD      = "#f0c030"
ICE       = "#dde6f5"
STEEL     = "#7a93c0"
BORDER    = "rgba(240,192,48,0.2)"

CHART_LAYOUT = dict(
    paper_bgcolor=CARD_BG,
    plot_bgcolor=CARD_BG,
    font=dict(family="Barlow Condensed, sans-serif", color=ICE, size=12),
    title_font=dict(family="Barlow Condensed, sans-serif", color=ICE, size=14),
    xaxis=dict(
        gridcolor="rgba(255,255,255,0.06)",
        tickfont=dict(color=STEEL, size=11),
        title_font=dict(color=STEEL),
        linecolor="rgba(240,192,48,0.2)",
        zerolinecolor="rgba(240,192,48,0.1)",
    ),
    yaxis=dict(
        gridcolor="rgba(255,255,255,0.06)",
        tickfont=dict(color=STEEL, size=11),
        title_font=dict(color=STEEL),
        linecolor="rgba(240,192,48,0.2)",
        zerolinecolor="rgba(240,192,48,0.1)",
    ),
    legend=dict(
        font=dict(color=ICE, size=11),
        bgcolor="rgba(14,26,61,0.8)",
        bordercolor="rgba(240,192,48,0.2)",
        borderwidth=1,
    ),
)

def apply_chart_theme(fig, show_legend=False):
    fig.update_layout(**CHART_LAYOUT, showlegend=show_legend, margin=dict(t=50,b=30,l=20,r=20))
    return fig

def add_bar_labels(fig):
    fig.update_traces(texttemplate="%{y}", textposition="outside", cliponaxis=False)
    fig.update_layout(**CHART_LAYOUT, showlegend=False, margin=dict(t=60,b=30,l=20,r=20))
    return fig


def chart_rank_distribution(df, title):
    rc = df["Rank"].value_counts().reindex(RANK_ORDER[:-1], fill_value=0).reset_index()
    rc.columns = ["Rank","Count"]
    st.markdown(f"**Total Personnel:** {int(rc['Count'].sum())}")
    fig = px.pie(rc, names="Rank", values="Count", title=title, hole=0.45,
                 color_discrete_sequence=COLORS)
    fig.update_traces(textposition="inside", textinfo="value+percent",
                      textfont=dict(color=ICE))
    # In-chart legend on the right (replaces the external chart_legend block).
    _layout = {**CHART_LAYOUT}
    _layout["legend"] = {**(CHART_LAYOUT.get("legend") or {}),
                         "title": {"text": "Rank"},
                         "orientation": "v",
                         "x": 1.02, "y": 0.5,
                         "yanchor": "middle",
                         "xanchor": "left"}
    fig.update_layout(**_layout, showlegend=True,
                      margin=dict(t=50, b=20, l=20, r=120))
    return fig


def tenure_pie(df, month_col):
    ranks = ["A1C","SrA","SSgt","TSgt","MSgt"]
    if "TIG" in month_col:
        bucket_labels = ["<1"] + [str(i) for i in range(1,11)] + ["10+"]
        max_year = 10
    else:
        bucket_labels = ["<1"] + [str(i) for i in range(1,21)] + ["20+"]
        max_year = 20
    color_map = {
        "<1":"#4472C4","1":"#ED7D31","2":"#A5A5A5","3":"#FFC000","4":"#5B9BD5",
        "5":"#70AD47","6":"#264478","7":"#9E480E","8":"#636363","9":"#997300",
        "10":"#255E91","10+":"#BF9000","11":"#43682B","12":"#2F5597","13":"#843C0C",
        "14":"#404040","15":"#7F6000","16":"#1F4E79","17":"#375623","18":"#1F3864",
        "19":"#7F3F00","20":"#1F4E79","20+":"#BF9000"
    }
    charts = []
    for rank in ranks:
        rdf = df[df["Rank"]==rank].copy()
        years = (rdf[month_col] // 12)
        def bucket(x, _max=max_year):
            if x < 1:   return "<1"
            if x >= _max: return str(_max)+"+"
            return str(int(x))
        rdf["Bucket"] = years.apply(bucket)
        counts = rdf["Bucket"].value_counts().reindex(bucket_labels, fill_value=0).astype(int)
        fig = px.bar(x=counts.values.tolist(), y=counts.index.tolist(), orientation="h",
                     color=counts.index.tolist(), color_discrete_map=color_map,
                     labels={"x":"Count","y":"Years"})
        fig.update_traces(texttemplate="%{x}", textposition="outside", cliponaxis=False)
        # Merge axis overrides with the base CHART_LAYOUT axes so we don't pass
        # `xaxis` / `yaxis` to update_layout() twice (Plotly raises TypeError).
        _layout = {**CHART_LAYOUT}
        _layout["yaxis"] = {**CHART_LAYOUT.get("yaxis", {}),
                            "categoryorder": "array",
                            "categoryarray": bucket_labels}
        _layout["xaxis"] = {**CHART_LAYOUT.get("xaxis", {}),
                            "dtick": 1,
                            "tickmode": "linear"}
        # In-chart legend on the right. Plotly's legend auto-scrolls when it
        # has more entries than fit (TIS goes up to 20+ years = 22 entries),
        # so we just enable it and reserve right-side margin for it. Merge
        # the font dict so we preserve the ICE color from CHART_LAYOUT and
        # only override the size.
        _base_legend = (CHART_LAYOUT.get("legend") or {})
        _base_font   = (_base_legend.get("font") or {})
        _layout["legend"] = {**_base_legend,
                             "title": {"text": "Years"},
                             "orientation": "v",
                             "x": 1.02, "y": 0.5,
                             "yanchor": "middle",
                             "xanchor": "left",
                             "font": {**_base_font, "size": 10}}
        fig.update_layout(**_layout, showlegend=True,
                          margin=dict(t=10, b=20, l=20, r=110),
                          title_text="")
        charts.append((rank, fig, len(rdf)))
    for i in range(0, len(charts), 2):
        cols = st.columns(2)
        for j in range(2):
            if i+j < len(charts):
                rank, fig, total = charts[i+j]
                cols[j].markdown(
                    f'<div class="wg-rank-header" style="font-family:Barlow Condensed,sans-serif;'
                    f'font-size:1.05rem;font-weight:700;letter-spacing:1.5px;'
                    f'text-transform:uppercase;color:#ffffff;'
                    f'background:#162050;padding:8px 12px 4px 12px;'
                    f'border-radius:6px 6px 0 0;margin:0;">{rank}'
                    f'<span style="font-family:Barlow,sans-serif;font-weight:400;'
                    f'font-size:0.82rem;letter-spacing:0.5px;text-transform:none;'
                    f'color:#9dc4db;margin-left:10px;">Total: {total}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )
                cols[j].plotly_chart(fig, use_container_width=True, key=f"{month_col}_{rank}")


def _credential_chart(df, title, fields_for_rank_fn, ranks, color_seq=None):
    """Build a per-rank subplot chart for credential-style data (PME or Edu).
    Each rank gets its own subplot. Within each subplot, x-axis is the
    credential (e.g. ALS, EJPME I, NCOA…); y-axis is the count of members
    in that rank holding that credential (plus a Total Members bar). A
    shared legend on the right deduplicates credential colors across all
    subplots so each appears exactly once.

    Mirrors the visual pattern of the Promotion Scorecard Category Scoring
    Distribution charts so the dashboard reads consistently.

    Returns (fig, metrics_in_order) — `metrics` is the deduped list of
    credential labels in encounter order, used by the caller to build the
    "PME Legend" / "Higher Education Legend" UI block above the chart.
    """
    from plotly.subplots import make_subplots
    palette = color_seq or COLORS

    # Walk every rank to collect (metric, count) pairs and figure out the
    # union of metric labels in encounter order. Total Members is always
    # the first metric so it leads each subplot.
    per_rank_data = {}
    metric_order = []
    seen_metrics = set()

    def _push_metric(m):
        if m not in seen_metrics:
            metric_order.append(m); seen_metrics.add(m)

    for rank in ranks:
        rdf = df[df["Rank"] == rank]
        rows = [("Total Members", len(rdf))]
        _push_metric("Total Members")
        for field, label in fields_for_rank_fn(rank):
            cnt = int(rdf[field].astype(str).str.lower().eq("yes").sum())
            rows.append((label, cnt))
            _push_metric(label)
        per_rank_data[rank] = dict(rows)

    # Stable color assignment: each metric gets the same color across all
    # subplots, drawn in encounter order from the palette.
    metric_colors = {m: palette[i % len(palette)]
                     for i, m in enumerate(metric_order)}

    # Compute global y-max for shared scale.
    ymax = 1
    for rank in ranks:
        if per_rank_data[rank]:
            ymax = max(ymax, max(per_rank_data[rank].values()))
    if ymax <= 10:    _ydtick = 1
    elif ymax <= 25:  _ydtick = 2
    elif ymax <= 50:  _ydtick = 5
    elif ymax <= 200: _ydtick = 10
    else:             _ydtick = 25

    fig = make_subplots(
        rows=1, cols=len(ranks),
        subplot_titles=ranks,
        shared_yaxes=True,
        horizontal_spacing=0.04,
    )

    seen_in_legend = set()
    for ci, rank in enumerate(ranks, start=1):
        rdata = per_rank_data[rank]
        for metric in metric_order:
            count = rdata.get(metric, 0)
            color = metric_colors[metric]
            show_in_legend = metric not in seen_in_legend
            seen_in_legend.add(metric)
            fig.add_trace(
                go.Bar(
                    x=[metric],
                    y=[count],
                    marker=dict(color=color, line=dict(width=0)),
                    text=[str(count)],
                    textposition="outside",
                    textfont=dict(family="Barlow Condensed, sans-serif",
                                  size=12, color="#ffffff"),
                    cliponaxis=False,
                    name=metric,
                    legendgroup=metric,
                    showlegend=show_in_legend,
                    width=0.7,
                    hovertemplate=(f"<b>{rank} · {metric}</b><br>"
                                   f"{count} member(s)<extra></extra>"),
                ),
                row=1, col=ci,
            )
        # X-axis: every metric pinned as a tick so narrow subplots don't auto-thin
        fig.update_xaxes(
            row=1, col=ci,
            type="category",
            categoryorder="array",
            categoryarray=metric_order,
            tickmode="array",
            tickvals=metric_order,
            ticktext=metric_order,
            showgrid=False,
            zeroline=False,
            showline=True,
            linecolor="rgba(240,192,48,0.2)",
            linewidth=1,
            tickangle=-30,
            tickfont=dict(family="Barlow Condensed, sans-serif",
                          size=10, color="#9dc4db"),
        )
        fig.update_yaxes(
            row=1, col=ci,
            tickformat="d",
            dtick=_ydtick,
            tick0=0,
            range=[0, ymax + max(2, ymax * 0.25)],
            showgrid=True,
            gridcolor="rgba(240,192,48,0.08)",
            zeroline=False,
            showline=(ci == 1),
            linecolor="rgba(240,192,48,0.2)",
            linewidth=1,
            title_text="Count" if ci == 1 else None,
            tickfont=dict(family="Barlow, sans-serif",
                          size=11, color="#9dc4db"),
        )

    for annot in fig.layout.annotations:
        annot.font = dict(family="Barlow Condensed, sans-serif",
                          size=13, color="#f0c030")

    _layout = {**CHART_LAYOUT}
    _layout["legend"] = {**(CHART_LAYOUT.get("legend") or {}),
                         "title": {"text": ""}}
    fig.update_layout(
        **_layout,
        margin=dict(t=60, b=70, l=20, r=20),
        title=dict(
            text=title,
            font=dict(family="Barlow Condensed, sans-serif",
                      size=14, color="#ffffff"),
        ),
        bargap=0.2,
    )

    return fig, metric_order


def pme_chart(df, title):
    """PME completion by rank — per-rank subplot layout with shared legend."""
    pme_ranks = ["SrA", "SSgt", "TSgt", "MSgt", "SMSgt"]
    return _credential_chart(df, title, chart_pme_fields, pme_ranks)


def edu_chart(df, title):
    """Higher Education by rank — per-rank subplot layout with shared legend."""
    edu_ranks = list(RANK_ORDER[:-1])
    edu_fields = [
        ("EDU_ASSOCIATES", "CCAF/Associates"),
        ("EDU_BACHELORS",  "Bachelors"),
        ("EDU_MASTERS",    "Masters"),
        ("EDU_DOCTORATE",  "Doctorate"),
    ]
    return _credential_chart(df, title,
                             lambda _r: edu_fields, edu_ranks)


def chart_card(fig, title=None, use_container_width=True, key=None):
    """Render a Plotly chart. Title (when provided) is rendered above the
    chart as a small uppercase header — no dark background panel since the
    chart itself already has a dark background.

    Plotly's mode bar (zoom, pan, screenshot, fullscreen, etc.) appears on
    hover. We keep it minimal: drop the lasso/select tools (rarely useful
    for these charts) but keep zoom, pan, autoscale, screenshot.
    """
    if title:
        st.markdown(
            f'<h3 style="font-family:Barlow Condensed,sans-serif;font-size:13px;'
            f'font-weight:700;letter-spacing:1px;text-transform:uppercase;'
            f'color:#9dc4db;margin:8px 0 4px 0;">{title}</h3>',
            unsafe_allow_html=True
        )
    kwargs = dict(
        use_container_width=use_container_width,
        config={
            "displayModeBar": "hover",
            "responsive": True,
            "displaylogo": False,
            "modeBarButtonsToRemove": [
                "lasso2d", "select2d", "autoScale2d", "toggleSpikelines",
            ],
            "toImageButtonOptions": {
                "format": "png",
                "filename": "wg_chart",
                "scale": 2,
            },
        },
    )
    if key: kwargs["key"] = key
    st.plotly_chart(fig, **kwargs)


def common_dashboard(dfx, title_prefix):
    sec_header("Rank Distribution")
    chart_card(chart_rank_distribution(dfx, f"{title_prefix} Rank Distribution"))
    sec_header("TIG / TIS")
    st.markdown('<div class="section-title">TIG by Rank</div>', unsafe_allow_html=True)
    tenure_pie(dfx.assign(TIGMonthsNum=dfx["DOR"].apply(parse_date).apply(months_since)), "TIGMonthsNum")
    st.markdown('<div class="section-title">TIS by Rank</div>', unsafe_allow_html=True)
    tenure_pie(dfx.assign(TISMonthsNum=dfx["DOE"].apply(parse_date).apply(months_since)), "TISMonthsNum")
    pfig, pmetrics = pme_chart(dfx, f"{title_prefix} Professional Military Education")
    sec_header("Professional Military Education")
    chart_card(pfig)
    efig, emetrics = edu_chart(dfx, f"{title_prefix} Higher Education")
    sec_header("Higher Education")
    chart_card(efig)


# ── Member form (shared by Edit and Add) ──────────────────────────────────────
def _clear_add_form_state():
    """Remove all 'add_' prefixed widget keys from session state so the Add
    Member form opens completely blank next time."""
    keys_to_delete = [k for k in st.session_state if k.startswith("add_")]
    for k in keys_to_delete:
        del st.session_state[k]


def _flight_options_for_tenant(tenant_id, df=None):
    """Return the list of flight option strings to show in a Flight dropdown
    for the given tenant_id.

    Source of truth: the canonical `flights` table managed in Administration.
    The optional `df` argument is used only as a fallback for two edge cases:
    (1) tenant_id is None (super-admin "All Units" scope), or (2) the tenant
    has no flights configured yet — in which case we surface whatever flight
    strings are already in the loaded member dataframe so the dropdown isn't
    empty for older data.

    Per design, this helper does NOT cascade canonical-list changes back to
    members; renaming or removing a flight option in Administration just
    changes what's selectable going forward — existing member assignments
    keep their stored flight string verbatim.
    """
    if tenant_id is not None:
        try:
            from database import get_flights_for_tenant
            rows = get_flights_for_tenant(tenant_id)
            names = [r.get("name", "") for r in rows if r.get("name")]
            if names:
                return sorted(names)
        except Exception:
            pass
    # Fallback: derive from member data if available.
    if df is not None and "Flight" in df.columns:
        return sorted(df["Flight"].dropna().unique().tolist())
    return []


def member_form(df, form_key_prefix, existing_row=None, flight_options=None):
    """
    Renders the full member data entry form.

    Parameters
    ----------
    df               : full DataFrame (used to derive flight list if not provided)
    form_key_prefix  : string prefix for all widget keys — use "edit" or "add"
    existing_row     : dict of existing values to pre-populate (None for blank / Add)
    flight_options   : list of flight strings to offer in the Flight selectbox

    Returns
    -------
    (saved: bool, cancelled: bool, new_row: dict | None)
        saved      — True when the user clicked Save
        cancelled  — True when the user clicked Cancel
        new_row    — the collected values dict when saved is True, else None
    """
    row = existing_row or {}
    pk  = form_key_prefix  # short alias
    is_add = existing_row is None  # True when adding a new member

    if flight_options is None:
        flight_options = sorted(df["Flight"].dropna().unique().tolist())

    # ── Basic info ────────────────────────────────────────────────────────────
    st.markdown("""<style>
div[class*="stTextInput"] > label p,
div[class*="stSelectbox"] > label p,
div[class*="stDateInput"] > label p,
div[class*="stNumberInput"] > label p {
    font-family: 'Barlow Condensed', sans-serif !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    color: #555 !important;
}
div[class*="stTextInput"] > label,
div[class*="stSelectbox"] > label,
div[class*="stDateInput"] > label,
div[class*="stNumberInput"] > label {
    background: rgba(0,0,0,0.05) !important;
    padding: 6px 12px 6px 12px !important;
    border-bottom: 1px solid rgba(0,0,0,0.10) !important;
    width: 100% !important;
    display: block !important;
    margin-bottom: 0 !important;
}
div[class*="stTextInput"] > div > div > input,
div[class*="stDateInput"] > div input {
    background: white !important;
}
div[class*="stSelectbox"] > div [data-baseweb="select"] > div {
    background: white !important;
}
div[class*="stTextInput"],
div[class*="stSelectbox"],
div[class*="stDateInput"],
div[class*="stNumberInput"] {
    border: 1px solid rgba(0,0,0,0.12) !important;
    border-radius: 4px !important;
    overflow: hidden !important;
    margin-bottom: 10px !important;
}
</style>""", unsafe_allow_html=True)
    a1, a2, a3, a4, a5 = st.columns(5)
    first_name = a1.text_input("First Name",  value=safe_text(row.get("FirstName","")),  key=f"{pk}_first")
    last_name  = a2.text_input("Last Name",   value=safe_text(row.get("LastName","")),   key=f"{pk}_last")
    rank = a3.selectbox(
        "Rank", [""] + RANK_ORDER[:-1] if is_add else RANK_ORDER[:-1],
        index=0 if is_add else (RANK_ORDER[:-1].index(row["Rank"]) if row.get("Rank") in RANK_ORDER[:-1] else 0),
        format_func=lambda x: "-- Select --" if x == "" else x,
        key=f"{pk}_rank"
    )

    # ── Squadron field ────────────────────────────────────────────────────────
    # Derive the squadron list from the tenants table. Super-admins can pick
    # any tenant; everyone else is locked to their own tenant. The selected
    # squadron is what determines the member's tenant_id on save.
    SQUADRON_UNIT_ORDER = [
        "195 WG HQ", "195 OG", "147 CBCS", "148 SOPS", "216 EWS", "261 COS",
        "195 ISRG", "149 IS", "222 ISS", "234 IS",
    ]
    try:
        from database import get_all_tenants as _gat
        _all_tenants = _gat()
    except Exception:
        _all_tenants = []
    _name_to_id = {t["name"]: t["id"] for t in _all_tenants}
    _id_to_name = {t["id"]: t["name"] for t in _all_tenants}
    _is_super = (st.session_state.get("role") == "super_admin")

    # Current squadron name for pre-selection
    _current_tid = row.get("_tenant_id")
    _current_squadron = _id_to_name.get(_current_tid, "")
    if not _current_squadron:
        # Fall back to the user's own tenant if the row didn't carry one
        _own_tid = st.session_state.get("tenant_id")
        _current_squadron = _id_to_name.get(_own_tid, "")

    if _is_super:
        squadron_opts = [""] + [n for n in SQUADRON_UNIT_ORDER if n in _name_to_id] if is_add else \
                        [n for n in SQUADRON_UNIT_ORDER if n in _name_to_id]
        try:
            _sq_idx = squadron_opts.index(_current_squadron)
        except ValueError:
            _sq_idx = 0
        squadron = a4.selectbox(
            "Unit", squadron_opts, index=_sq_idx,
            format_func=lambda x: "-- Select --" if x == "" else x,
            key=f"{pk}_squadron",
        )
    else:
        # Locked to the user's own unit
        squadron = _current_squadron or (st.session_state.get("tenant_name") or "")
        a4.text_input("Unit", value=squadron, key=f"{pk}_squadron_disp", disabled=True)

    cur_flight = safe_text(row.get("Flight",""))
    flight_opts_with_blank = [""] + flight_options if is_add else flight_options
    flight_idx = 0 if is_add else (flight_options.index(cur_flight) if cur_flight in flight_options else 0)
    flight = a5.selectbox("Flight", flight_opts_with_blank, index=flight_idx,
                          format_func=lambda x: "-- Select --" if x == "" else x,
                          key=f"{pk}_flight")

    # ── Dates, DAFSC & Skill Level ───────────────────────────────────────────
    r2a, r2b, r2c, r2d = st.columns(4)
    doe = r2a.date_input("Date of Entry", value=None if is_add else (parse_date(row.get("DOE","")) or date.today()),
                         format="MM/DD/YYYY", key=f"{pk}_doe")
    dor = r2b.date_input("Date of Rank",  value=None if is_add else (parse_date(row.get("DOR","")) or date.today()),
                         format="MM/DD/YYYY", key=f"{pk}_dor")
    dafsc = r2c.text_input("DAFSC",
                           value="" if is_add else safe_text(row.get("DAFSC", "")),
                           key=f"{pk}_dafsc")
    skill_keys = list(SKILL_LABELS.keys())
    if is_add:
        skill_keys_with_blank = [""] + skill_keys
        skill = r2d.selectbox("Skill Level", skill_keys_with_blank, index=0,
                              format_func=lambda x: "-- Select --" if x == "" else SKILL_LABELS[x],
                              key=f"{pk}_skill")
    else:
        raw_skill = safe_text(row.get("SkillLevel",""))
        try:
            raw_skill = str(int(float(raw_skill))) if raw_skill else "3"
        except (ValueError, TypeError):
            raw_skill = "3"
        if raw_skill not in skill_keys:
            raw_skill = "3"
        skill = r2d.selectbox("Skill Level", skill_keys, index=skill_keys.index(raw_skill),
                              format_func=lambda x: SKILL_LABELS[x], key=f"{pk}_skill")

    # ── Eval / Promo / ACA ────────────────────────────────────────────────────
    r3a, r3b, r3c = st.columns(3)
    last_eval = r3a.date_input("Last Eval Date", value=None if is_add else (parse_date(row.get("LastEval","")) or date.today()),
                               format="MM/DD/YYYY", key=f"{pk}_eval")
    promo_opts = ["N/A","Not Ready Now","Promote","Must Promote","Promote Now"]
    promo_opts_form = [""] + promo_opts if is_add else promo_opts
    cur_promo  = safe_text(row.get("PromoRecomm",""))
    promo = r3b.selectbox("Promotion Recommendation", promo_opts_form,
                          index=0 if is_add else (promo_opts.index(cur_promo) if cur_promo in promo_opts else 0),
                          format_func=lambda x: "-- Select --" if x == "" else x,
                          key=f"{pk}_promo")
    last_aca = r3c.date_input("Last ACA Date", value=None if is_add else (parse_date(row.get("LastACA","")) or date.today()),
                              format="MM/DD/YYYY", key=f"{pk}_aca")

    # ── PME ───────────────────────────────────────────────────────────────────
    st.markdown('<div class="kv-title">Professional Military Education</div>', unsafe_allow_html=True)
    st.markdown('<div class="hint">Select all that apply.</div>', unsafe_allow_html=True)
    pme_updates   = {}
    eligible_pme  = rank_gate_pme(rank)
    if eligible_pme:
        cols = st.columns(3)
        for i, (field, label) in enumerate(eligible_pme):
            pme_updates[field] = cols[i % 3].checkbox(
                label, value=yn(row.get(field,"No")), key=f"{pk}_pme_{field}")
    else:
        st.markdown('<div class="kv-value">No PME options for this rank.</div>', unsafe_allow_html=True)

    # ── Education ─────────────────────────────────────────────────────────────
    st.markdown('<div class="kv-title">Higher Education</div>', unsafe_allow_html=True)
    st.markdown('<div class="hint">Select all that apply.</div>', unsafe_allow_html=True)
    edu_updates = {}
    cols = st.columns(4)
    for i, (field, label) in enumerate(EDU_FIELDS):
        edu_updates[field] = cols[i % 4].checkbox(
            label, value=yn(row.get(field,"No")), key=f"{pk}_edu_{field}")

    # ── Leadership ────────────────────────────────────────────────────────────
    st.markdown('<div class="kv-title">Leadership Roles</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hint">Select all that apply for criteria met: '
        'AFSC/Supervisor experience held min 3 YRS. Program Manager experience held min. 1 YR. '
        'Flight Chief experience held min. 2 YRS. Senior Enlisted Leader experience held min. 2 YRS.</div>',
        unsafe_allow_html=True)
    existing_lead  = split_list_field(row.get("LeadershipRoles",""))
    existing_years = {}
    for item in existing_lead:
        low = item.lower(); digits = "".join(ch for ch in item if ch.isdigit()); yrs = int(digits) if digits else 0
        if "supervisor" in low:           existing_years["Supervisor"] = yrs
        elif "program manager" in low:    existing_years["Program Manager"] = yrs
        elif "flight chief" in low:       existing_years["Flight Chief"] = yrs
        elif "senior enlisted leader" in low: existing_years["Senior Enlisted Leader"] = yrs
    leadership_selected = []; leadership_years = {}
    for opt in LEADERSHIP_OPTIONS:
        left, right = st.columns([2,2])
        checked = left.checkbox(opt, value=any(opt.lower() in item.lower() for item in existing_lead),
                                key=f"{pk}_lead_{opt}")
        if checked:
            leadership_selected.append(opt)
            leadership_years[opt] = right.number_input(
                f"{opt} Years", min_value=0, max_value=20,
                value=int(existing_years.get(opt, 1)), step=1, key=f"{pk}_leadyrs_{opt}")

    # ── Assignments ───────────────────────────────────────────────────────────
    st.markdown('<div class="kv-title">Assignments</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hint">Select all that apply for criteria met: '
        'TDY/Exercise, Deployment, and Mobilization must be within the last 2 CY. '
        'Stat Tour, ADOS, WIT Team, Group Staff, Wing Staff, and Joint Tour require a min. of 1 YR.</div>',
        unsafe_allow_html=True)
    existing_assign = set(split_list_field(row.get("Assignments","")))
    existing_dates  = parse_keyed_dates(row.get("AssignmentsDate",""))
    assign_values   = []; assign_dates = {}
    for opt in ASSIGNMENT_OPTIONS:
        left, right = st.columns([2,2])
        checked = left.checkbox(opt, value=opt in existing_assign, key=f"{pk}_a_{opt}")
        if checked:
            assign_values.append(opt)
            if opt in ["TDY/Exercise","Deployment","Mobilization"]:
                dt = right.date_input(f"{opt} Date",
                                      value=parse_date(existing_dates.get(opt,"")) or None,
                                      format="MM/DD/YYYY", key=f"{pk}_d_{opt}")
                assign_dates[opt] = dt.strftime("%m/%d/%Y") if dt else ""

    # ── Awards ────────────────────────────────────────────────────────────────
    st.markdown('<div class="kv-title">Awards and Decorations</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hint">Select all that apply for criteria met: '
        'Federal/State Decoration must be within the last 3 CY. '
        'Wing/Group/Squadron Airman of the Quarter or Year must be within the last 2 CY.</div>',
        unsafe_allow_html=True)
    existing_awards     = set(split_list_field(row.get("AwardsDecs","")))
    existing_award_dates = parse_keyed_dates(row.get("AwardsDecsDate",""))
    award_values = []; award_dates = {}
    for opt in AWARD_OPTIONS:
        left, right = st.columns([2,2])
        checked = left.checkbox(opt, value=opt in existing_awards, key=f"{pk}_w_{opt}")
        if checked:
            award_values.append(opt)
            if opt == "Federal/State Decoration":
                dt = right.date_input("Date of Last Decoration",
                                      value=parse_date(existing_award_dates.get(opt,"")) or None,
                                      format="MM/DD/YYYY", key=f"{pk}_awd_dec")
                award_dates[opt] = dt.strftime("%m/%d/%Y") if dt else ""
            elif opt == "Wing/Group/Squadron Airman of the Quarter or Year":
                dt = right.date_input("Date Last Awarded",
                                      value=parse_date(existing_award_dates.get(opt,"")) or None,
                                      format="MM/DD/YYYY", key=f"{pk}_awd_qtr")
                award_dates[opt] = dt.strftime("%m/%d/%Y") if dt else ""

    # ── Fitness ───────────────────────────────────────────────────────────────
    st.markdown('<div class="kv-title">Fitness</div>', unsafe_allow_html=True)
    st.markdown('<div class="hint">Select highest PFA score in the last 2 years.</div>', unsafe_allow_html=True)
    fit_opts = ["Excellent","Satisfactory","N/A"]
    cur_fit  = safe_text(row.get("Fitness",""))
    if is_add:
        fitness = st.radio("Fitness", fit_opts, index=None,
                           horizontal=True, label_visibility="collapsed", key=f"{pk}_fitness")
    else:
        fitness = st.radio("Fitness", fit_opts,
                           index=fit_opts.index(cur_fit) if cur_fit in fit_opts else 1,
                           horizontal=True, label_visibility="collapsed", key=f"{pk}_fitness")

    # ── Professional Orgs ─────────────────────────────────────────────────────
    st.markdown('<div class="kv-title">Professional Organizations</div>', unsafe_allow_html=True)
    st.markdown('<div class="hint">Select all that apply.</div>', unsafe_allow_html=True)
    existing_orgs = set(split_list_field(row.get("ProfOrgMbr","")))
    org_selected  = []
    # Show all orgs when rank is blank (add mode, no rank chosen yet); otherwise filter by rank
    visible_orgs = [name for name, ranks in ORG_FIELDS] if (is_add and not rank) else prof_org_options(rank)
    if visible_orgs:
        cols = st.columns(3)
        for i, opt in enumerate(visible_orgs):
            checked = cols[i % 3].checkbox(opt, value=opt in existing_orgs, key=f"{pk}_o_{opt}")
            if checked:
                org_selected.append(opt)
    else:
        st.markdown('<div class="kv-value">No organization options for this rank.</div>', unsafe_allow_html=True)

    # ── Notes ─────────────────────────────────────────────────────────────────
    st.markdown('<div class="kv-title">Supervisor Notes</div>', unsafe_allow_html=True)
    st.markdown('<div class="hint">A place to capture standards/expectations, goals, and action items.</div>',
                unsafe_allow_html=True)
    supervisor_notes = st.text_area("", value=safe_text(row.get("SupervisorNotes","")),
                                    key=f"{pk}_sup_notes")

    st.markdown('<div class="kv-title">Ratee Notes</div>', unsafe_allow_html=True)
    st.markdown('<div class="hint">A place to capture standards/expectations, goals, and action items.</div>',
                unsafe_allow_html=True)
    ratee_notes = st.text_area("", value=safe_text(row.get("RateeNotes","")),
                               key=f"{pk}_ratee_notes")

    # ── Save / Cancel buttons ─────────────────────────────────────────────────
    btn1, btn2, _ = st.columns([1, 1, 5])
    save_clicked   = btn1.button("Save",   type="primary", key=f"{pk}_save")
    cancel_clicked = btn2.button("Cancel", type="primary", key=f"{pk}_cancel")

    # White buffer space below Save / Cancel for both Edit Member and Add Member views
    st.markdown("<div style='height:48px;'></div>", unsafe_allow_html=True)

    if cancel_clicked:
        return False, True, None

    if save_clicked:
        # ── Validation for add mode ───────────────────────────────────────────
        fmt_date = lambda d: d.strftime("%m/%d/%Y") if d else ""
        errors = []
        if is_add:
            if not first_name.strip():  errors.append("First Name is required.")
            if not last_name.strip():   errors.append("Last Name is required.")
            if not rank:                errors.append("Rank is required.")
            if not squadron:            errors.append("Squadron is required.")
            if not flight:              errors.append("Flight is required.")
            if not skill:               errors.append("Skill Level is required.")
            if not promo:               errors.append("Promotion Recommendation is required.")
            if not fitness:             errors.append("Fitness is required.")
        if errors:
            for e in errors:
                st.error(e)
            return False, False, None

        # Compile PME — start from blanked slate so unchecked boxes clear properly
        pme_compiled = {field: "No" for field, _ in PME_FIELDS}
        pme_compiled.update({f: ("Yes" if v else "No") for f, v in pme_updates.items()})

        leadership_compiled = [
            f"{role} {leadership_years.get(role,0)} years"
            for role in leadership_selected
        ]

        # Resolve the picked squadron name back to a tenant_id
        _squadron_tid = _name_to_id.get(squadron) if squadron else None

        new_row = {
            "FirstName":       first_name,
            "LastName":        last_name,
            "Rank":            rank,
            "Flight":          flight,
            "_tenant_id":      _squadron_tid,
            "DOE":             fmt_date(doe),
            "DOR":             fmt_date(dor),
            "DAFSC":           safe_text(dafsc),
            "SkillLevel":      skill,
            "LastEval":        fmt_date(last_eval),
            "PromoRecomm":     promo,
            "LastACA":         fmt_date(last_aca),
            "Fitness":         fitness,
            "Assignments":     join_list_field(assign_values),
            "AssignmentsDate": join_keyed_dates(assign_dates),
            "AwardsDecs":      join_list_field(award_values),
            "AwardsDecsDate":  join_keyed_dates(award_dates),
            "ProfOrgMbr":      join_list_field(org_selected),
            "LeadershipRoles": join_list_field(leadership_compiled),
            "SupervisorNotes": supervisor_notes,
            "RateeNotes":      ratee_notes,
            "LastEdit":        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **pme_compiled,
            **{f: ("Yes" if v else "No") for f, v in edu_updates.items()},
        }
        return True, False, new_row

    return False, False, None


# ── Individual Profile page ───────────────────────────────────────────────────
def page_individual_profile(df):
    # ── Unit / Flight selector (same hierarchical pattern as Squadron Overview) ──
    SQUADRON_UNIT_ORDER = [
        "195 WG HQ",
        "195 OG",
        "147 CBCS",
        "148 SOPS",
        "216 EWS",
        "261 COS",
        "195 ISRG",
        "149 IS",
        "222 ISS",
        "234 IS",
    ]

    try:
        from database import get_all_tenants as _gat
        _tenant_lookup = {t["id"]: t["name"] for t in _gat()}
    except Exception:
        _tenant_lookup = {}

    df_with_unit = df.copy()
    if "_tenant_id" in df_with_unit.columns:
        df_with_unit["_unit_name"] = df_with_unit["_tenant_id"].map(
            lambda tid: _tenant_lookup.get(tid) if pd.notna(tid) else None
        )
    else:
        df_with_unit["_unit_name"] = st.session_state.get("tenant_name") or None

    def _flights_for(unit_name):
        sub = df_with_unit[df_with_unit["_unit_name"] == unit_name]
        flights = sub["Flight"].dropna().astype(str).str.strip()
        flights = flights[flights != ""]
        return sorted(flights.unique().tolist())

    uf_options = [("none", None, None), ("all", None, None)]
    for unit_name in SQUADRON_UNIT_ORDER:
        uf_options.append(("unit", unit_name, None))
        for flight_name in _flights_for(unit_name):
            uf_options.append(("flight", unit_name, flight_name))

    def _uf_fmt(opt):
        kind, unit_name, flight_name = opt
        if kind == "none":
            return "No option selected"
        if kind == "all":
            return "All Units"
        if kind == "unit":
            return unit_name
        # Two-line stacked: unit on top, indented flight beneath.
        return f"{unit_name}\n\u00a0\u00a0\u00a0\u00a0↳ {flight_name}"

    # CSS to render newlines in the two selectboxes on this page.
    st.markdown("""
    <style>
    /* Individual Profile selectboxes: render \\n as line breaks. */
    .st-key-individual_unit_flight [data-baseweb="select"] *,
    .st-key-individual_unit_flight [role="option"],
    .st-key-individual_unit_flight [role="option"] *,
    .st-key-individual_member_select [data-baseweb="select"] *,
    .st-key-individual_member_select [role="option"],
    .st-key-individual_member_select [role="option"] * {
        white-space: pre-line !important;
        line-height: 1.25 !important;
    }
    .st-key-individual_unit_flight [data-baseweb="select"] > div,
    .st-key-individual_member_select [data-baseweb="select"] > div {
        min-height: 44px !important;
        height: auto !important;
        padding-top: 4px !important;
        padding-bottom: 4px !important;
    }
    [data-baseweb="popover"] [role="option"] {
        min-height: 36px !important;
        height: auto !important;
        padding-top: 6px !important;
        padding-bottom: 6px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    uf_sel = st.selectbox(
        "Select Unit / Flight",
        uf_options,
        format_func=_uf_fmt,
        key="individual_unit_flight",
    )
    uf_kind, uf_unit, uf_flight = uf_sel

    # Mirror the Unit selection into tenant_name as a non-authoritative cache
    # (the banner reads selectbox state directly so this update is just for
    # any other code paths that still rely on tenant_name).
    if uf_kind == "none" or uf_kind == "all":
        st.session_state["tenant_name"] = "All Units"
    elif uf_kind in ("unit", "flight") and uf_unit:
        st.session_state["tenant_name"] = uf_unit

    # Filter members down based on the Unit / Flight pick.
    if uf_kind == "none":
        fdf = df_with_unit.iloc[0:0]   # empty until they choose
    elif uf_kind == "all":
        fdf = df_with_unit.copy()
    elif uf_kind == "unit":
        fdf = df_with_unit[df_with_unit["_unit_name"] == uf_unit].copy()
    else:  # flight
        fdf = df_with_unit[
            (df_with_unit["_unit_name"] == uf_unit)
            & (df_with_unit["Flight"].astype(str).str.strip() == uf_flight)
        ].copy()

    # ── Member selector (searchable; native typing-to-filter on st.selectbox) ──
    if uf_kind == "none":
        st.markdown(
            '<div style="margin:6px 0 18px 0;padding:0;color:#9dc4db;'
            'font-family:Barlow Condensed,sans-serif;font-size:13px;'
            'letter-spacing:1.5px;text-transform:uppercase;">'
            'Select a unit or flight from the dropdown above to browse members.</div>',
            unsafe_allow_html=True,
        )
        # Still let them open the Add Member view
        member_options_for_picker = [("none", None)]
        st.selectbox(
            "Select Member",
            member_options_for_picker,
            format_func=lambda o: "No member selected",
            key="individual_member_select",
            disabled=True,
        )
        sel_member = None
    else:
        # Build member option list; "No member selected" first so a fresh
        # Unit/Flight pick doesn't immediately force a member-page render.
        # Sort: lowest rank first (Amn → CMSgt), then last name alphabetically,
        # then first name as a final tiebreaker. Members with an unrecognized
        # rank fall to the bottom of the list.
        _rank_idx = {r: i for i, r in enumerate(RANK_ORDER)}
        def _member_sort_key(r):
            rank = (r.get("Rank") or "").strip()
            return (
                _rank_idx.get(rank, len(RANK_ORDER)),
                (r.get("LastName") or "").strip().lower(),
                (r.get("FirstName") or "").strip().lower(),
            )
        member_rows = sorted(
            fdf.dropna(subset=["FullName"]).to_dict("records"),
            key=_member_sort_key,
        )
        member_options_for_picker = [("none", None)] + [
            ("member", r) for r in member_rows
        ]

        def _member_fmt(opt):
            kind, r = opt
            if kind == "none":
                return "No member selected"
            # FullName already contains "Rank FirstName LastName" — using it as-is
            # avoids the duplicate-rank bug. Fall back to "Last, First" if for
            # some reason FullName is missing.
            full = r.get("FullName")
            if not full:
                full = f"{safe_text(r.get('LastName',''))}, {safe_text(r.get('FirstName',''))}"
            return safe_text(full)

        # Try to keep the previously-selected member if still in scope
        _prev = st.session_state.get("selected_member") or ""
        _idx = 0
        if _prev:
            for i, opt in enumerate(member_options_for_picker):
                if opt[0] == "member" and opt[1].get("FullName") == _prev:
                    _idx = i
                    break

        if not member_rows:
            st.warning("No members are available for the selected unit / flight.")
            sel_member = None
            st.selectbox(
                "Select Member",
                [("none", None)],
                format_func=lambda o: "No member selected",
                key="individual_member_select",
                disabled=True,
            )
        else:
            picked = st.selectbox(
                "Select Member",
                member_options_for_picker,
                index=_idx,
                format_func=_member_fmt,
                key="individual_member_select",
            )
            if picked[0] == "none":
                sel_member = None
            else:
                sel_member = picked[1].get("FullName")
                st.session_state.selected_member = sel_member
                st.session_state.locked_member   = sel_member
                _flt = picked[1].get("Flight")
                if _flt:
                    st.session_state.selected_flight = _flt
                    st.session_state.locked_flight   = _flt

    if sel_member is None:
        # Nothing rendered below until a member is picked.
        return

    # ── Resolve selected member into a row ─────────────────────────────────
    _matches = df.index[df["FullName"] == sel_member]
    if len(_matches) == 0:
        st.warning("Selected member could not be found in the loaded data.")
        return
    idx = _matches[0]
    row = df.loc[idx].to_dict()

    tabs = ["Member Profile"] + (["Scorecard"] if row["Rank"] in BOARD_RANKS else [])
    tab_objs = st.tabs(tabs)

    # ── Scorecard tab ─────────────────────────────────────────────
    if row["Rank"] in BOARD_RANKS:
        with tab_objs[1]:
            # No sec_header - tab already says Scorecard
            scorecard, cats = scorecard_summary(row)
            st.markdown(
                f'<p style="font-family:Barlow Condensed,sans-serif;font-size:0.85rem;'
                f'color:#7a93c0;letter-spacing:1px;text-transform:uppercase;margin-bottom:16px;">'
                f'<span style="color:#1a2a5e;font-weight:700;">Scorecard Used:</span> <span style="color:#7a93c0;">{scorecard}</span></p>',
                unsafe_allow_html=True)
            score_df, total, total_max = score_table_df(cats)

            fig = px.bar(score_df[score_df["Category"]!="Total"],
                         x="Category", y=["Total Score","Max Score"],
                         barmode="group", color_discrete_sequence=COLORS[:2],
                         )
            fig.update_layout(**CHART_LAYOUT, showlegend=True,
                               title=dict(text="Board Score by Category", font=dict(size=14, color="#ffffff", family="Barlow Condensed, sans-serif")))
            fig.update_traces(texttemplate="%{y}", textposition="outside", cliponaxis=False)
            fig.update_yaxes(tickformat="d", dtick=1, tick0=0)
            st.plotly_chart(fig, use_container_width=True)

            fig2 = go.Figure()
            fig2.add_trace(go.Bar(x=[total_max], y=["Total Score"], orientation="h",
                                  marker_color=COLORS[1], width=0.25,
                                  name="Total Possible", text=[total_max], textposition="inside"))
            fig2.add_trace(go.Bar(x=[total], y=["Total Score"], orientation="h",
                                  marker_color=COLORS[0], width=0.25,
                                  name="Member Total", text=[total], textposition="inside"))
            fig2.update_layout(**CHART_LAYOUT, barmode="overlay", showlegend=True, height=200,
                               margin=dict(t=40,b=10,l=10,r=10),
                               title=dict(text="Total Score Summary", font=dict(size=14, color="#ffffff", family="Barlow Condensed, sans-serif")))
            st.plotly_chart(fig2, use_container_width=True)

            # Table styled like index.html
            _score_display = score_df.copy()
            _rows_html = ""
            for _, r in _score_display.iterrows():
                _is_total = r["Category"] == "Total"
                _row_style = "background:#1f3272;font-weight:700;" if _is_total else ""
                _rows_html += (
                    f'<tr style="{_row_style}">'
                    f'<td style="padding:10px 13px;border-bottom:1px solid rgba(240,192,48,0.1);color:{"#f0c030" if _is_total else "#dde6f5"};font-size:14px;">{r["Category"]}</td>'
                    f'<td style="padding:10px 13px;border-bottom:1px solid rgba(240,192,48,0.1);color:{"#ffffff" if _is_total else "#dde6f5"};font-size:14px;text-align:center;font-family:Barlow Condensed,sans-serif;font-weight:600;">{int(r["Total Score"])}</td>'
                    f'<td style="padding:10px 13px;border-bottom:1px solid rgba(240,192,48,0.1);color:#7a93c0;font-size:14px;text-align:center;">{int(r["Max Score"])}</td>'
                    f'<td style="padding:10px 13px;border-bottom:1px solid rgba(240,192,48,0.1);color:#7a93c0;font-size:13px;">{r["Detail"]}</td>'
                    f'</tr>'
                )
            st.markdown(
                '<div style="overflow-x:auto;border-radius:8px;border:1px solid rgba(240,192,48,0.2);margin-bottom:40px;">'
                '<table style="width:100%;border-collapse:collapse;font-size:14px;">'
                '<thead><tr style="background:#1f3272;">'
                '<th style="font-family:Barlow Condensed,sans-serif;font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#f0c030;padding:11px 13px;text-align:left;border-bottom:1px solid rgba(240,192,48,0.2);">Category</th>'
                '<th style="font-family:Barlow Condensed,sans-serif;font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#f0c030;padding:11px 13px;text-align:center;border-bottom:1px solid rgba(240,192,48,0.2);">Score</th>'
                '<th style="font-family:Barlow Condensed,sans-serif;font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#f0c030;padding:11px 13px;text-align:center;border-bottom:1px solid rgba(240,192,48,0.2);">Max</th>'
                '<th style="font-family:Barlow Condensed,sans-serif;font-size:13px;letter-spacing:1px;text-transform:uppercase;color:#f0c030;padding:11px 13px;text-align:left;border-bottom:1px solid rgba(240,192,48,0.2);">Detail</th>'
                '</tr></thead>'
                f'<tbody style="background:#162050;">{_rows_html}</tbody>'
                '</table></div>',
                unsafe_allow_html=True)

    # ── Member Profile tab ────────────────────────────────────────
    with tab_objs[0]:
        # Resolve the squadron name from the row's tenant_id using the lookup
        # built at the top of this function.
        _squadron_name = _tenant_lookup.get(row.get("_tenant_id"), "") if isinstance(_tenant_lookup, dict) else ""
        if not _squadron_name:
            _squadron_name = st.session_state.get("tenant_name") or ""

        r1 = st.columns(5)
        with r1[0]: render_kv("Rank", row["Rank"])
        with r1[1]: render_kv("First Name", row["FirstName"])
        with r1[2]: render_kv("Last Name", row["LastName"])
        with r1[3]: render_kv("Unit", _squadron_name)
        with r1[4]: render_kv("Flight", row["Flight"])

        r2 = st.columns(4)
        with r2[0]: render_kv("Date of Entry", row["DOE"])
        with r2[1]: render_kv("Time in Service", row["TIS"])
        with r2[2]: render_kv("Date of Rank", row["DOR"])
        with r2[3]: render_kv("Time in Grade", row["TIG"])

        r3 = st.columns(3)
        with r3[0]: render_kv("Last Eval Date", row["LastEval"])
        with r3[1]: render_kv("Promotion Recommendation", row["PromoRecomm"])
        with r3[2]: render_kv("Last ACA Date", row["LastACA"])

        pme_items = [label for field,label in rank_gate_pme(row["Rank"]) if yn(row.get(field,"No"))]
        edu_items = [label for field,label in EDU_FIELDS if yn(row.get(field,"No"))]
        leadership_items = split_list_field(row.get("LeadershipRoles",""))
        assign_items     = split_list_field(row.get("Assignments",""))
        assign_dates     = parse_keyed_dates(row.get("AssignmentsDate",""))
        award_items      = split_list_field(row.get("AwardsDecs",""))
        award_dates      = parse_keyed_dates(row.get("AwardsDecsDate",""))
        org_items        = split_list_field(row.get("ProfOrgMbr",""))

        assign_display = (
            "<br>".join([f"{item} ({assign_dates.get(item)})"
                         if safe_text(assign_dates.get(item)) else item
                         for item in assign_items])
            if assign_items else "None recorded"
        )
        award_display = (
            "<br>".join([f"{item} ({award_dates.get(item)})"
                         if safe_text(award_dates.get(item)) else item
                         for item in award_items])
            if award_items else "None recorded"
        )

        row5 = st.columns(4)
        with row5[0]:
            render_kv("DAFSC", safe_text(row.get("DAFSC", "")) or "Not recorded")
        with row5[1]:
            render_kv("Skill Level", SKILL_LABELS.get(safe_text(row["SkillLevel"]), safe_text(row["SkillLevel"])))
        with row5[2]:
            st.markdown(
            f'<div class="kv-wrap"><div class="kv-title">Professional Military Education</div><div class="kv-value">{"<br>".join(pme_items) if pme_items else "None recorded"}</div></div>', unsafe_allow_html=True)
        with row5[3]:
            st.markdown(
            f'<div class="kv-wrap"><div class="kv-title">Higher Education</div><div class="kv-value">{"<br>".join(edu_items) if edu_items else "None recorded"}</div></div>', unsafe_allow_html=True)

        row6 = st.columns(3)
        with row6[0]:
            st.markdown(
            f'<div class="kv-wrap"><div class="kv-title">Leadership Roles</div><div class="kv-value">{"<br>".join(leadership_items) if leadership_items else "None recorded"}</div></div>', unsafe_allow_html=True)
        with row6[1]:
            st.markdown(
            f'<div class="kv-wrap"><div class="kv-title">Assignments</div><div class="kv-value">{assign_display}</div></div>', unsafe_allow_html=True)
        with row6[2]:
            st.markdown(
            f'<div class="kv-wrap"><div class="kv-title">Awards and Decorations</div><div class="kv-value">{award_display}</div></div>', unsafe_allow_html=True)

        row7 = st.columns(2)
        with row7[0]: render_kv("Fitness", row["Fitness"])
        with row7[1]:
            st.markdown(
            f'<div class="kv-wrap"><div class="kv-title">Professional Organizations</div><div class="kv-value">{"<br>".join(org_items) if org_items else "None recorded"}</div></div>', unsafe_allow_html=True)

        # Supervisor Notes — match the Edit/Add Member styling
        # (kv-title gray bar + hint subtitle + bordered card around value)
        st.markdown('<div class="kv-title">Supervisor Notes</div>', unsafe_allow_html=True)
        st.markdown('<div class="hint">A place to capture standards/expectations, goals, and action items.</div>', unsafe_allow_html=True)
        _sup = safe_text(row.get("SupervisorNotes","")) or "No notes recorded."
        st.markdown(
            f'<div style="border:1px solid rgba(0,0,0,0.12);border-radius:4px;'
            f'padding:12px 14px;margin-bottom:16px;font-family:Barlow,sans-serif;'
            f'font-size:0.95rem;color:#111;">{_sup}</div>',
            unsafe_allow_html=True)

        st.markdown('<div class="kv-title">Ratee Notes</div>', unsafe_allow_html=True)
        st.markdown('<div class="hint">A place to capture standards/expectations, goals, and action items.</div>', unsafe_allow_html=True)
        _rat = safe_text(row.get("RateeNotes","")) or "No notes recorded."
        st.markdown(
            f'<div style="border:1px solid rgba(0,0,0,0.12);border-radius:4px;'
            f'padding:12px 14px;margin-bottom:32px;font-family:Barlow,sans-serif;'
            f'font-size:0.95rem;color:#111;">{_rat}</div>',
            unsafe_allow_html=True)

        _le = format_dt(row.get("LastEdit",""))
        st.markdown(
            f'<p style="font-family:Barlow Condensed,sans-serif;font-size:0.78rem;' +
            f'font-weight:700;letter-spacing:1.5px;text-transform:uppercase;' +
            f'color:#1a2a5e;margin:0 0 2px 0;">Last Modified</p>' +
            f'<p style="font-family:Barlow,sans-serif;font-size:0.9rem;color:#1a2a5e;margin-bottom:24px;">{_le}</p>',
            unsafe_allow_html=True)

        # ── Edit Member / Add Member buttons ──────────────────────
        # The active-yellow state when a view is open is handled by
        # the polling JS in app.py (which tags the button with
        # data-active="true" based on st.session_state.edit_open /
        # add_open exposed via #wg-active-state). The CSS lives in
        # apply_theme().
        st.markdown("<div style='padding-bottom:0;'></div>", unsafe_allow_html=True)
        st.markdown("---")

        btn_col1, btn_col2, _ = st.columns([1, 1, 5])
        st.markdown("<div style='padding-bottom:40px;'></div>", unsafe_allow_html=True)
        if btn_col1.button("Edit Member", type="primary", key="edit_member_btn"):
            st.session_state.edit_open = not st.session_state.edit_open
            st.session_state.add_open  = False
            st.rerun()
        if btn_col2.button("✚  Add Member", key="add_member_btn", type="primary"):
            st.session_state.add_open  = not st.session_state.add_open
            st.session_state.edit_open = False
            st.rerun()

        if st.session_state.edit_open:
            st.markdown("---")
            sec_header("Edit Member")
            saved, cancelled, new_row = member_form(
                df, form_key_prefix="edit", existing_row=row,
                flight_options=_flight_options_for_tenant(
                    st.session_state.get("active_tenant_id"), df
                )
            )
            if cancelled:
                st.session_state.edit_open = False
                st.rerun()
            if saved and new_row:
                for col, val in new_row.items():
                    df.loc[idx, col] = val
                df = recompute_tenure(df)
                save_data(df)
                st.session_state.edit_open = False
                st.success("Member updated.")
                st.rerun()

        # ── Add Member form (scoped to the Member Profile tab) ────
        if st.session_state.add_open:
            sec_header("Add New Member")
            saved, cancelled, new_row = member_form(
                df, form_key_prefix="add", existing_row=None,
                flight_options=_flight_options_for_tenant(
                    st.session_state.get("active_tenant_id"), df
                )
            )
            if cancelled:
                _clear_add_form_state()
                st.session_state.add_open = False
                st.rerun()
            if saved and new_row:
                # Append new row to DataFrame
                new_row["TIG"] = "0y 0m"
                new_row["TIS"] = "0y 0m"
                new_df = pd.concat([df.drop(columns=["FullName","TIGMonthsNum","TISMonthsNum"], errors="ignore"),
                                     pd.DataFrame([new_row])], ignore_index=True)
                new_df = recompute_tenure(new_df)
                save_data(new_df)
                _clear_add_form_state()
                st.session_state.add_open = False
                st.success(f"Member {new_row.get('FirstName','')} {new_row.get('LastName','')} added.")
                st.rerun()


# ── Force Development page (SNCO Stratification Dashboard) ──────────────────
# Reads a Microsoft Forms Excel export of evaluation rubric submissions and
# renders an Org-level / per-rank dashboard with submission stats, score
# histograms, optional stratification scores, and Excel-style filterable
# MSgt and SMSgt rosters. Restricted in app.py to super-admin OR
# title in {Commander, SEL, Senior Enlisted Leader}.

# Canonical unit ordering — used for the SNCO Stratification dropdown,
# the Promotion Scorecard dropdown, and the Unit/Flight dropdown on
# Individual Profile / Unit Overview. Keep this single source of truth.
FD_ORGS = [
    "195 WG HQ",
    "195 OG",
    "147 CBCS",
    "148 SOPS",
    "216 EWS",
    "261 COS",
    "195 ISRG",
    "149 IS",
    "222 ISS",
    "234 IS",
]

FD_EVAL_RECORD_COLS = [
    # (key, label, max_pts)
    ("experience",  "Experience",                 5),
    ("education",   "Education",                  5),
    ("awards",      "Awards",                     5),
    ("decorations", "Decorations",                5),
    ("evalTotal",   "Eval of Record Total Score", 20),
]
FD_EPB_COLS = [
    # (key, label, max_pts)
    ("execMission", "Executing Mission",          5),
    ("leadPeople",  "Leading People",             5),
    ("manageRes",   "Managing Resources",         5),
    ("improveUnit", "Improving the Unit",         5),
    ("epbTotal",    "Current EPB Total Score",   20),
]


def _fd_num(v):
    """Parse a numeric value, return None for blanks/invalid."""
    if v is None or v == "" or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fd_str(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    # pandas turns missing cells into NaN, which str() converts to "nan".
    # Treat that and a few common placeholders as empty so we don't accept
    # them as valid identifying fields.
    if s.lower() in ("nan", "nat", "none", "null"):
        return ""
    return s


def _fd_norm_rank(r):
    s = _fd_str(r)
    if not s:
        return ""
    u = s.upper()
    if u in ("MSGT", "MSG", "E7"):  return "MSgt"
    if u in ("SMSGT", "SMSG", "E8"): return "SMSgt"
    return s


def _fd_fmt_completion(v):
    """Render a completion-time cell as 'YYYY-MM-DD HH:MM' or fallback."""
    if v is None or v == "":
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M")
    s = str(v).strip()
    # Try to parse ISO-ish strings
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%m/%d/%Y %H:%M", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    return s


def _fd_parse_excel(uploaded_bytes):
    """Read an .xlsx into a list of normalized member dicts.

    Returns (members, error_message, debug_info). Members is a list of
    dicts; error_message is a string when parsing fails (and members will
    be empty); debug_info is a dict with column names, row counts, and
    rejection reasons that the page surfaces when no rows make it through."""
    debug = {"columns": [], "row_count": 0, "rejected": [], "first_row": {}}
    try:
        xls_df = pd.read_excel(uploaded_bytes, sheet_name=0)
    except Exception as e:
        return [], f"Could not read Excel file: {e}", debug

    debug["columns"]   = [str(c) for c in xls_df.columns]
    debug["row_count"] = int(len(xls_df))

    # Map free-form column names that begin with known prefixes — Microsoft
    # Forms appends question-id suffixes like "Executing the Mission (xyz)".
    keys = list(xls_df.columns)
    def find_prefix(prefix):
        for k in keys:
            if str(k).startswith(prefix):
                return k
        return None

    exec_col    = find_prefix("Executing the Mission")
    lead_col    = find_prefix("Leading People")
    manage_col  = find_prefix("Managing Resources")
    improve_col = find_prefix("Improving the Unit")
    epb_col     = find_prefix("Current EPB")

    members = []
    for idx, r in xls_df.iterrows():
        rank = _fd_norm_rank(r.get("Rank", ""))
        # In this Microsoft Forms export, each row contains the rater's
        # identity in `Name` and the ratee's identity in `Name2`. The rest
        # of the row (Rank, Unit, AFSC, scores, etc.) describes the ratee.
        # If `Name2` is empty the row has no identifiable subject and is
        # skipped — we do NOT fall back to `Name` (the rater).
        name = _fd_str(r.get("Name2"))
        unit = _fd_str(r.get("Unit"))
        if not (name and rank and unit):
            if len(debug["rejected"]) < 5:  # first 5 rejected rows
                debug["rejected"].append({
                    "row": int(idx) + 2,  # 1-based + header
                    "name": name or "(missing)",
                    "rank": rank or "(missing)",
                    "unit": unit or "(missing)",
                })
            continue
        if not debug["first_row"]:
            debug["first_row"] = {"name": name, "rank": rank, "unit": unit}
        members.append({
            "name":           name,
            "unit":           unit,
            "rank":           rank,
            "afsc":           _fd_str(r.get("AFSC")),
            "dutyTitle":      _fd_str(r.get("Duty Title")),
            "tos":            _fd_str(r.get("Time in Service:")),
            "dor":            _fd_str(r.get("Date of Rank:")),
            "education":      _fd_num(r.get("Education")),
            "experience":     _fd_num(r.get("Experience")),
            "awards":         _fd_num(r.get("Awards")),
            "decorations":    _fd_num(r.get("Decorations")),
            "evalTotal":      _fd_num(r.get("Evaluation of Record Total Score")),
            "execMission":    _fd_num(r.get(exec_col))    if exec_col    else None,
            "leadPeople":     _fd_num(r.get(lead_col))    if lead_col    else None,
            "manageRes":      _fd_num(r.get(manage_col))  if manage_col  else None,
            "improveUnit":    _fd_num(r.get(improve_col)) if improve_col else None,
            "epbTotal":       _fd_num(r.get(epb_col))     if epb_col     else None,
            "stratScore":     _fd_num(r.get("Stratification Overall Score")),
            "submitStrat":    _fd_str(r.get("Submit for Stratification?")).upper(),
            "noReason":       _fd_str(r.get("Provide reason for non-stratification selection")),
            "completionTime": _fd_fmt_completion(r.get("Completion time")),
        })

    # ── Deduplicate ───────────────────────────────────────────────────────────
    # If the same ratee (Name2 + Rank) appears in multiple rows — even rated
    # under two different units — keep only the MOST RECENT submission,
    # decided by Completion time. Unit is intentionally NOT part of the key:
    # we want one record per person, taking the latest data we have for them.
    import re as _re
    def _norm_name(s):
        # Lowercase, strip punctuation, collapse whitespace, sort the words so
        # "First Last" / "Last, First" / "first  last" all match.
        s = (s or "").lower()
        s = _re.sub(r"[^\w\s]", " ", s)
        return " ".join(sorted(s.split()))
    def _norm_rank_key(s):
        return _fd_norm_rank(s).lower()

    by_key = {}
    duplicates_dropped = 0
    for m in members:
        key = (
            _norm_name(m.get("name")),
            _norm_rank_key(m.get("rank")),
        )
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = m
        else:
            # Keep the MOST RECENT submission. completionTime is formatted
            # "YYYY-MM-DD HH:MM" by _fd_fmt_completion, so lexicographic
            # comparison matches chronological order. If both are equal or
            # blank, the later-listed row in the file wins (later rows tend
            # to be later submissions in MS Forms exports).
            duplicates_dropped += 1
            new_t = m.get("completionTime") or ""
            old_t = existing.get("completionTime") or ""
            if new_t >= old_t:
                by_key[key] = m
    members = list(by_key.values())
    debug["duplicates_dropped"] = duplicates_dropped
    return members, "", debug


def _strat_record_to_db_row(m: dict) -> dict:
    """Convert a parsed _fd_parse_excel record into a strat_records DB row.
    Drops UI-only fields (dutyTitle, tos, dor, noReason) that aren't persisted."""
    return {
        "name":            m.get("name"),
        "rank":            m.get("rank"),
        "unit":            m.get("unit"),
        "afsc":            m.get("afsc"),
        "experience":      m.get("experience"),
        "education":       m.get("education"),
        "awards":          m.get("awards"),
        "decorations":     m.get("decorations"),
        "eval_total":      m.get("evalTotal"),
        "exec_mission":    m.get("execMission"),
        "lead_people":     m.get("leadPeople"),
        "manage_res":      m.get("manageRes"),
        "improve_unit":    m.get("improveUnit"),
        "epb_total":       m.get("epbTotal"),
        "submit_strat":    m.get("submitStrat"),
        "strat_score":     m.get("stratScore"),
        "completion_time": m.get("completionTime"),
    }


def _strat_db_row_to_record(r: dict) -> dict:
    """Inverse of _strat_record_to_db_row. Re-shapes a row from the DB into
    the record dict the rest of the page expects (camelCase keys, etc)."""
    return {
        "name":           r.get("name"),
        "rank":           r.get("rank"),
        "unit":           r.get("unit"),
        "afsc":           r.get("afsc"),
        "dutyTitle":      "",      # not persisted
        "tos":            "",      # not persisted
        "dor":            "",      # not persisted
        "experience":     r.get("experience"),
        "education":      r.get("education"),
        "awards":         r.get("awards"),
        "decorations":    r.get("decorations"),
        "evalTotal":      r.get("eval_total"),
        "execMission":    r.get("exec_mission"),
        "leadPeople":     r.get("lead_people"),
        "manageRes":      r.get("manage_res"),
        "improveUnit":    r.get("improve_unit"),
        "epbTotal":       r.get("epb_total"),
        "submitStrat":    r.get("submit_strat"),
        "stratScore":     r.get("strat_score"),
        "noReason":       "",      # not persisted
        "completionTime": r.get("completion_time"),
    }


def _strat_member_key(m: dict) -> tuple:
    """Lowercased (name, rank) tuple used for "new member" comparison."""
    return ((m.get("name") or "").strip().lower(),
            (m.get("rank") or "").strip().lower())


def _render_table_export(df, filename_prefix, key_suffix):
    """Render a small CSV download icon (top-right) above a table.
    Filename includes a timestamp so multiple exports don't collide.
    The icon is rendered without a wrapping st.columns row so it does
    NOT add visible whitespace between the section header and the table
    below. CSS pulls it tight to the right edge."""
    from datetime import datetime as _dt
    if df is None or df.empty:
        return
    ts = _dt.now().strftime("%Y%m%d_%H%M%S")
    safe_prefix = filename_prefix.replace(" ", "_")
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    btn_key = f"export_csv_{key_suffix}"
    # Aggressively collapse all the Streamlit wrapper padding around the
    # download button so it doesn't push content apart. Right-align via
    # `justify-content: flex-end` on the keyed wrapper itself.
    st.markdown(
        f"""
        <style>
        /* Collapse the stElementContainer / stVerticalBlock wrappers so
           the icon sits flush under the section header instead of below
           an empty Streamlit padded row. */
        div[data-testid="stElementContainer"]:has(.st-key-{btn_key}) {{
            margin: 0 !important;
            padding: 0 !important;
            min-height: 0 !important;
        }}
        .st-key-{btn_key} {{
            display: flex !important;
            justify-content: flex-end !important;
            margin: 0 !important;
            padding: 0 !important;
            min-height: 0 !important;
            line-height: 0;
            margin-top: -8px !important;
            margin-bottom: 0 !important;
        }}
        .st-key-{btn_key} button {{
            min-width: 32px !important; max-width: 36px !important;
            width: 36px !important;
            min-height: 26px !important; height: 26px !important;
            padding: 1px 4px !important;
            margin: 0 !important;
            font-size: 13px !important;
            line-height: 1 !important;
            border-radius: 4px !important;
        }}
        .st-key-{btn_key} button p {{
            font-size: 13px !important;
            margin: 0 !important;
            line-height: 1 !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.download_button(
        label="⬇",
        data=csv_bytes,
        file_name=f"{safe_prefix}_{ts}.csv",
        mime="text/csv",
        key=btn_key,
        help="Download table as CSV",
    )


def _fd_render_roster_table(rows, tid, base_height=520, new_member_keys=None):
    """Render an Excel-style sortable / multi-select-filterable roster table
    inside a sandboxed iframe. Identical interaction model to the Squadron
    Overview Member Information table; styled with a darker theme to fit
    the rest of the Force Development page.

    `new_member_keys` is an optional set of (lower(name), lower(rank)) tuples
    representing members who appeared in the latest upload but NOT in the
    immediately-prior version. Those rows render with a small gold "NEW"
    pill next to the Name cell.
    """
    import html as _html
    import uuid as _uuid
    new_member_keys = new_member_keys or set()

    # Sort: by last name (alphabetical), then first name as tiebreaker.
    def _sort_key(r):
        full = str(r.get("name", "") or "").strip()
        parts = full.split()
        last  = parts[-1].lower() if parts else ""
        first = parts[0].lower()  if parts else ""
        return (last, first)
    sorted_rows = sorted(rows, key=_sort_key)

    cols = [
        ("name",           "Name"),
        ("rank",           "Rank"),
        ("afsc",           "AFSC"),
        ("unit",           "Unit"),
        # Strat upload doesn't carry Flight, so it's not shown here.
        ("experience",     "Exp"),
        ("education",      "Edu"),
        ("awards",         "Awards"),
        ("decorations",    "Decs"),
        ("evalTotal",      "Eval Total"),
        ("execMission",    "Exec Mission"),
        ("leadPeople",     "Lead People"),
        ("manageRes",      "Res Mgmt"),
        ("improveUnit",    "Improve Unit"),
        ("epbTotal",       "EPB Total"),
        ("submitStrat",    "Submitted"),
        ("stratScore",     "Strat Score"),
        ("completionTime", "Completion Time"),
    ]

    # Columns that always render as whole-number integers (no decimals).
    # The strat-rubric upload sometimes returns floats (e.g. 28.0) and
    # category sub-scores can be non-integer floats; the user wants every
    # score column to display as a clean integer.
    _INT_SCORE_KEYS = {
        "stratScore", "evalTotal", "epbTotal",
        "execMission", "leadPeople", "manageRes", "improveUnit",
        "experience", "education", "awards", "decorations",
    }

    def _disp(r, k):
        v = r.get(k)
        if k == "submitStrat":
            return "YES" if v == "YES" else "NO"
        if v is None:
            return "-"
        if k in _INT_SCORE_KEYS:
            try:
                return str(int(round(float(v))))
            except (TypeError, ValueError):
                return str(v)
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v)

    header_cells = ""
    for idx, (key, label) in enumerate(cols):
        header_cells += (
            f'<th data-col-idx="{idx}" data-col-key="{key}">'
            f'<div class="wg-th-inner">'
            f'<div class="wg-th-label" data-col-idx="{idx}">'
            f'<span class="wg-th-name">{_html.escape(label)}</span>'
            f'<span class="wg-th-sort">⇅</span>'
            f'</div>'
            f'<button type="button" class="wg-th-filter" data-col-idx="{idx}" '
            f'aria-haspopup="listbox" aria-expanded="false">'
            f'<span class="wg-th-filter-label">(all)</span>'
            f'<span class="wg-th-filter-caret">▾</span>'
            f'</button>'
            f'</div></th>'
        )

    data_rows = ""
    for row_i, r in enumerate(sorted_rows):
        cells = ""
        # Determine if this row represents a "new" member (member appears
        # in current upload but not in the prior version).
        _is_new = _strat_member_key(r) in new_member_keys
        for col_i, (key, _label) in enumerate(cols):
            val = _disp(r, key)
            cell_classes = "fd-cell"
            if key == "name":
                cell_classes += " fd-name"
            elif key == "rank":
                cell_classes += " fd-rank"
            elif key == "submitStrat":
                cell_classes += " fd-yes" if val == "YES" else " fd-no"
            elif key == "stratScore":
                if r.get("stratScore") is not None:
                    s = r["stratScore"]
                    if   s >= 25: cell_classes += " fd-strat-hi"
                    elif s >= 18: cell_classes += " fd-strat-md"
                    else:         cell_classes += " fd-strat-lo"
                else:
                    cell_classes += " fd-strat-none"
            elif key in ("unit", "afsc", "completionTime"):
                cell_classes += " fd-text"
            else:
                cell_classes += " fd-num"
            # For the Name column, append a small "NEW" pill if this row is
            # flagged as a new member.
            if key == "name" and _is_new:
                _new_pill = ' <span class="fd-new-pill">NEW</span>'
                cells += (
                    f'<td class="{cell_classes}" data-col-idx="{col_i}" '
                    f'data-val="{_html.escape(val)}">{_html.escape(val)}{_new_pill}</td>'
                )
            else:
                cells += (
                    f'<td class="{cell_classes}" data-col-idx="{col_i}" '
                    f'data-val="{_html.escape(val)}">{_html.escape(val)}</td>'
                )
        data_rows += f"<tr>{cells}</tr>"

    tbl_id = "fd_tbl_" + _uuid.uuid4().hex[:8]
    nrows = max(1, len(sorted_rows))
    iframe_height = min(640, 110 + nrows * 30)

    table_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  html, body {{
    margin: 0; padding: 0; background: transparent;
    font-family: 'Barlow', sans-serif; color: #dde6f5;
  }}
  .wg-tbl-toolbar {{
    display: flex; gap: 12px; align-items: center;
    padding: 4px 0 8px 0;
  }}
  .wg-tbl-clear {{
    padding: 6px 14px; background: #2a4090; color: #dde6f5;
    border: 1px solid rgba(240,192,48,0.3); border-radius: 4px;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 11px; font-weight: 700;
    letter-spacing: 1px; text-transform: uppercase;
    cursor: pointer; transition: all 0.15s ease;
  }}
  .wg-tbl-clear:hover {{
    background: #f0c030; color: #0e1a3d; border-color: #f0c030;
    transform: scale(1.03); box-shadow: 0 4px 16px rgba(240,192,48,0.4);
  }}
  .wg-tbl-count {{ font-size: 0.85rem; color: #9dc4db; }}
  .wg-tbl-scroll {{
    overflow: auto;
    max-height: {iframe_height - 55}px;
    border: 1px solid rgba(240,192,48,0.2);
    border-radius: 4px;
    background: #162050;
  }}
  table.wg-tbl {{
    border-collapse: collapse;
    font-size: 0.82rem;
    width: 100%;
  }}
  table.wg-tbl thead th {{
    position: sticky; top: 0; z-index: 2;
    background: #1f3272;
    padding: 0;
    border: 1px solid rgba(240,192,48,0.2);
    white-space: nowrap;
    font-weight: 700;
    color: #f0c030;
  }}
  .wg-th-inner {{
    display: flex; flex-direction: column; gap: 4px;
    padding: 6px 8px;
  }}
  .wg-th-label {{
    display: flex; align-items: center; justify-content: space-between;
    cursor: pointer; user-select: none; gap: 6px;
  }}
  .wg-th-name {{ white-space: nowrap; }}
  .wg-th-sort {{ font-size: 0.72rem; opacity: 0.55; color: #dde6f5; }}
  .wg-th-label.wg-sort-asc .wg-th-sort,
  .wg-th-label.wg-sort-desc .wg-th-sort {{ opacity: 1; }}
  .wg-th-filter {{
    font-size: 0.72rem;
    padding: 3px 6px;
    border: 1px solid rgba(240,192,48,0.3);
    border-radius: 3px;
    background-color: #0e1a3d;
    color: #dde6f5;
    width: 100%;
    box-sizing: border-box;
    font-family: 'Barlow', sans-serif;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 4px;
    text-align: left;
    line-height: 1.3;
  }}
  .wg-th-filter:hover {{
    background-color: #1a2a5e;
    border-color: rgba(240,192,48,0.6);
  }}
  .wg-th-filter.wg-active {{
    background-color: #c9960a;
    color: #0e1a3d;
    border-color: #f0c030;
  }}
  .wg-th-filter-label {{
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1;
  }}
  .wg-th-filter-caret {{
    font-size: 0.65rem; color: inherit; flex-shrink: 0;
  }}
  table.wg-tbl tbody td {{
    padding: 5px 10px;
    border: 1px solid rgba(240,192,48,0.15);
    white-space: nowrap;
    color: #dde6f5;
    background: transparent;
  }}
  table.wg-tbl tbody tr:nth-child(even):not(.wg-row-hidden) td {{
    background: rgba(255,255,255,0.02);
  }}
  table.wg-tbl tbody tr.wg-row-hidden {{ display: none; }}
  td.fd-name {{ color: #f8d96a; font-weight: 600; }}
  td.fd-rank {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; color: #f0c030; }}
  td.fd-num  {{ text-align: right; font-variant-numeric: tabular-nums; }}
  td.fd-text {{ color: #9dc4db; }}
  td.fd-yes  {{ color: #22c55e; font-weight: 700; text-align: center; }}
  td.fd-no   {{ color: #c0283e; font-weight: 700; text-align: center; }}
  td.fd-strat-hi  {{ color: #22c55e; font-weight: 700; text-align: right; }}
  td.fd-strat-md  {{ color: #f0c030; font-weight: 700; text-align: right; }}
  td.fd-strat-lo  {{ color: #c0283e; font-weight: 700; text-align: right; }}
  td.fd-strat-none {{ color: #7a93c0; text-align: right; }}
  /* Gold "NEW" pill for members appearing for the first time in this version. */
  .fd-new-pill {{
    display: inline-block;
    margin-left: 6px;
    padding: 1px 6px;
    background: #f0c030;
    color: #1a2a5e;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    border-radius: 3px;
    vertical-align: middle;
  }}

  /* Filter popover (same model as Squadron Overview) */
  .wg-popover {{
    position: absolute; z-index: 1000;
    background: #0e1a3d; color: #dde6f5;
    border: 1px solid rgba(240,192,48,0.3);
    border-radius: 4px;
    box-shadow: 0 6px 24px rgba(0,0,0,0.5);
    padding: 6px;
    min-width: 200px;
    max-width: 300px;
    font-family: 'Barlow', sans-serif;
    display: none;
  }}
  .wg-popover.wg-open {{ display: block; }}
  .wg-popover-search {{
    width: 100%; box-sizing: border-box;
    padding: 4px 6px; margin-bottom: 4px;
    border: 1px solid rgba(240,192,48,0.3);
    border-radius: 3px;
    font-size: 0.78rem;
    background: #162050; color: #dde6f5;
  }}
  .wg-popover-actions {{ display: flex; gap: 4px; margin-bottom: 4px; }}
  .wg-popover-actions button {{
    flex: 1; padding: 3px 4px;
    border: 1px solid rgba(240,192,48,0.3);
    border-radius: 3px;
    background: #1f3272; color: #dde6f5;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 10px; font-weight: 700;
    letter-spacing: 0.5px; text-transform: uppercase;
    cursor: pointer;
  }}
  .wg-popover-actions button:hover {{
    background: #2a4090; border-color: #f0c030;
  }}
  .wg-popover-list {{
    max-height: 220px; overflow-y: auto;
    border: 1px solid rgba(240,192,48,0.2);
    border-radius: 3px; padding: 2px 0;
    background: #162050;
  }}
  .wg-popover-list label {{
    display: flex; align-items: center; gap: 6px;
    padding: 3px 6px; font-size: 0.78rem;
    cursor: pointer; user-select: none;
  }}
  .wg-popover-list label:hover {{ background: #1f3272; }}
  .wg-popover-list label.wg-hidden {{ display: none; }}
  .wg-popover-list input[type="checkbox"] {{ margin: 0; cursor: pointer; }}
  .wg-popover-list .wg-empty {{
    padding: 8px; text-align: center; color: #7a93c0;
    font-size: 0.78rem; font-style: italic;
  }}
  .wg-popover-footer {{ display: flex; gap: 4px; margin-top: 6px; }}
  .wg-popover-footer button {{
    flex: 1; padding: 4px 6px;
    border: 1px solid; border-radius: 3px;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 10px; font-weight: 700;
    letter-spacing: 0.5px; text-transform: uppercase;
    cursor: pointer;
  }}
  .wg-popover-apply {{ background: #f0c030; color: #0e1a3d; border-color: #f0c030; }}
  .wg-popover-apply:hover {{ background: #f8d96a; border-color: #f8d96a; }}
  .wg-popover-cancel {{ background: transparent; color: #dde6f5; border-color: rgba(240,192,48,0.3); }}
  .wg-popover-cancel:hover {{ background: #1a2a5e; }}
</style></head><body>
<div class="wg-tbl-toolbar">
  <button type="button" class="wg-tbl-clear">Clear filters</button>
  <span class="wg-tbl-count"></span>
</div>
<div class="wg-tbl-scroll">
  <table class="wg-tbl" id="{tbl_id}">
    <thead><tr>{header_cells}</tr></thead>
    <tbody>{data_rows}</tbody>
  </table>
</div>
<div class="wg-popover" id="wg-popover" role="dialog" aria-modal="false">
  <input type="text" class="wg-popover-search" placeholder="Search values..." />
  <div class="wg-popover-actions">
    <button type="button" class="wg-popover-selectall">Select all</button>
    <button type="button" class="wg-popover-clear">Clear</button>
  </div>
  <div class="wg-popover-list"></div>
  <div class="wg-popover-footer">
    <button type="button" class="wg-popover-cancel">Cancel</button>
    <button type="button" class="wg-popover-apply">Apply</button>
  </div>
</div>
<script>
(function() {{
  var table = document.getElementById("{tbl_id}");
  if (!table) return;
  var tbody   = table.querySelector("tbody");
  var rows    = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
  var clear   = document.querySelector(".wg-tbl-clear");
  var counter = document.querySelector(".wg-tbl-count");
  var filterBtns = document.querySelectorAll(".wg-th-filter");
  var labels  = document.querySelectorAll(".wg-th-label");
  var popover = document.getElementById("wg-popover");
  var popSearch = popover.querySelector(".wg-popover-search");
  var popList   = popover.querySelector(".wg-popover-list");
  var popSelectAll = popover.querySelector(".wg-popover-selectall");
  var popClear     = popover.querySelector(".wg-popover-clear");
  var popApply     = popover.querySelector(".wg-popover-apply");
  var popCancel    = popover.querySelector(".wg-popover-cancel");

  var selectedByCol = {{}};
  var popContext = null;
  var pendingSelection = null;
  var sortState = {{ col: null, dir: 0 }};

  labels.forEach(function(lbl) {{
    lbl.addEventListener("click", function(e) {{
      if (e.target.closest(".wg-th-filter")) return;
      var ci = parseInt(lbl.getAttribute("data-col-idx"), 10);
      if (sortState.col === ci) {{
        sortState.dir = sortState.dir === 1 ? -1 : (sortState.dir === -1 ? 0 : 1);
      }} else {{
        sortState.col = ci; sortState.dir = 1;
      }}
      labels.forEach(function(l) {{
        l.classList.remove("wg-sort-asc", "wg-sort-desc");
        var s = l.querySelector(".wg-th-sort");
        if (s) s.textContent = "\u21C5";
      }});
      if (sortState.dir !== 0) {{
        lbl.classList.add(sortState.dir === 1 ? "wg-sort-asc" : "wg-sort-desc");
        var s = lbl.querySelector(".wg-th-sort");
        if (s) s.textContent = sortState.dir === 1 ? "\u25B2" : "\u25BC";
      }} else {{
        sortState.col = null;
      }}
      applySort();
    }});
  }});

  filterBtns.forEach(function(btn) {{
    btn.addEventListener("click", function(e) {{
      e.stopPropagation();
      openPopover(parseInt(btn.getAttribute("data-col-idx"), 10), btn);
    }});
  }});
  document.addEventListener("click", function(e) {{
    if (popContext && !popover.contains(e.target) &&
        !e.target.classList.contains("wg-th-filter")) {{
      closePopover(false);
    }}
  }});
  document.addEventListener("keydown", function(e) {{
    if (e.key === "Escape" && popContext) closePopover(false);
  }});
  document.querySelector(".wg-tbl-scroll").addEventListener("scroll", function() {{
    if (popContext) closePopover(false);
  }});

  popSearch.addEventListener("input", function() {{
    var q = (popSearch.value || "").trim().toLowerCase();
    popList.querySelectorAll("label").forEach(function(lbl) {{
      var v = (lbl.getAttribute("data-val") || "").toLowerCase();
      if (q && v.indexOf(q) === -1) lbl.classList.add("wg-hidden");
      else lbl.classList.remove("wg-hidden");
    }});
  }});
  popSelectAll.addEventListener("click", function() {{
    popList.querySelectorAll("label:not(.wg-hidden) input[type=checkbox]")
      .forEach(function(cb) {{
        cb.checked = true; pendingSelection.add(cb.value);
      }});
  }});
  popClear.addEventListener("click", function() {{
    popList.querySelectorAll("label:not(.wg-hidden) input[type=checkbox]")
      .forEach(function(cb) {{
        cb.checked = false; pendingSelection.delete(cb.value);
      }});
  }});
  popCancel.addEventListener("click", function() {{ closePopover(false); }});
  popApply.addEventListener("click", function() {{ closePopover(true); }});

  function openPopover(ci, anchorBtn) {{
    popContext = {{ ci: ci, anchor: anchorBtn }};
    var availableVals = computeAvailableValues(ci);
    var current = selectedByCol[ci];
    pendingSelection = new Set(current ? Array.from(current) : availableVals);
    popList.innerHTML = "";
    if (availableVals.length === 0) {{
      var empty = document.createElement("div");
      empty.className = "wg-empty";
      empty.textContent = "No values to filter";
      popList.appendChild(empty);
    }} else {{
      availableVals.forEach(function(v) {{
        var lbl = document.createElement("label");
        lbl.setAttribute("data-val", v);
        var cb = document.createElement("input");
        cb.type = "checkbox"; cb.value = v;
        cb.checked = pendingSelection.has(v);
        cb.addEventListener("change", function() {{
          if (cb.checked) pendingSelection.add(v);
          else            pendingSelection.delete(v);
        }});
        var text = document.createElement("span");
        text.textContent = v;
        lbl.appendChild(cb); lbl.appendChild(text);
        popList.appendChild(lbl);
      }});
    }}
    popSearch.value = "";
    popList.querySelectorAll("label").forEach(function(l) {{ l.classList.remove("wg-hidden"); }});
    var rect = anchorBtn.getBoundingClientRect();
    popover.classList.add("wg-open");
    var pw = popover.offsetWidth, ph = popover.offsetHeight;
    var top  = rect.bottom + window.scrollY + 2;
    var left = rect.left   + window.scrollX;
    var vw = document.documentElement.clientWidth;
    if (left + pw > vw - 8) left = Math.max(8, vw - pw - 8);
    var vh = window.innerHeight;
    if (rect.bottom + ph > vh - 8 && rect.top - ph > 8) {{
      top = rect.top + window.scrollY - ph - 2;
    }}
    popover.style.left = left + "px";
    popover.style.top  = top + "px";
    anchorBtn.setAttribute("aria-expanded", "true");
    setTimeout(function() {{ popSearch.focus(); }}, 0);
  }}

  function closePopover(commit) {{
    if (!popContext) return;
    if (commit) {{
      var ci = popContext.ci;
      var availableVals = computeAvailableValues(ci);
      if (pendingSelection.size === 0 || pendingSelection.size === availableVals.length) {{
        selectedByCol[ci] = null;
      }} else {{
        selectedByCol[ci] = new Set(pendingSelection);
      }}
      updateFilterButtonLabel(ci);
      applyFilters();
    }}
    popover.classList.remove("wg-open");
    if (popContext.anchor) popContext.anchor.setAttribute("aria-expanded", "false");
    popContext = null;
    pendingSelection = null;
  }}

  function computeAvailableValues(ci) {{
    var seen = {{}}, values = [];
    rows.forEach(function(tr) {{
      for (var key in selectedByCol) {{
        var k = parseInt(key, 10);
        if (k === ci) continue;
        var sel = selectedByCol[k];
        if (!sel) continue;
        var td = tr.children[k];
        var v = (td && td.getAttribute("data-val")) || "";
        if (!sel.has(v)) return;
      }}
      var td = tr.children[ci];
      if (!td) return;
      var v = td.getAttribute("data-val") || "";
      if (v === "" || seen[v]) return;
      seen[v] = true; values.push(v);
    }});
    values.sort(function(a, b) {{
      return a.localeCompare(b, undefined, {{numeric:true, sensitivity:"base"}});
    }});
    return values;
  }}

  function updateFilterButtonLabel(ci) {{
    var btn = document.querySelector('.wg-th-filter[data-col-idx="' + ci + '"]');
    if (!btn) return;
    var labelEl = btn.querySelector(".wg-th-filter-label");
    var sel = selectedByCol[ci];
    if (!sel) {{
      labelEl.textContent = "(all)";
      btn.classList.remove("wg-active");
    }} else {{
      var arr = Array.from(sel);
      if (arr.length === 1) labelEl.textContent = arr[0];
      else if (arr.length <= 3) labelEl.textContent = arr.join(", ");
      else labelEl.textContent = arr.length + " selected";
      btn.classList.add("wg-active");
    }}
  }}

  clear.addEventListener("click", function() {{
    selectedByCol = {{}};
    filterBtns.forEach(function(btn) {{
      var labelEl = btn.querySelector(".wg-th-filter-label");
      labelEl.textContent = "(all)";
      btn.classList.remove("wg-active");
    }});
    applyFilters();
  }});

  function applyFilters() {{
    var visible = 0;
    rows.forEach(function(tr) {{
      var show = true;
      for (var key in selectedByCol) {{
        var sel = selectedByCol[key];
        if (!sel) continue;
        var ci = parseInt(key, 10);
        var td = tr.children[ci];
        var v = (td && td.getAttribute("data-val")) || "";
        if (!sel.has(v)) {{ show = false; break; }}
      }}
      if (show) {{ tr.classList.remove("wg-row-hidden"); visible++; }}
      else      {{ tr.classList.add("wg-row-hidden"); }}
    }});
    counter.textContent = "Showing " + visible + " of " + rows.length;
  }}

  function applySort() {{
    if (sortState.col === null || sortState.dir === 0) {{
      rows.forEach(function(tr) {{ tbody.appendChild(tr); }});
      return;
    }}
    var ci = sortState.col, dir = sortState.dir;
    rows.slice().sort(function(a, b) {{
      var av = (a.children[ci] && a.children[ci].getAttribute("data-val")) || "";
      var bv = (b.children[ci] && b.children[ci].getAttribute("data-val")) || "";
      // Numeric-aware comparison
      var an = parseFloat(av), bn = parseFloat(bv);
      var cmp = (!isNaN(an) && !isNaN(bn))
        ? an - bn
        : av.localeCompare(bv, undefined, {{numeric:true, sensitivity:"base"}});
      return cmp * dir;
    }}).forEach(function(tr) {{ tbody.appendChild(tr); }});
  }}

  applyFilters();
}})();
</script></body></html>
"""
    # Build a clean DataFrame for CSV/XLSX export using the same display
    # logic the on-screen table uses, so the export matches what the user sees.
    _export_records = []
    for _r in sorted_rows:
        _rec = {}
        for _key, _label in cols:
            _rec[_label] = _disp(_r, _key)
        _export_records.append(_rec)
    _export_df = pd.DataFrame(_export_records)
    _render_table_export(_export_df, f"strat_roster_{tid}", f"strat_{tid}")

    _components.html(table_html, height=iframe_height, scrolling=False)


def _render_snco_stratification_tab():
    """SNCO Stratification tab — Microsoft Forms .xlsx upload, summary cards,
    organization charts, rosters, score distributions, strat-score charts.

    Data sourcing:
      * Super-admin uploads of the global file are persisted to the database
        (last 3 retained). Other users see the latest global upload by default
        and can pick from the last 3 versions via the dropdown.
      * Tenant admins / Commanders / SELs can upload a LOCAL file for preview;
        local uploads are session-only and do NOT override the global dataset.
      * Non-super-admin viewers see only their tenant's slice of the data.
    """
    role = st.session_state.get("role", "user")
    user_id = st.session_state.get("user_id")
    user_title = st.session_state.get("title", "")
    is_super = (role == "super_admin")
    can_upload_global = is_super
    _fd_titles = {"Commander", "SEL", "Senior Enlisted Leader"}
    can_upload_local = is_super or (user_title in _fd_titles) or role in ("admin",)

    # ── Page-scoped spacing tweaks ───────────────────────────────────────────
    # Drop a marker div at the top of this tab and use it as a CSS scope so
    # the spacing reductions below ONLY affect the SNCO Stratification tab and
    # don't bleed into other pages (Squadron Overview, Promotion Scorecard,
    # etc.) which have their own carefully-tuned spacing.
    #
    # The marker is an empty zero-height element; we then use general-sibling
    # selectors (`~`) so any element rendered after it within the same tab
    # panel inherits the tighter spacing. Streamlit puts every render call in
    # its own stElementContainer sibling, so this works across the whole tab.
    st.markdown(
        """
        <div class="snco-strat-scope" style="display:none;height:0;"></div>
        <style>
        /* Section headers (sec_header) sit tighter to the content below.
           This shrinks the gap between every "Title" / "Roster" / "Score
           Distributions" / "Stratification Overall Scores" header and the
           thing immediately under it (download icon, chart, or iframe). */
        div[data-testid="stElementContainer"]:has(.snco-strat-scope)
            ~ div[data-testid="stElementContainer"]:has(.wg-sec-hdr) .wg-sec-hdr {
            margin-top: 4px !important;
            margin-bottom: 4px !important;
        }
        /* Iframe (the roster table) should also sit tight under the icon. */
        div[data-testid="stElementContainer"]:has(.snco-strat-scope)
            ~ div[data-testid="stElementContainer"]:has(iframe) {
            margin-top: 0 !important;
        }
        /* Plotly chart top-margin: shave the global 18px down to 6px on this
           tab so charts hug the section header / category subtitle above. */
        div[data-testid="stElementContainer"]:has(.snco-strat-scope)
            ~ div[data-testid="stElementContainer"] div[data-testid="stPlotlyChart"],
        div[data-testid="stElementContainer"]:has(.snco-strat-scope)
            ~ div[data-testid="stElementContainer"] .stPlotlyChart {
            margin-top: 6px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Initialize session state ─────────────────────────────────────────────
    # fd_members: the currently-DISPLAYED dataset (could be from DB, from a
    #   local-preview upload, or empty)
    # fd_source:  "db" / "local" / "" — tells the UI where the data came from
    # fd_version_id: the strat_uploads.id currently displayed (None for local)
    # fd_prior_records_keys: set of (lower(name), lower(rank)) tuples from
    #   the immediately-prior version, used to flag "new" members
    if "fd_members" not in st.session_state:
        st.session_state.fd_members = []
        st.session_state.fd_loaded_name = ""
        st.session_state.fd_debug = {}
        st.session_state.fd_source = ""
        st.session_state.fd_version_id = None
        st.session_state.fd_prior_records_keys = set()
    # Tracks the (name, size) of the last upload we already processed.
    # The st.file_uploader widget keeps its file across reruns, so without
    # this guard the post-save st.rerun() would loop back into the upload
    # branch and re-save the same file repeatedly (causing the page to
    # appear to reload itself several times after a successful upload).
    if "fd_last_processed_upload" not in st.session_state:
        st.session_state.fd_last_processed_upload = None

    # ── Load latest global version from DB on first render ───────────────────
    if not st.session_state.fd_members and not st.session_state.fd_loaded_name:
        try:
            latest = get_latest_strat_upload()
        except Exception as e:
            latest = None
            st.warning(f"Could not load saved stratification data: {e}")
        if latest:
            try:
                rows = get_strat_records(latest["id"])
                st.session_state.fd_members = [_strat_db_row_to_record(r) for r in rows]
                st.session_state.fd_loaded_name = latest.get("file_name") or "(unnamed upload)"
                st.session_state.fd_source = "db"
                st.session_state.fd_version_id = latest["id"]
                # Pull the prior version (if any) to compute "new member" flags
                _all = list_strat_uploads(limit=3)
                if len(_all) >= 2:
                    _prior = get_strat_records(_all[1]["id"])
                    st.session_state.fd_prior_records_keys = {
                        _strat_member_key(_strat_db_row_to_record(r)) for r in _prior
                    }
                else:
                    st.session_state.fd_prior_records_keys = set()
            except Exception as e:
                st.warning(f"Could not load latest stratification version: {e}")

    # ── Top bar: load the version metadata used by the dropdown below ────────
    versions = []
    try:
        versions = list_strat_uploads(limit=3)
    except Exception:
        pass

    # ── Top bar: upload control on the left, status + version dropdown
    # stacked on the right ────────────────────────────────────────────────────
    upload_col, right_col = st.columns([3, 2])

    with upload_col:
        if can_upload_global:
            _upload_label = "Upload GLOBAL stratification rubric (super-admin)"
            _upload_help  = "Saved as the new global version. Older versions are kept (last 3)."
        elif can_upload_local:
            _upload_label = "Upload LOCAL preview (your unit only — not saved)"
            _upload_help  = "Local uploads are session-only and do NOT override the global dataset."
        else:
            _upload_label = None

        if _upload_label:
            uploaded = st.file_uploader(
                _upload_label,
                type=["xlsx", "xls"],
                key="fd_uploader",
                help=_upload_help,
            )
            # The file_uploader retains its file across reruns. After we
            # successfully save an upload and call st.rerun(), this branch
            # would otherwise re-execute and re-save the same file, causing
            # the page to reload itself multiple times. Fingerprint the
            # current upload (name + size) and skip it if we've already
            # processed it on a prior run.
            _upload_fp = (
                (uploaded.name, uploaded.size)
                if uploaded is not None else None
            )
            if (uploaded is not None
                    and _upload_fp != st.session_state.fd_last_processed_upload):
                members, err, debug = _fd_parse_excel(uploaded.getvalue())
                if err:
                    st.session_state.fd_last_processed_upload = _upload_fp
                    st.error(err)
                else:
                    if can_upload_global:
                        # Persist to DB. Capture prior-version keys BEFORE the
                        # new upload becomes "version 1" so we can flag new
                        # members against the (now displaced) prior-latest.
                        _prior_keys = set()
                        try:
                            _existing = list_strat_uploads(limit=3)
                            if _existing:
                                _prior = get_strat_records(_existing[0]["id"])
                                _prior_keys = {
                                    _strat_member_key(_strat_db_row_to_record(r)) for r in _prior
                                }
                        except Exception:
                            pass
                        try:
                            db_rows = [_strat_record_to_db_row(m) for m in members]
                            new_id = create_strat_upload(uploaded.name, user_id, db_rows)
                            st.session_state.fd_members = members
                            st.session_state.fd_loaded_name = uploaded.name
                            st.session_state.fd_debug = debug
                            st.session_state.fd_source = "db"
                            st.session_state.fd_version_id = new_id
                            st.session_state.fd_prior_records_keys = _prior_keys
                            # Mark this exact file as already processed so the
                            # post-rerun render does not re-trigger this branch
                            # (the uploader keeps its file across reruns).
                            st.session_state.fd_last_processed_upload = _upload_fp
                            st.success(
                                f"Saved as new global version "
                                f"({len(members)} records). Older versions auto-pruned to 3."
                            )
                            st.rerun()
                        except Exception as e:
                            # Even on error, fingerprint this attempt so we
                            # don't hammer the DB with the same failing file
                            # on every rerun. The user can re-upload to retry.
                            st.session_state.fd_last_processed_upload = _upload_fp
                            st.error(f"Could not save upload to database: {e}")
                    else:
                        # Local-only preview — does NOT persist.
                        st.session_state.fd_members = members
                        st.session_state.fd_loaded_name = uploaded.name
                        st.session_state.fd_debug = debug
                        st.session_state.fd_source = "local"
                        st.session_state.fd_version_id = None
                        st.session_state.fd_prior_records_keys = set()
                        st.session_state.fd_last_processed_upload = _upload_fp
                        st.info(
                            "Loaded as LOCAL preview only — this upload is "
                            "session-only and will not override the global dataset."
                        )
        else:
            st.markdown(
                '<div style="font-family:Barlow Condensed,sans-serif;font-size:11px;'
                'letter-spacing:1px;text-transform:uppercase;color:#7a93c0;'
                'padding:30px 0 0 0;">View only — uploads require leadership role</div>',
                unsafe_allow_html=True,
            )

    with right_col:
        # Top of the right column: GLOBAL · <filename> — N records status line.
        _src = st.session_state.get("fd_source", "")
        if st.session_state.fd_loaded_name:
            _dup = (st.session_state.get("fd_debug") or {}).get("duplicates_dropped", 0)
            _dup_html = (
                f' <span style="color:#c9960a;">— {_dup} duplicate'
                f'{"" if _dup == 1 else "s"} merged (kept latest)</span>'
                if _dup else ""
            )
            _src_tag = (
                '<span style="color:#22c55e;">GLOBAL</span>' if _src == "db"
                else '<span style="color:#c9960a;">LOCAL PREVIEW</span>' if _src == "local"
                else '<span style="color:#7a93c0;">—</span>'
            )
            st.markdown(
                f'<div style="font-family:Barlow Condensed,sans-serif;font-size:11px;'
                f'letter-spacing:1px;text-transform:uppercase;color:#22c55e;'
                f'padding:6px 0 6px 0;">{_src_tag} · '
                f'<span style="color:#1a2a5e;font-weight:700;">{st.session_state.fd_loaded_name}</span> '
                f'<span style="color:#7a93c0;">— {len(st.session_state.fd_members)} records</span>'
                f'{_dup_html}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div style="font-family:Barlow Condensed,sans-serif;font-size:11px;'
                'letter-spacing:1px;text-transform:uppercase;color:#7a93c0;'
                'padding:6px 0 6px 0;">No data loaded</div>',
                unsafe_allow_html=True,
            )

        # Underneath the status line: the version dropdown.
        if versions:
            def _ver_label(v):
                ts = v.get("uploaded_at", "")
                # Trim to YYYY-MM-DD HH:MM if ISO format
                ts_disp = ts[:16].replace("T", " ") if ts else "?"
                return f"{ts_disp} — {v.get('file_name') or 'unnamed'}"
            ver_options = {v["id"]: _ver_label(v) for v in versions}
            current_id = st.session_state.fd_version_id or versions[0]["id"]
            sel = st.selectbox(
                "Stratification version (last 3 global uploads)",
                options=list(ver_options.keys()),
                index=list(ver_options.keys()).index(current_id) if current_id in ver_options else 0,
                format_func=lambda i: ver_options.get(i, str(i)),
                key="fd_version_select",
            )
            if sel != st.session_state.fd_version_id:
                # User picked a different version — reload its records.
                try:
                    rows = get_strat_records(sel)
                    st.session_state.fd_members = [_strat_db_row_to_record(r) for r in rows]
                    sel_meta = next((v for v in versions if v["id"] == sel), {})
                    st.session_state.fd_loaded_name = sel_meta.get("file_name") or "(unnamed upload)"
                    st.session_state.fd_source = "db"
                    st.session_state.fd_version_id = sel
                    # Prior-version keys: the next-older upload, if any
                    sel_idx = next((i for i, v in enumerate(versions) if v["id"] == sel), None)
                    if sel_idx is not None and sel_idx + 1 < len(versions):
                        _prior = get_strat_records(versions[sel_idx + 1]["id"])
                        st.session_state.fd_prior_records_keys = {
                            _strat_member_key(_strat_db_row_to_record(r)) for r in _prior
                        }
                    else:
                        st.session_state.fd_prior_records_keys = set()
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not load that version: {e}")
        else:
            st.markdown(
                '<div style="font-family:Barlow Condensed,sans-serif;font-size:11px;'
                'letter-spacing:1px;text-transform:uppercase;color:#7a93c0;'
                'padding:6px 0 0 0;">No saved versions yet</div>',
                unsafe_allow_html=True,
            )

    members = st.session_state.fd_members

    # Tenant scoping: super-admin sees all units; everyone else sees only
    # their own tenant's slice. The strat data uses "unit" (e.g. "149 IS")
    # which we match against the tenant name.
    if not is_super and members:
        try:
            _tenant_id = st.session_state.get("tenant_id")
            if _tenant_id:
                _tenants = get_all_tenants()
                _my = next((t for t in _tenants if t.get("id") == _tenant_id), None)
                if _my:
                    _my_name = (_my.get("name") or "").strip()
                    if _my_name:
                        members = [m for m in members
                                   if (m.get("unit") or "").strip() == _my_name]
        except Exception:
            pass

    if not members:
        # If a file was uploaded but parsed to 0 rows, surface diagnostic
        # info so the user can see why (column-name mismatch is the most
        # common cause when the form template has been changed).
        debug = st.session_state.get("fd_debug", {})
        if st.session_state.fd_loaded_name and debug:
            st.warning(
                f'Loaded "{st.session_state.fd_loaded_name}" but no submission '
                f'rows passed the Name / Rank / Unit check. Expand the diagnostic '
                f'panel below to see what came through.'
            )
            with st.expander("Diagnostic info — Excel parsing"):
                st.markdown(f"**Total rows read:** {debug.get('row_count', 0)}")
                st.markdown(f"**Detected columns ({len(debug.get('columns', []))}):**")
                st.code("\n".join(debug.get("columns", [])) or "(none)")
                rejected = debug.get("rejected", [])
                if rejected:
                    st.markdown(f"**First {len(rejected)} rejected row(s) — "
                                "Force Development requires Name + Rank + Unit:**")
                    for rr in rejected:
                        st.markdown(
                            f"- Row {rr['row']}: name={rr['name']!r} "
                            f"rank={rr['rank']!r} unit={rr['unit']!r}"
                        )
                st.markdown(
                    "**Required column headers** (case-sensitive): "
                    "`Name` (or `Name2`), `Rank`, `Unit`. "
                    "Rank values are normalized — both `MSgt` and `MSGT` work."
                )
        else:
            st.markdown(
                '<div style="margin:6px 0 18px 0;padding:0;color:#9dc4db;'
                'font-family:Barlow Condensed,sans-serif;font-size:13px;'
                'letter-spacing:1.5px;text-transform:uppercase;">'
                'Upload an Excel export above to populate the stratification dashboard.</div>',
                unsafe_allow_html=True,
            )
        return

    # ── Unit-only dropdown ────────────────────────────────────────────────────
    # Use 3-tuple shape (kind, unit, flight) so the banner code in app.py
    # which inspects this value can use the same logic as other pages.
    # `flight` is always None on this page since stratification is unit-level
    # only (no flight breakdown).
    units_in_data = {m["unit"] for m in members if m["unit"]}
    options = [("none", None, None), ("all", None, None)]
    for u in FD_ORGS:
        if u in units_in_data:
            options.append(("unit", u, None))
    # Append any non-canonical units present in the data so we don't hide them.
    for u in sorted(units_in_data):
        if u not in FD_ORGS:
            options.append(("unit", u, None))

    def _fmt_opt(opt):
        kind, unit, _flight = opt
        if kind == "none": return "No option selected"
        if kind == "all":  return "All Units"
        return unit

    selected = st.selectbox(
        "Select Unit",
        options=options,
        format_func=_fmt_opt,
        key="force_dev_unit",
    )

    kind, unit = selected[0], selected[1]
    if kind == "none":
        st.markdown(
            '<div style="margin:6px 0 18px 0;padding:0;color:#9dc4db;'
            'font-family:Barlow Condensed,sans-serif;font-size:13px;'
            'letter-spacing:1.5px;text-transform:uppercase;">'
            'Select a unit from the dropdown above to load its stratification dashboard.</div>',
            unsafe_allow_html=True,
        )
        return

    if kind == "all":
        scoped = list(members)
        org_label = "All Units"
    else:
        scoped = [m for m in members if m["unit"] == unit]
        org_label = unit

    if not scoped:
        st.warning(f"No submissions found for {org_label}.")
        return

    # ── Summary stat cards ────────────────────────────────────────────────────
    msgt   = [m for m in scoped if m["rank"] == "MSgt"]
    smsgt  = [m for m in scoped if m["rank"] == "SMSgt"]
    yes_r  = [m for m in scoped if m["submitStrat"] == "YES"]
    no_r   = [m for m in scoped if m["submitStrat"] != "YES"]
    msgt_y = [m for m in msgt   if m["submitStrat"] == "YES"]
    smsgt_y= [m for m in smsgt  if m["submitStrat"] == "YES"]
    has_strat = any(m["stratScore"] is not None for m in scoped)
    orgs_represented = len({m["unit"] for m in scoped if m["unit"]})

    sec_header(f"Summary — {org_label}", tag="OVERVIEW")
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        stat_card("Total Submissions", str(len(scoped)),
                  sub="across all ranks", color="gold")
    with s2:
        stat_card("Submitted for Stratification", str(len(yes_r)),
                  sub=f"{len(yes_r)} / {len(scoped)} total", color="green")
    with s3:
        stat_card("Not Submitted", str(len(no_r)),
                  sub=f"{len(no_r)} / {len(scoped)} total", color="red")
    with s4:
        stat_card("Units Represented", str(orgs_represented),
                  sub=f"of {len(FD_ORGS)} units", color="blue")

    # ── Submissions by Rank ───────────────────────────────────────────────────
    sec_header("Submissions by Rank", tag="RANK DETAIL")
    r1, r2 = st.columns(2)
    for col, label, rk_all, rk_sub in [
        (r1, "MSgt",  msgt,  msgt_y),
        (r2, "SMSgt", smsgt, smsgt_y),
    ]:
        t = len(rk_all); y = len(rk_sub); n = t - y
        pct = round(100 * y / t) if t else 0
        with col:
            st.markdown(
                f'<div style="background:#162050;border:1px solid rgba(240,192,48,0.2);'
                f'border-radius:8px;padding:18px 22px;position:relative;overflow:hidden;'
                f'margin-bottom:10px;">'
                f'<h3 style="font-family:Barlow Condensed,sans-serif;font-size:22px;'
                f'font-weight:800;letter-spacing:1px;color:#f0c030;margin-bottom:12px;'
                f'border-bottom:1px solid rgba(240,192,48,0.2);padding-bottom:10px;">'
                f'{label} <span style="color:#dde6f5;font-size:14px;font-weight:400;'
                f'margin-left:6px;">({t} total)</span></h3>'
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:7px 0;border-bottom:1px solid rgba(255,255,255,0.05);">'
                f'<span style="font-size:12px;color:#7a93c0;">Submitted for Stratification</span>'
                f'<span style="font-family:Barlow Condensed,sans-serif;font-size:20px;'
                f'font-weight:700;color:#22c55e;">{y}/{t}</span></div>'
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:7px 0;border-bottom:1px solid rgba(255,255,255,0.05);">'
                f'<span style="font-size:12px;color:#7a93c0;">Not Submitted</span>'
                f'<span style="font-family:Barlow Condensed,sans-serif;font-size:20px;'
                f'font-weight:700;color:#c0283e;">{n}/{t}</span></div>'
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:7px 0;">'
                f'<span style="font-size:12px;color:#7a93c0;">Submission Rate</span>'
                f'<span style="font-family:Barlow Condensed,sans-serif;font-size:20px;'
                f'font-weight:700;color:#f0c030;">{pct}%</span></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Submissions by Unit ───────────────────────────────────────────────────
    sec_header("Submissions by Unit", tag="UNIT OVERVIEW")
    tot_per_org = {o: 0 for o in FD_ORGS}
    sub_per_org = {o: 0 for o in FD_ORGS}
    for m in scoped:
        if m["unit"] in tot_per_org:
            tot_per_org[m["unit"]] += 1
            if m["submitStrat"] == "YES":
                sub_per_org[m["unit"]] += 1

    o1, o2 = st.columns(2)
    # Per-org bar colors. Drawn from the existing Office-palette colors used
    # by the tenure charts so the Force Development page reads as part of
    # the same theme. Order matches FD_ORGS so each org is visually
    # consistent across the two side-by-side charts.
    FD_ORG_COLORS = [
        "#1F2A8A",  # 195 WG HQ — deep navy
        "#F2C400",  # 195 ISRG — gold
        "#C91F2C",  # 195 OG — crimson
        "#6E93B6",  # 147 CBCS — steel blue
        "#4A66AC",  # 148 SOPS — medium blue
        "#5B9BD5",  # 149 IS — azure
        "#70AD47",  # 216 EWS — green
        "#ED7D31",  # 261 COS — orange
        "#9DC4DB",  # 234 IS — sky light
        "#A5A5A5",  # 222 ISS — neutral grey
    ]
    while len(FD_ORG_COLORS) < len(FD_ORGS):
        FD_ORG_COLORS.append("#5B9BD5")  # safety net for added orgs
    with o1:
        fig_tot = px.bar(
            x=FD_ORGS,
            y=[tot_per_org[o] for o in FD_ORGS],
            labels={"x": "Unit", "y": "Total Submissions"},
            title="Total Submissions per Unit",
        )
        fig_tot.update_traces(marker_color=FD_ORG_COLORS[:len(FD_ORGS)], width=0.6, texttemplate="%{y}", textposition="outside", cliponaxis=False)
        fig_tot.update_layout(**CHART_LAYOUT, showlegend=False,
                              margin=dict(t=42, b=20, l=20, r=20),
                              bargap=0.4)
        fig_tot.update_yaxes(tickformat="d", dtick=1, tick0=0)
        chart_card(fig_tot, key="fd_org_tot")
    with o2:
        fig_sub = px.bar(
            x=FD_ORGS,
            y=[sub_per_org[o] for o in FD_ORGS],
            labels={"x": "Unit", "y": "Submitted for Stratification"},
            title="Submitted for Stratification per Unit",
        )
        fig_sub.update_traces(marker_color=FD_ORG_COLORS[:len(FD_ORGS)], width=0.6, texttemplate="%{y}", textposition="outside", cliponaxis=False)
        fig_sub.update_layout(**CHART_LAYOUT, showlegend=False,
                              margin=dict(t=42, b=20, l=20, r=20),
                              bargap=0.4)
        fig_sub.update_yaxes(tickformat="d", dtick=1, tick0=0)
        chart_card(fig_sub, key="fd_org_sub")

    # ── Compute "new member" keys for the upload ─────────────────────────────
    # A "new member" is someone in the CURRENT version whose (name, rank)
    # didn't appear in the immediately-prior version. If there's no prior
    # version (first upload, or local preview), no one is flagged.
    _prior_keys = st.session_state.get("fd_prior_records_keys") or set()
    if _prior_keys:
        _new_keys = {_strat_member_key(m) for m in scoped
                     if _strat_member_key(m) not in _prior_keys}
    else:
        _new_keys = set()

    # ── Rosters (moved above the charts so the table is the primary view) ────
    sec_header("MSgt Roster", tag="SORTED BY LAST NAME")
    if msgt:
        _fd_render_roster_table(msgt, "msgt", new_member_keys=_new_keys)
    else:
        st.info(f"No MSgt submissions for {org_label}.")

    sec_header("SMSgt Roster", tag="SORTED BY LAST NAME")
    if smsgt:
        _fd_render_roster_table(smsgt, "smsgt", new_member_keys=_new_keys)
    else:
        st.info(f"No SMSgt submissions for {org_label}.")

    # ── Score Distributions ───────────────────────────────────────────────────
    sec_header(f"Score Distributions — {org_label}", tag="BY CATEGORY")
    # MSgt + SMSgt are the only ranks in scope for SNCO Stratification.
    _STRAT_RANKS = ["MSgt", "SMSgt"]
    # Per-score color palette — same MS-Office-style palette used by the
    # TIG / TIS charts in Unit Overview, applied to scores 0..20 (covers all
    # individual categories at 0..5 and totals at 0..20). Keeps the look
    # consistent across the dashboard.
    _STRAT_SCORE_COLORS = {
         0: "#4472C4",  # blue
         1: "#ED7D31",  # orange
         2: "#A5A5A5",  # grey
         3: "#FFC000",  # gold
         4: "#5B9BD5",  # azure
         5: "#70AD47",  # green
         6: "#264478",  # navy
         7: "#9E480E",  # rust
         8: "#636363",  # dark grey
         9: "#997300",  # dark gold
        10: "#255E91",  # deep blue
        11: "#43682B",  # deep green
        12: "#2F5597",  # steel blue
        13: "#843C0C",  # deep rust
        14: "#404040",  # charcoal
        15: "#7F6000",  # bronze
        16: "#1F4E79",  # navy
        17: "#375623",  # forest
        18: "#1F3864",  # midnight blue
        19: "#7F3F00",  # mahogany
        20: "#BF9000",  # antique gold
    }
    def _strat_score_color(v):
        if v < 0:
            v = 0
        if v in _STRAT_SCORE_COLORS:
            return _STRAT_SCORE_COLORS[v]
        return _STRAT_SCORE_COLORS[v % 21]

    def _section(cols_def, section_title, key_prefix):
        """Render one chart per category in `cols_def`. Each chart is a 1×2
        subplot grid (MSgt | SMSgt). Bars are colored per integer score
        value with a shared legend on the right; every score from 0..max_pts
        is a tick on the x-axis (so the full rubric range is visible even
        when some scores have zero members)."""
        from plotly.subplots import make_subplots

        st.markdown(
            f'<div style="font-family:Barlow Condensed,sans-serif;font-size:15px;'
            f'font-weight:700;color:#9dc4db;letter-spacing:1.5px;text-transform:uppercase;'
            f'margin:4px 0 6px 0;border-bottom:1px solid rgba(240,192,48,0.22);'
            f'padding-bottom:4px;">{section_title}</div>',
            unsafe_allow_html=True,
        )
        for key, label, max_pts in cols_def:
            # Bin all values across both ranks. Use the rubric max_pts as the
            # x-axis ceiling so the chart shows the FULL possible range, not
            # just the observed range.
            per_rank_bins = {}
            for rank in _STRAT_RANKS:
                vals = [m[key] for m in scoped
                        if m.get("rank") == rank and m.get(key) is not None]
                bins = {}
                for v in vals:
                    k = int(round(v))
                    bins[k] = bins.get(k, 0) + 1
                per_rank_bins[rank] = bins

            any_data = any(per_rank_bins[r] for r in _STRAT_RANKS)
            if not any_data:
                st.markdown(
                    f'<div style="background:#162050;border:1px solid rgba(240,192,48,0.2);'
                    f'border-radius:8px;padding:18px;color:#7a93c0;text-align:center;'
                    f'font-family:Barlow Condensed,sans-serif;letter-spacing:1px;'
                    f'text-transform:uppercase;margin-bottom:12px;">{label} — No data</div>',
                    unsafe_allow_html=True,
                )
                continue

            # X-axis: 0..max_pts (full rubric range). If any observed value
            # somehow exceeds max_pts (data anomaly), extend to cover it.
            observed_max = 0
            for rank in _STRAT_RANKS:
                if per_rank_bins[rank]:
                    observed_max = max(observed_max, max(per_rank_bins[rank].keys()))
            xmax = max(max_pts, observed_max)
            score_vals = list(range(0, xmax + 1))
            score_strs = [str(v) for v in score_vals]

            # Compute global y-max for shared scale.
            ymax = 1
            for rank in _STRAT_RANKS:
                if per_rank_bins[rank]:
                    ymax = max(ymax, max(per_rank_bins[rank].values()))
            if ymax <= 5:    _ydtick = 1
            elif ymax <= 15: _ydtick = 2
            elif ymax <= 30: _ydtick = 5
            else:            _ydtick = 10

            fig = make_subplots(
                rows=1, cols=len(_STRAT_RANKS),
                subplot_titles=_STRAT_RANKS,
                shared_yaxes=True,
                horizontal_spacing=0.06,
            )

            # One trace per (rank, score). Using legendgroup deduplicates the
            # legend so each score color appears once across the whole chart.
            seen_in_legend = set()
            for ci, rank in enumerate(_STRAT_RANKS, start=1):
                bins = per_rank_bins[rank]
                for v in score_vals:
                    count = bins.get(v, 0)
                    color = _strat_score_color(v)
                    show_in_legend = v not in seen_in_legend
                    seen_in_legend.add(v)
                    fig.add_trace(
                        go.Bar(
                            x=[str(v)],
                            y=[count],
                            marker=dict(color=color, line=dict(width=0)),
                            text=[str(count)],
                            textposition="outside",
                            textfont=dict(family="Barlow Condensed, sans-serif",
                                          size=12, color="#ffffff"),
                            cliponaxis=False,
                            name=str(v),
                            legendgroup=str(v),
                            showlegend=show_in_legend,
                            width=0.7,
                            hovertemplate=(f"<b>{rank} · score {v}</b><br>"
                                           f"{count} member(s)<extra></extra>"),
                        ),
                        row=1, col=ci,
                    )

                # X-axis: categorical with every score from 0..xmax pinned as
                # a tick so the full rubric range is always visible.
                fig.update_xaxes(
                    row=1, col=ci,
                    type="category",
                    categoryorder="array",
                    categoryarray=score_strs,
                    tickmode="array",
                    tickvals=score_strs,
                    ticktext=score_strs,
                    title_text="Score" if ci == 1 else None,
                    showgrid=False,
                    zeroline=False,
                    showline=True,
                    linecolor="rgba(240,192,48,0.2)",
                    linewidth=1,
                    tickfont=dict(family="Barlow Condensed, sans-serif",
                                  size=11, color="#9dc4db"),
                )
                fig.update_yaxes(
                    row=1, col=ci,
                    tickformat="d",
                    dtick=_ydtick,
                    tick0=0,
                    range=[0, ymax + max(2, ymax * 0.25)],
                    showgrid=True,
                    gridcolor="rgba(240,192,48,0.08)",
                    zeroline=False,
                    showline=(ci == 1),
                    linecolor="rgba(240,192,48,0.2)",
                    linewidth=1,
                    title_text="Members" if ci == 1 else None,
                    tickfont=dict(family="Barlow, sans-serif",
                                  size=11, color="#9dc4db"),
                )

            for annot in fig.layout.annotations:
                annot.font = dict(family="Barlow Condensed, sans-serif",
                                  size=13, color="#f0c030")

            _layout = {**CHART_LAYOUT}
            _layout["legend"] = {**(CHART_LAYOUT.get("legend") or {}),
                                 "title": {"text": "Score"}}
            fig.update_layout(
                **_layout,
                margin=dict(t=60, b=40, l=20, r=20),
                title=dict(
                    text=f"{label} — Score Distribution (max {max_pts} pts)",
                    font=dict(family="Barlow Condensed, sans-serif",
                              size=14, color="#ffffff"),
                ),
                bargap=0.15,
            )
            chart_card(fig, key=f"{key_prefix}_{key}")

    _section(FD_EVAL_RECORD_COLS, "Evaluation of Record", "fd_evalrec")
    _section(FD_EPB_COLS,         "Current EPB",          "fd_epb")

    # ── Stratification Overall Scores (only if any data exists) ───────────────
    if has_strat:
        sec_header("Stratification Overall Scores", tag="STRAT SCORE")
        # Stacked vertically — MSgt on top, SMSgt below — so longer lists of
        # names get the full page width instead of being cramped side-by-side.
        for label, rk in [
            ("MSgt",  msgt),
            ("SMSgt", smsgt),
        ]:
            sr = sorted(
                [r for r in rk if r["stratScore"] is not None],
                key=lambda r: -r["stratScore"]
            )
            if not sr:
                st.markdown(
                    f'<div style="background:#162050;border:1px solid rgba(240,192,48,0.2);'
                    f'border-radius:8px;padding:18px;color:#7a93c0;text-align:center;'
                    f'font-family:Barlow Condensed,sans-serif;letter-spacing:1px;'
                    f'text-transform:uppercase;margin-bottom:12px;">{label} — No stratification scores</div>',
                    unsafe_allow_html=True,
                )
                continue
            fig = px.bar(
                x=[r["name"] for r in sr],
                y=[r["stratScore"] for r in sr],
                labels={"x": "Member", "y": "Strat Score"},
                title=f"{label} — sorted high to low",
            )
            fig.update_traces(marker_color="#F2C400", width=0.6,
                              texttemplate="%{y:.0f}", textposition="outside",
                              cliponaxis=False)
            fig.update_layout(**CHART_LAYOUT, showlegend=False,
                              margin=dict(t=42, b=80, l=20, r=20),
                              bargap=0.4,
                              yaxis=dict(tickformat="d"))
            # For very small N, pad the x-axis so a single bar doesn't expand
            # to fill the entire chart width and look ridiculous.
            if len(sr) < 5:
                # extend the categorical axis with phantom slots on the right
                fig.update_xaxes(range=[-0.5, max(4.5, len(sr) - 0.5)])
            fig.update_xaxes(tickangle=-35)
            # Y-axis: integer ticks but adapt density to the data range so we
            # don't end up with 26 overlapping labels on a 25-tall chart.
            ymax = max((r["stratScore"] or 0) for r in sr)
            if ymax <= 10:
                _dtick = 1
            elif ymax <= 25:
                _dtick = 2
            elif ymax <= 50:
                _dtick = 5
            else:
                _dtick = 10
            fig.update_yaxes(tickformat="d", dtick=_dtick, tick0=0)
            chart_card(fig, key=f"fd_strat_{label}")


# ── Promotion Scorecard tab ──────────────────────────────────────────────────
# Reuses the per-member scorecard logic from `scorecard_summary()` (the same
# function Individual Profile → Scorecard tab uses) and applies it to every
# member in the squadron.

# All four ranks (SSgt, TSgt, MSgt, SMSgt) get the same 7 categories. Max
# points per category come from scorecard_summary's hardcoded values.
_PS_CATS = [
    # (canonical_name,                   short_label,    max_pts)
    ("Primary Duty Performance",        "Primary Duty", 5),
    ("Leadership",                      "Leadership",   5),
    ("Assignments",                     "Assignments",  3),
    ("Professional Military Education", "PME",          5),
    ("Higher Education",                "Higher Ed",    5),
    ("Awards and Decorations",          "Awards & Decs",5),
    ("Fitness",                         "Fitness",      5),
]
_PS_MAX_TOTAL = sum(c[2] for c in _PS_CATS)  # 33
_PS_RANKS = ["SSgt", "TSgt", "MSgt", "SMSgt"]


def _ps_compute_scorecards(df):
    """Run scorecard_summary on every SSgt+ member; return list of dicts
    shaped for the Promotion Scorecard tab. Junior ranks (Amn, A1C, SrA) are
    skipped entirely — they aren't promotion-board candidates."""
    out = []
    if df is None or df.empty:
        return out
    for _, row in df.iterrows():
        rank = str(row.get("Rank", "") or "").strip()
        # Promotion Scorecards only apply to SSgt and above.
        if rank not in _PS_RANKS:
            continue
        first = str(row.get("FirstName", "") or "").strip()
        last  = str(row.get("LastName", "") or "").strip()
        if not (first or last):
            continue
        full_name = f"{first} {last}".strip()
        unit = str(row.get("_unit_name", "") or "").strip()
        flight = str(row.get("Flight", "") or "").strip()
        dafsc = str(row.get("DAFSC", "") or "").strip() or "—"
        last_mod = str(row.get("LastEdit", "") or "").strip()

        rubric_label, cats = scorecard_summary(row)
        has_rubric = bool(cats)
        cat_map = {c[0]: c[1] for c in cats}
        scored = {canon: cat_map.get(canon) for canon, _, _ in _PS_CATS}
        total = sum(v for v in scored.values() if isinstance(v, (int, float)))
        out.append({
            "name":          full_name,
            "rank":          rank,
            "unit":          unit,
            "flight":        flight,
            "dafsc":         dafsc,
            "last_modified": last_mod,
            "total":         int(total) if has_rubric else None,
            "max_total":     _PS_MAX_TOTAL if has_rubric else None,
            "cats":          scored,
            "rubric_label":  rubric_label,
            "has_rubric":    has_rubric,
        })
    return out


_PS_TOP_N = 50


def _ps_render_total_charts(scorecards, org_label):
    """One bar chart per rank (SSgt/TSgt/MSgt/SMSgt), vertically stacked.
    X-axis: member names. Y-axis: total scorecard score. Always caps each
    rank chart at the top 50 members so the All Units view stays
    readable; a footnote in the header announces the cap."""
    sec_header(f"Member Scorecard Total Distribution — {org_label}",
               tag=f"TOP {_PS_TOP_N} PER RANK")
    st.markdown(
        f"""
        <style>
        /* Pull the note's stElementContainer up tight against the section
           header above. Streamlit wraps every markdown call in its own
           container with default vertical spacing; we target this specific
           one via :has() on its inner class. */
        div[data-testid="stElementContainer"]:has(.ps-top-n-note) {{
            margin-top: -16px !important;
            margin-bottom: 0 !important;
            padding-top: 0 !important;
            min-height: 0 !important;
        }}
        .ps-top-n-note {{
            font-family: Barlow, sans-serif; font-size: 14px;
            color: #9dc4db; font-style: italic;
            margin: 0 0 8px 0; line-height: 1.4;
        }}
        </style>
        <div class="ps-top-n-note">
          Note: Each rank chart shows the top {_PS_TOP_N} members by total
          scorecard score. Members beyond the top {_PS_TOP_N} appear in the
          roster table above.
        </div>
        """,
        unsafe_allow_html=True,
    )
    any_drawn = False
    for rank in _PS_RANKS:
        rk = [s for s in scorecards if s["rank"] == rank and s["has_rubric"]
              and s["total"] is not None]
        rk = sorted(rk, key=lambda r: -r["total"])
        total_in_rank = len(rk)
        rk = rk[:_PS_TOP_N]   # always cap to top 50 for chart readability
        if not rk:
            st.markdown(
                f'<div style="background:#162050;border:1px solid rgba(240,192,48,0.2);'
                f'border-radius:8px;padding:18px;color:#7a93c0;text-align:center;'
                f'font-family:Barlow Condensed,sans-serif;letter-spacing:1px;'
                f'text-transform:uppercase;margin-bottom:12px;">{rank} — No data</div>',
                unsafe_allow_html=True,
            )
            continue
        any_drawn = True
        title_suffix = (
            f"showing top {_PS_TOP_N} of {total_in_rank} (max {_PS_MAX_TOTAL} points)"
            if total_in_rank > _PS_TOP_N
            else f"sorted high to low (max {_PS_MAX_TOTAL} points)"
        )
        fig = px.bar(
            x=[r["name"] for r in rk],
            y=[r["total"] for r in rk],
            labels={"x": "Member", "y": "Total Score"},
            title=f"{rank} — {title_suffix}",
        )
        fig.update_traces(marker_color="#F2C400", width=0.6, texttemplate="%{y}", textposition="outside", cliponaxis=False)
        fig.update_layout(**CHART_LAYOUT, showlegend=False,
                          margin=dict(t=42, b=80, l=20, r=20),
                          bargap=0.4)
        if len(rk) < 5:
            fig.update_xaxes(range=[-0.5, max(4.5, len(rk) - 0.5)])
        fig.update_xaxes(tickangle=-35)
        # Y-axis: 0..33 max, integer ticks every 5 so labels don't crowd
        fig.update_yaxes(tickformat="d", dtick=5, tick0=0,
                         range=[0, _PS_MAX_TOTAL + 1])
        chart_card(fig, key=f"ps_total_{rank}")
    if not any_drawn:
        st.info("No scorecard data available for any rank in this squadron.")


def _ps_render_category_distributions(scorecards, org_label):
    """One chart per category (vertically stacked across the page). Each chart
    is a 1×4 subplot grid (one column per rank: SSgt / TSgt / MSgt / SMSgt).
    Within each subplot, the x-axis is the score value (0..max_pts) and bars
    show the count of members at that score. The score is the x-axis label
    natively — no annotation/offset hacks needed.
    """
    from plotly.subplots import make_subplots

    sec_header(f"Category Scoring Distribution — {org_label}",
               tag="BY CATEGORY")
    score_colors = {
        0: "#C91F2C",  # red — zero
        1: "#F2C400",  # gold
        2: "#6E93B6",  # steel
        3: "#1F2A8A",  # navy
        4: "#4A66AC",  # mid blue
        5: "#5B9BD5",  # azure
    }
    for canon, short, max_pts in _PS_CATS:
        score_vals = list(range(0, max_pts + 1))

        fig = make_subplots(
            rows=1, cols=len(_PS_RANKS),
            subplot_titles=_PS_RANKS,
            shared_yaxes=True,
            horizontal_spacing=0.04,
        )

        # Compute the global y-max across all ranks so all subplots share the
        # same visual scale.
        global_max = 0
        rank_data = {}
        for rank in _PS_RANKS:
            members_in_rank = [s for s in scorecards
                               if s["rank"] == rank and s["has_rubric"]]
            counts = [
                sum(1 for s in members_in_rank if s["cats"].get(canon) == v)
                for v in score_vals
            ]
            rank_data[rank] = counts
            if counts:
                global_max = max(global_max, max(counts))

        ymax = max(global_max, 1)
        if ymax <= 5:
            _dtick = 1
        elif ymax <= 15:
            _dtick = 2
        else:
            _dtick = 5

        for ci, rank in enumerate(_PS_RANKS, start=1):
            counts = rank_data[rank]
            for v_idx, v in enumerate(score_vals):
                count = counts[v_idx]
                color = score_colors.get(v, "#5B9BD5")
                # One entry per score in the legend; deduplicated by
                # legendgroup so the same score color appears once across
                # the whole chart.
                show_in_legend = (ci == 1)
                fig.add_trace(
                    go.Bar(
                        x=[str(v)],
                        y=[count],
                        marker=dict(color=color,
                                    line=dict(color="rgba(255,255,255,0.06)",
                                              width=0.5)),
                        text=[str(count)],
                        textposition="outside",
                        textfont=dict(family="Barlow Condensed, sans-serif",
                                      size=12, color="#ffffff"),
                        cliponaxis=False,
                        name=str(v),
                        legendgroup=str(v),
                        showlegend=show_in_legend,
                        width=0.7,
                        hovertemplate=(f"<b>{rank} · score {v}</b><br>"
                                       f"{count} member(s)<extra></extra>"),
                    ),
                    row=1, col=ci,
                )
            # X-axis: explicit category order + tickmode='array' with all
            # tickvals so EVERY score value (0..max) renders as a tick label.
            # Without explicit tickvals, narrow subplots auto-thin to 0,2,4.
            _str_scores = [str(v) for v in score_vals]
            fig.update_xaxes(
                row=1, col=ci,
                type="category",
                categoryorder="array",
                categoryarray=_str_scores,
                tickmode="array",
                tickvals=_str_scores,
                ticktext=_str_scores,
                title_text="Score" if ci == 1 else None,
                showgrid=False,
                zeroline=False,
                showline=True,
                linecolor="rgba(240,192,48,0.2)",
                linewidth=1,
                tickfont=dict(family="Barlow Condensed, sans-serif",
                              size=11, color="#9dc4db"),
            )
            # Y-axis: shared scale across subplots, integer ticks, force start
            # at 0 to ensure no negative tick labels. Show gridlines on every
            # subplot (with shared_yaxes the lines extend across all panels);
            # show the y-axis line only on the leftmost panel where the tick
            # labels are. Show the right-edge axis line on the rightmost panel
            # so the chart visually closes.
            fig.update_yaxes(
                row=1, col=ci,
                tickformat="d",
                dtick=_dtick,
                tick0=0,
                range=[0, ymax + max(2, ymax * 0.25)],
                showgrid=True,
                gridcolor="rgba(240,192,48,0.08)",
                zeroline=False,
                showline=(ci == 1),
                linecolor="rgba(240,192,48,0.2)",
                linewidth=1,
                title_text="Count" if ci == 1 else None,
                tickfont=dict(family="Barlow, sans-serif",
                              size=11, color="#9dc4db"),
            )

        # Style the per-subplot rank titles so they read as rank labels.
        for annot in fig.layout.annotations:
            annot.font = dict(family="Barlow Condensed, sans-serif",
                              size=13, color="#f0c030")

        _layout = {**CHART_LAYOUT}
        _layout["legend"] = {**(CHART_LAYOUT.get("legend") or {}),
                             "title": {"text": "Score"}}
        fig.update_layout(
            **_layout,
            margin=dict(t=60, b=40, l=20, r=20),
            title=dict(
                text=f"{org_label} — {canon} Score Distribution ({max_pts} pts max)",
                font=dict(family="Barlow Condensed, sans-serif",
                          size=14, color="#ffffff"),
            ),
            bargap=0.2,
        )

        chart_card(fig, key=f"ps_cat_{canon}")


def _ps_render_promotion_readiness(scorecards, org_label):
    """Stacked horizontal bars per rank showing the percentage of members in
    each total-score bucket. Quick at-a-glance pipeline health: green-heavy
    bars mean a deep bench; red-heavy bars mean room for growth."""
    sec_header(f"Promotion-Readiness Distribution — {org_label}",
               tag="PIPELINE HEALTH")
    # Buckets across the 0..33 range. Tunable; chosen to give meaningful
    # spread for the existing scoring rubric.
    buckets = [
        ("0–10",  0,  10,  "#C91F2C"),  # red
        ("11–20", 11, 20,  "#F2C400"),  # gold
        ("21–27", 21, 27,  "#5B9BD5"),  # azure
        ("28–33", 28, 33,  "#22c55e"),  # green
    ]
    records = []
    for rank in _PS_RANKS:
        members_in_rank = [s for s in scorecards
                           if s["rank"] == rank and s["has_rubric"]
                           and s["total"] is not None]
        n = len(members_in_rank)
        for label, lo, hi, _color in buckets:
            count = sum(1 for s in members_in_rank if lo <= s["total"] <= hi)
            pct = (count / n * 100) if n else 0
            records.append({
                "Rank": rank, "Bucket": label,
                "Members": count, "Pct": round(pct, 1),
                "RankTotal": n,
            })
    df = pd.DataFrame(records)
    if df.empty or df["Members"].sum() == 0:
        st.info("No scored members yet — pipeline chart will populate once "
                "members have scorecard data.")
        return
    bucket_colors = {b[0]: b[3] for b in buckets}
    fig = px.bar(
        df, y="Rank", x="Pct", color="Bucket",
        orientation="h", barmode="stack",
        category_orders={"Rank": _PS_RANKS,
                         "Bucket": [b[0] for b in buckets]},
        color_discrete_map=bucket_colors,
        title=f"{org_label} — % of members in each total-score band",
        custom_data=["Members", "RankTotal"],
    )
    fig.update_traces(
        texttemplate="%{customdata[0]}",
        textposition="inside",
        insidetextanchor="middle",
        insidetextfont=dict(color="#ffffff"),
        hovertemplate="<b>%{y} · %{fullData.name}</b><br>"
                      "%{customdata[0]} of %{customdata[1]} members "
                      "(%{x:.1f}%)<extra></extra>",
    )
    _layout = {**CHART_LAYOUT}
    _layout["legend"] = {**(CHART_LAYOUT.get("legend") or {}),
                         "title": {"text": "Total band"}}
    fig.update_layout(**_layout,
                      margin=dict(t=42, b=40, l=20, r=20),
                      bargap=0.35)
    fig.update_xaxes(tickformat="d", dtick=20, range=[0, 100],
                     ticksuffix="%")
    chart_card(fig, key="ps_pipeline")


def _ps_render_table(scorecards, key_prefix="ps"):
    """Render the Promotion Scorecard roster as a sortable / multi-select-
    filterable table. Mirrors `_fd_render_roster_table` styling so the page
    feels cohesive."""
    import html as _html
    import uuid as _uuid

    # Default sort: rank ascending (lowest rank first → SSgt before TSgt
    # before MSgt before SMSgt) then last name alphabetical. Members
    # without a scorecard rubric (shouldn't normally exist for PS since
    # we filter to SSgt+) sort to the end.
    rank_idx = {r: i for i, r in enumerate(_PS_RANKS)}
    def _sort_key(r):
        has = 0 if r.get("has_rubric") else 1   # rubric rows first
        ri  = rank_idx.get(r.get("rank", ""), 99)
        # Pull last name out of "First Last" full name string.
        full = r.get("name", "") or ""
        parts = full.strip().split()
        last_name = parts[-1].lower() if parts else ""
        first_name = parts[0].lower() if parts else ""
        return (has, ri, last_name, first_name)
    sorted_rows = sorted(scorecards, key=_sort_key)

    # Column definitions — Name / Rank / AFSC / Unit / Flight / 7 categories
    # in user-specified order / Score / Last Modified.
    cols = [
        ("name",   "Name"),
        ("rank",   "Rank"),
        ("dafsc",  "AFSC"),
        ("unit",   "Unit"),
        ("flight", "Flight"),
    ]
    for canon, short, _max in _PS_CATS:
        cols.append((f"cat::{canon}", short))
    cols.append(("total_str",     "Score"))
    cols.append(("last_modified", "Last Modified"))

    def _fmt_last_modified(raw):
        """Render Last Modified as 'YYYY-MM-DD HH:MM'. Tries ISO format first
        (handles '2026-04-24T22:21:00.000Z' and similar) and falls back to
        the original string if it can't be parsed."""
        if not raw:
            return "—"
        try:
            ts = pd.to_datetime(raw, errors="coerce")
            if pd.isna(ts):
                return str(raw)
            return ts.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return str(raw)

    def _disp(r, k):
        if k == "total_str":
            if not r.get("has_rubric"):
                return "No data"
            try:
                return str(int(round(float(r["total"]))))
            except (TypeError, ValueError):
                return str(r["total"])
        if k == "last_modified":
            return _fmt_last_modified(r.get("last_modified", ""))
        if k.startswith("cat::"):
            if not r.get("has_rubric"):
                return "No data"
            canon = k[5:]
            v = r["cats"].get(canon)
            if v is None:
                return "—"
            try:
                return str(int(round(float(v))))
            except (TypeError, ValueError):
                return str(v)
        v = r.get(k, "")
        if v is None or v == "":
            return "—"
        return str(v)

    header_cells = ""
    for idx, (key, label) in enumerate(cols):
        header_cells += (
            f'<th data-col-idx="{idx}" data-col-key="{key}">'
            f'<div class="wg-th-inner">'
            f'<div class="wg-th-label" data-col-idx="{idx}">'
            f'<span class="wg-th-name">{_html.escape(label)}</span>'
            f'<span class="wg-th-sort">⇅</span>'
            f'</div>'
            f'<button type="button" class="wg-th-filter" data-col-idx="{idx}" '
            f'aria-haspopup="listbox" aria-expanded="false">'
            f'<span class="wg-filter-text">(all)</span>'
            f'<span class="wg-filter-caret">▾</span></button>'
            f'</div></th>'
        )
    body_rows_html = ""
    _bold_cols = {"name", "rank", "total_str"}
    for r in sorted_rows:
        cells = ""
        for key, _label in cols:
            classes = []
            if key == "total_str" and not r.get("has_rubric"):
                classes.append("wg-no-data")
            if key in _bold_cols:
                classes.append("wg-bold")
            cls = f' class="{" ".join(classes)}"' if classes else ""
            cells += f'<td{cls}>{_html.escape(_disp(r, key))}</td>'
        body_rows_html += f'<tr>{cells}</tr>'

    tid = key_prefix + "_" + _uuid.uuid4().hex[:8]
    nrows = len(sorted_rows)
    # Cap at 720px (vs FD strat's 640) — PS table can be larger since it
    # often shows many ranks at once. The inner scroll wrapper handles
    # overflow when rows exceed available height.
    iframe_height = max(280, min(720, 95 + nrows * 28))

    # Reuse the same iframe structure used for the FD strat roster — just
    # different ID and contents. Most of the CSS/JS is identical (sort,
    # multi-select popover, filter bar). Inline it here so the table is
    # self-contained.
    table_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  html, body {{
    margin: 0; padding: 0; background: transparent;
    font-family: 'Barlow', sans-serif; color: #dde6f5;
  }}
  .wg-tbl-toolbar {{
    display: flex; gap: 12px; align-items: center;
    padding: 4px 0 8px 0;
  }}
  .wg-tbl-clear {{
    padding: 6px 14px; background: #2a4090; color: #dde6f5;
    border: 1px solid rgba(240,192,48,0.3); border-radius: 4px;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 11px; font-weight: 700;
    letter-spacing: 1px; text-transform: uppercase;
    cursor: pointer; transition: all 0.15s ease;
  }}
  .wg-tbl-clear:hover {{ background: #3551a8; }}
  .wg-tbl-count {{ font-size: 12px; color: #9dc4db; }}
  .wg-tbl-scroll {{
    max-width: 100%;
    max-height: {iframe_height - 70}px;
    overflow: auto;
    border: 1px solid rgba(240,192,48,0.2);
    border-radius: 4px; background: #162050;
  }}
  table.wg-tbl {{
    border-collapse: collapse; font-size: 0.82rem; width: 100%;
  }}
  table.wg-tbl thead th {{
    position: sticky; top: 0; z-index: 2;
    background: #1f3272; padding: 0;
    border: 1px solid rgba(240,192,48,0.2);
    white-space: nowrap; font-weight: 700; color: #f0c030;
  }}
  .wg-th-inner {{ display: flex; flex-direction: column; gap: 4px; padding: 6px 8px; }}
  .wg-th-label {{
    display: flex; align-items: center; justify-content: space-between;
    gap: 6px; cursor: pointer; user-select: none;
    text-transform: uppercase; letter-spacing: 0.5px; font-size: 11px;
  }}
  .wg-th-sort {{ opacity: 0.5; font-size: 10px; }}
  .wg-th-label.wg-sorted .wg-th-sort {{ opacity: 1; color: #f0c030; }}
  .wg-th-filter {{
    display: flex; align-items: center; justify-content: space-between;
    gap: 4px; padding: 3px 6px; background: #0e1a3d;
    border: 1px solid rgba(240,192,48,0.25); border-radius: 3px;
    cursor: pointer; font-family: 'Barlow', sans-serif; font-size: 11px;
    color: #dde6f5; min-width: 70px;
  }}
  .wg-th-filter:hover {{ background: #1a2a5e; }}
  .wg-th-filter[data-active="true"] {{ background: #c9960a; color: #0e1a3d; border-color: #f0c030; }}
  .wg-th-filter[data-active="true"] .wg-filter-caret {{ color: #0e1a3d; }}
  .wg-filter-caret {{ font-size: 9px; opacity: 0.7; }}
  table.wg-tbl tbody td {{
    padding: 6px 10px; border-bottom: 1px solid rgba(255,255,255,0.06);
    color: #dde6f5; vertical-align: middle;
    white-space: nowrap;
  }}
  table.wg-tbl tbody td.wg-no-data {{ color: #c9960a; font-style: italic; }}
  table.wg-tbl tbody td.wg-bold {{ font-weight: 700; }}
  table.wg-tbl tbody tr:nth-child(even) {{ background: rgba(255,255,255,0.02); }}
  table.wg-tbl tbody tr:hover {{ background: rgba(240,192,48,0.06); }}
  .wg-row-hidden {{ display: none; }}
  .wg-popover {{
    position: fixed; z-index: 9999; display: none;
    background: #0e1a3d; border: 1px solid rgba(240,192,48,0.4);
    border-radius: 4px; padding: 8px; min-width: 180px; max-width: 280px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.6);
    font-family: 'Barlow', sans-serif;
  }}
  .wg-popover[data-open="true"] {{ display: block; }}
  .wg-popover-search {{
    width: 100%; padding: 4px 6px; margin-bottom: 6px;
    background: #1a2a5e; color: #dde6f5;
    border: 1px solid rgba(240,192,48,0.3); border-radius: 3px;
    font-family: 'Barlow', sans-serif; font-size: 12px;
  }}
  .wg-popover-list {{
    max-height: 200px; overflow-y: auto;
    background: #1a2a5e; border: 1px solid rgba(240,192,48,0.2);
    border-radius: 3px;
  }}
  .wg-popover-list label {{
    display: flex; align-items: center; gap: 6px; padding: 4px 8px;
    color: #dde6f5; font-size: 12px; cursor: pointer;
  }}
  .wg-popover-list label:hover {{ background: #2a4090; }}
  .wg-popover-list input[type=checkbox] {{ margin: 0; cursor: pointer; }}
  .wg-empty {{ padding: 8px; color: #7a93c0; text-align: center; font-size: 11px; font-style: italic; }}
  .wg-popover-actions {{
    display: flex; gap: 6px; margin-top: 8px;
  }}
  .wg-popover-actions button {{
    flex: 1; padding: 5px; border-radius: 3px; cursor: pointer;
    font-family: 'Barlow Condensed', sans-serif; font-size: 11px;
    font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase;
    border: 1px solid rgba(240,192,48,0.3);
  }}
  .wg-popover-cancel {{ background: transparent; color: #dde6f5; border-color: rgba(240,192,48,0.3); }}
  .wg-popover-apply {{ background: #f0c030; color: #0e1a3d; border-color: #f0c030; }}
  .wg-popover-cancel:hover {{ background: #2a4090; }}
  .wg-popover-apply:hover {{ background: #f8d96a; }}
  .wg-popover-toprow {{
    display: flex; gap: 6px; margin: 4px 0 6px 0;
  }}
  .wg-popover-toprow button {{
    flex: 1; padding: 4px 6px; border-radius: 3px; cursor: pointer;
    font-family: 'Barlow Condensed', sans-serif; font-size: 11px;
    font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase;
    background: #1f3272; color: #dde6f5;
    border: 1px solid rgba(240,192,48,0.3);
  }}
  .wg-popover-toprow button:hover {{
    background: #2a4090; border-color: #f0c030;
  }}
</style></head>
<body>
<div class="wg-tbl-toolbar">
  <button id="{tid}-clear" class="wg-tbl-clear">Clear filters</button>
  <span id="{tid}-count" class="wg-tbl-count">Showing {nrows} of {nrows}</span>
</div>
<div class="wg-tbl-scroll">
<table class="wg-tbl" id="{tid}">
  <thead><tr>{header_cells}</tr></thead>
  <tbody>{body_rows_html}</tbody>
</table>
</div>
<div id="{tid}-pop" class="wg-popover">
  <input type="text" class="wg-popover-search" placeholder="Search values..." />
  <div class="wg-popover-toprow">
    <button class="wg-popover-selectall" type="button">Select all</button>
    <button class="wg-popover-clear-pop" type="button">Clear</button>
  </div>
  <div class="wg-popover-list"></div>
  <div class="wg-popover-actions">
    <button class="wg-popover-cancel" type="button">Cancel</button>
    <button class="wg-popover-apply"  type="button">Apply</button>
  </div>
</div>
<script>
(function() {{
  var table = document.getElementById("{tid}");
  if (!table) return;
  var tbody = table.querySelector("tbody");
  var rows = Array.from(tbody.querySelectorAll("tr"));
  var ths = Array.from(table.querySelectorAll("thead th"));
  var pop = document.getElementById("{tid}-pop");
  var popList = pop.querySelector(".wg-popover-list");
  var popSearch = pop.querySelector(".wg-popover-search");
  var btnApply = pop.querySelector(".wg-popover-apply");
  var btnCancel = pop.querySelector(".wg-popover-cancel");
  var btnSelectAll = pop.querySelector(".wg-popover-selectall");
  var btnClearPop  = pop.querySelector(".wg-popover-clear-pop");
  var clearBtn = document.getElementById("{tid}-clear");
  var countEl = document.getElementById("{tid}-count");
  var totalRows = rows.length;
  var filters = {{}};   // {{colIdx: Set(values)}}
  var sortColIdx = null;
  var sortDir = 1;

  var pendingColIdx = null;
  var pendingSelection = new Set();

  function applyFilters() {{
    var visible = 0;
    rows.forEach(function(tr) {{
      var keep = true;
      for (var ci in filters) {{
        var sel = filters[ci];
        if (!sel || sel.size === 0) continue;
        var cellText = tr.children[ci].textContent.trim();
        if (!sel.has(cellText)) {{ keep = false; break; }}
      }}
      tr.classList.toggle("wg-row-hidden", !keep);
      if (keep) visible++;
    }});
    countEl.textContent = "Showing " + visible + " of " + totalRows;
    ths.forEach(function(th, idx) {{
      var btn = th.querySelector(".wg-th-filter");
      if (!btn) return;
      var has = filters[idx] && filters[idx].size > 0;
      btn.setAttribute("data-active", has ? "true" : "false");
      btn.querySelector(".wg-filter-text").textContent =
        has ? (filters[idx].size + " selected") : "(all)";
    }});
  }}

  function openPopover(colIdx, anchorBtn) {{
    pendingColIdx = colIdx;
    var existing = filters[colIdx] || new Set();
    pendingSelection = new Set(existing);
    var availableVals = new Set();
    rows.forEach(function(tr) {{
      var hideForOther = false;
      for (var ci in filters) {{
        if (parseInt(ci, 10) === colIdx) continue;
        var sel = filters[ci];
        if (!sel || sel.size === 0) continue;
        var t = tr.children[ci].textContent.trim();
        if (!sel.has(t)) {{ hideForOther = true; break; }}
      }}
      if (!hideForOther) availableVals.add(tr.children[colIdx].textContent.trim());
    }});
    var sortedVals = Array.from(availableVals).sort(function(a, b) {{
      var aN = parseFloat(a), bN = parseFloat(b);
      if (!isNaN(aN) && !isNaN(bN)) return aN - bN;
      return a.localeCompare(b);
    }});
    popList.innerHTML = "";
    if (sortedVals.length === 0) {{
      var empty = document.createElement("div");
      empty.className = "wg-empty";
      empty.textContent = "No values to filter";
      popList.appendChild(empty);
    }} else {{
      sortedVals.forEach(function(v) {{
        var lbl = document.createElement("label");
        lbl.setAttribute("data-val", v);
        var cb = document.createElement("input");
        cb.type = "checkbox";
        cb.value = v;
        cb.checked = pendingSelection.has(v);
        cb.addEventListener("change", function() {{
          if (cb.checked) pendingSelection.add(v);
          else            pendingSelection.delete(v);
        }});
        var text = document.createElement("span");
        text.textContent = v;
        lbl.appendChild(cb);
        lbl.appendChild(text);
        popList.appendChild(lbl);
      }});
    }}
    popSearch.value = "";
    var rect = anchorBtn.getBoundingClientRect();
    pop.style.top = (rect.bottom + 4) + "px";
    pop.style.left = rect.left + "px";
    pop.setAttribute("data-open", "true");
    setTimeout(function() {{ popSearch.focus(); }}, 50);
  }}

  function closePopover() {{
    pop.setAttribute("data-open", "false");
    pendingColIdx = null;
  }}

  popSearch.addEventListener("input", function() {{
    var q = popSearch.value.toLowerCase();
    Array.from(popList.querySelectorAll("label")).forEach(function(lbl) {{
      var v = lbl.getAttribute("data-val") || "";
      lbl.style.display = v.toLowerCase().indexOf(q) === -1 ? "none" : "";
    }});
  }});
  // Select All / Clear buttons in the popover toprow. Both operate on the
  // currently visible (search-filtered) rows only — same behavior as the FD
  // strat / Unit Overview tables.
  btnSelectAll.addEventListener("click", function() {{
    Array.from(popList.querySelectorAll("label")).forEach(function(lbl) {{
      if (lbl.style.display === "none") return;
      var cb = lbl.querySelector("input[type=checkbox]");
      if (cb) {{
        cb.checked = true;
        pendingSelection.add(cb.value);
      }}
    }});
  }});
  btnClearPop.addEventListener("click", function() {{
    Array.from(popList.querySelectorAll("label")).forEach(function(lbl) {{
      if (lbl.style.display === "none") return;
      var cb = lbl.querySelector("input[type=checkbox]");
      if (cb) {{
        cb.checked = false;
        pendingSelection.delete(cb.value);
      }}
    }});
  }});
  btnCancel.addEventListener("click", closePopover);
  btnApply.addEventListener("click", function() {{
    if (pendingColIdx !== null) {{
      filters[pendingColIdx] = pendingSelection;
      if (pendingSelection.size === 0) delete filters[pendingColIdx];
      applyFilters();
    }}
    closePopover();
  }});
  document.addEventListener("click", function(ev) {{
    if (pop.getAttribute("data-open") !== "true") return;
    if (pop.contains(ev.target)) return;
    if (ev.target.closest(".wg-th-filter")) return;
    closePopover();
  }});

  ths.forEach(function(th, idx) {{
    var btn = th.querySelector(".wg-th-filter");
    if (btn) {{
      btn.addEventListener("click", function(e) {{
        e.stopPropagation();
        if (pop.getAttribute("data-open") === "true" && pendingColIdx === idx) {{
          closePopover();
        }} else {{
          openPopover(idx, btn);
        }}
      }});
    }}
    var lbl = th.querySelector(".wg-th-label");
    if (lbl) {{
      lbl.addEventListener("click", function() {{
        if (sortColIdx === idx) sortDir = -sortDir;
        else                   {{ sortColIdx = idx; sortDir = 1; }}
        ths.forEach(function(t) {{
          var l = t.querySelector(".wg-th-label");
          if (l) l.classList.remove("wg-sorted");
        }});
        lbl.classList.add("wg-sorted");
        rows.sort(function(a, b) {{
          var va = a.children[idx].textContent.trim();
          var vb = b.children[idx].textContent.trim();
          var na = parseFloat(va), nb = parseFloat(vb);
          var cmp;
          if (!isNaN(na) && !isNaN(nb))      cmp = na - nb;
          else                               cmp = va.localeCompare(vb);
          return cmp * sortDir;
        }}).forEach(function(tr) {{ tbody.appendChild(tr); }});
      }});
    }}
  }});

  clearBtn.addEventListener("click", function() {{
    filters = {{}};
    sortColIdx = null;
    applyFilters();
    ths.forEach(function(t) {{
      var l = t.querySelector(".wg-th-label");
      if (l) l.classList.remove("wg-sorted");
    }});
  }});

  applyFilters();
}})();
</script></body></html>
"""
    # Export buttons above the iframe — same display logic as the rendered
    # table so CSV/XLSX content matches what the user sees on screen.
    _export_records = []
    for _r in sorted_rows:
        _rec = {}
        for _key, _label in cols:
            _rec[_label] = _disp(_r, _key)
        _export_records.append(_rec)
    _export_df = pd.DataFrame(_export_records)
    _render_table_export(_export_df, "promotion_scorecard", f"ps_{tid}")

    _components.html(table_html, height=iframe_height, scrolling=False)


def _render_promotion_scorecard_tab():
    """Promotion Scorecard tab — applies the per-member scorecard logic to
    every member in the squadron and renders charts + a roster table."""
    df = load_data()
    if df is None or df.empty:
        st.info("No member data available. Add members in Administration first.")
        return

    # Add `_unit_name` (squadron name) to the dataframe — load_data() returns
    # the raw rows with `_tenant_id` only; squadron name is resolved via the
    # tenant lookup, the same way Individual Profile does it.
    try:
        from database import get_all_tenants as _gat
        _tenant_lookup = {t["id"]: t["name"] for t in _gat()}
    except Exception:
        _tenant_lookup = {}
    df = df.copy()
    if "_tenant_id" in df.columns:
        df["_unit_name"] = df["_tenant_id"].map(
            lambda tid: _tenant_lookup.get(tid) if pd.notna(tid) else None
        )
    else:
        df["_unit_name"] = st.session_state.get("tenant_name") or None

    # Unit-only dropdown (no flight breakdown for promotion scorecards).
    # Order canonical units per FD_ORGS, then any non-canonical ones alphabetically.
    units_in_data = {str(u).strip() for u in df["_unit_name"].dropna()
                     if str(u).strip()}
    options = [("none", None), ("all", None)]
    for u in FD_ORGS:
        if u in units_in_data:
            options.append(("unit", u))
    for u in sorted(units_in_data):
        if u not in FD_ORGS:
            options.append(("unit", u))

    def _fmt_opt(opt):
        kind, unit = opt
        if kind == "none": return "No option selected"
        if kind == "all":  return "All Units"
        return unit

    selected = st.selectbox(
        "Select Unit",
        options=options,
        format_func=_fmt_opt,
        key="ps_squadron",
    )
    kind, unit = selected
    if kind == "none":
        st.markdown(
            '<div style="margin:6px 0 18px 0;padding:0;color:#9dc4db;'
            'font-family:Barlow Condensed,sans-serif;font-size:13px;'
            'letter-spacing:1.5px;text-transform:uppercase;">'
            'Select a unit from the dropdown above to load its promotion scorecard dashboard.</div>',
            unsafe_allow_html=True,
        )
        return

    if kind == "all":
        scoped_df = df.copy()
        org_label = "All Units"
    else:
        scoped_df = df[df["_unit_name"] == unit].copy()
        org_label = unit

    if scoped_df.empty:
        st.warning(f"No members found for {org_label}.")
        return

    scorecards = _ps_compute_scorecards(scoped_df)
    rubric_count = sum(1 for s in scorecards if s["has_rubric"])
    st.markdown(
        f'<div style="font-family:Barlow Condensed,sans-serif;font-size:11px;'
        f'letter-spacing:1px;text-transform:uppercase;color:#9dc4db;'
        f'padding:6px 0 14px 0;">{org_label} — '
        f'<span style="color:#22c55e;">{len(scorecards)} members</span> '
        f'<span style="color:#7a93c0;">· {rubric_count} with scorecard rubric</span></div>',
        unsafe_allow_html=True,
    )

    # Roster table (above the charts, per the same layout as SNCO Stratification).
    sec_header(f"Member Scorecards — {org_label}", tag="ROSTER")
    _ps_render_table(scorecards)

    # Per-rank total charts (vertically stacked) — capped at top 50.
    _ps_render_total_charts(scorecards, org_label)

    # Promotion-readiness pipeline (horizontal stacked, % of members per band).
    _ps_render_promotion_readiness(scorecards, org_label)

    # Per-category histograms (vertically stacked across the page).
    _ps_render_category_distributions(scorecards, org_label)


RANK_TIER_ORDER_DESC = ["SMSgt", "MSgt", "TSgt", "SSgt", "SrA", "A1C", "Amn"]


def _bench_norm_name(s):
    """Canonicalize a name for cross-source lookup (roster ↔ MS Forms strat
    sheet). Lowercase, strip punctuation, collapse whitespace, and sort the
    tokens so 'First Last', 'Last, First', and 'Last  First' all match.

    Used by `_bench_compute_scores` (producer of the score lookup) and by
    `_render_enlisted_bench_tab` (consumer) so the keys agree.
    """
    import re as _re
    s = (s or "").lower()
    s = _re.sub(r"[^\w\s]", " ", s)
    return " ".join(sorted(s.split()))


def _bench_compute_scores(members_df, strat_records):
    """Return a dict keyed by (norm_name, lower(rank)) → {strat_score, ps_total}.

    `members_df` is the unit roster from get_members/get_all_members.
    `strat_records` is the parsed list of strat records for the latest version.
    PS total is computed via the existing scorecard_summary helper for SSgt+.

    Names are normalized via `_bench_norm_name()` (lowercase, strip punctuation,
    sort the tokens) so the roster's "Gloria Washington" matches a strat sheet
    that has "Washington, Gloria" or "Washington Gloria" — MS Forms freeform
    name fields are inconsistent across raters.
    """
    out = {}

    # Strat scores indexed by (norm_name, rank).
    for r in (strat_records or []):
        name = (r.get("name") or "").strip()
        rank = (r.get("rank") or "").strip()
        if not name or not rank:
            continue
        key = (_bench_norm_name(name), rank.lower())
        out.setdefault(key, {})["strat_score"] = r.get("stratScore")

    # PS scores from member roster (SSgt+ only).
    if members_df is not None and not members_df.empty:
        for _, row in members_df.iterrows():
            rank = str(row.get("Rank", "") or "").strip()
            if rank not in ("SSgt", "TSgt", "MSgt", "SMSgt"):
                continue
            first = str(row.get("FirstName", "") or "").strip()
            last  = str(row.get("LastName", "") or "").strip()
            full_name = f"{first} {last}".strip()
            if not full_name:
                continue
            try:
                _, cats = scorecard_summary(row)
                if cats:
                    cat_map = {c[0]: c[1] for c in cats}
                    scored = {canon: cat_map.get(canon)
                              for canon, _, _ in _PS_CATS}
                    total = sum(v for v in scored.values()
                                if isinstance(v, (int, float)))
                    key = (_bench_norm_name(full_name), rank.lower())
                    out.setdefault(key, {})["ps_total"] = int(total)
            except Exception:
                continue

    return out


def _render_enlisted_bench_tab():
    """Enlisted Bench tab — drag-and-drop org chart for talent management.

    Layout: members are grouped into vertical columns by (unit · flight).
    Within each column, tiles stack top-down sorted by rank (highest first),
    then strat score (MSgt/SMSgt) or PS total (SSgt+), then last name.
    Managers can drag tiles within and across columns; the placements
    snap into vertical slots so the chart doesn't go ragged. Filters
    (unit / flight / rank / TIG / TIS / strat / PS) narrow the visible
    set without losing the saved layout.

    Members in the strat upload but NOT in the database appear in a
    "Not in database" panel on the right — a data-quality signal so the
    manager knows to add the missing roster entry.

    Save flow: the in-iframe Save button writes the layout JSON to browser
    localStorage. A `streamlit_javascript` poll (run outside the iframe)
    reads that key on each rerun; when it finds a fresh save signal, the
    Python handler persists to the DB and clears the localStorage keys.
    Scales to ~500 members because localStorage has multi-MB capacity
    versus the ~32 KB hard limit on URL-based round-tripping.

    To avoid a DB migration, the existing schema's `tier_rank` /
    `position_in_tier` columns are repurposed: `tier_rank` now stores
    "{unit}|{flight}" (the column key) and `position_in_tier` is the
    vertical slot inside that column.
    """
    import json as _json
    from streamlit_javascript import st_javascript

    role = st.session_state.get("role", "user")
    user_id = st.session_state.get("user_id")
    user_title = st.session_state.get("title", "")
    is_super = (role == "super_admin")
    _save_titles = {"Commander", "SEL", "Senior Enlisted Leader"}
    can_save = is_super or (user_title in _save_titles)

    # ── Bench-tab filter recolor ─────────────────────────────────────────────
    # The default Streamlit primary color (red/coral) shows through on
    # multiselect chips and slider tracks. Recolor to dark grey + white text
    # by targeting the widgets' own keys (.st-key-bench_filter_*) rather
    # than relying on sibling selectors — Streamlit's tab-panel wrapping
    # breaks `:has(.marker) ~` chains across container boundaries.
    st.markdown(
        """
        <style>
        /* Multiselect chips inside the bench filter widgets. */
        div[class*="st-key-bench_filter_"] [data-baseweb="tag"],
        div[class*="st-key-bench_filter_"] span[data-baseweb="tag"] {
            background-color: #4a4a4a !important;
            border-color: #4a4a4a !important;
            color: #ffffff !important;
        }
        div[class*="st-key-bench_filter_"] [data-baseweb="tag"] span,
        div[class*="st-key-bench_filter_"] [data-baseweb="tag"] div,
        div[class*="st-key-bench_filter_"] [data-baseweb="tag"] svg,
        div[class*="st-key-bench_filter_"] [data-baseweb="tag"] path {
            color: #ffffff !important;
            fill: #ffffff !important;
            stroke: #ffffff !important;
        }
        /* Slider track filled portion + the tiny tick "thumb" line. */
        div[class*="st-key-bench_filter_"] [data-baseweb="slider"] div[role="progressbar"],
        div[class*="st-key-bench_filter_"] div[data-testid="stSlider"] div[role="progressbar"] {
            background-color: #4a4a4a !important;
            background: #4a4a4a !important;
        }
        /* Slider thumbs (the round draggables). */
        div[class*="st-key-bench_filter_"] [role="slider"],
        div[class*="st-key-bench_filter_"] div[data-testid="stSlider"] [role="slider"] {
            background-color: #4a4a4a !important;
            border-color: #4a4a4a !important;
            color: #ffffff !important;
            box-shadow: 0 0 0 1px #4a4a4a !important;
        }
        /* Slider value bubble (the number above each thumb while dragging). */
        div[class*="st-key-bench_filter_"] [data-testid="stThumbValue"] {
            color: #4a4a4a !important;
        }
        /* Last-line defense: any remaining rgb(255, 75, 75)-ish colored
           inline backgrounds on these widgets get clobbered. */
        div[class*="st-key-bench_filter_"] [style*="rgb(255, 75, 75)"],
        div[class*="st-key-bench_filter_"] [style*="rgb(255,75,75)"],
        div[class*="st-key-bench_filter_"] [style*="#ff4b4b"],
        div[class*="st-key-bench_filter_"] [style*="#FF4B4B"] {
            background-color: #4a4a4a !important;
            border-color: #4a4a4a !important;
            color: #ffffff !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Track which save tokens we've already processed ─────────────────────
    if "bench_processed_tokens" not in st.session_state:
        st.session_state.bench_processed_tokens = set()

    # ── Load members ────────────────────────────────────────────────────────
    # Use rows_to_df() and recompute_tenure() (same path the rest of the
    # dashboard uses) so we get normalized camelCase column names — Rank,
    # FirstName, LastName, Flight, DOR, DOE, _tenant_id, _db_id, etc — and
    # computed TIG/TIS columns. The bench code below references these
    # camelCase names; reading raw Supabase rows (which use snake_case like
    # first_name, last_name, dor, doe) would silently produce empty tiles.
    try:
        if is_super:
            members_rows = get_all_members()
        else:
            tenant_id = st.session_state.get("tenant_id")
            members_rows = get_members(tenant_id) if tenant_id else []
    except Exception as e:
        st.error(f"Could not load member data: {e}")
        return

    if not members_rows:
        st.info("No member data available. Add members in Administration first.")
        return

    members_df = rows_to_df(members_rows)
    members_df = recompute_tenure(members_df)

    # Resolve _tenant_id → readable unit name using the tenants table.
    try:
        _tenants = get_all_tenants()
        _tenant_map = {t["id"]: t.get("name", "") for t in _tenants}
    except Exception:
        _tenant_map = {}
    if "_tenant_id" in members_df.columns:
        members_df["_unit_name"] = members_df["_tenant_id"].map(
            lambda tid: _tenant_map.get(tid, "") if pd.notna(tid) else ""
        )
    else:
        members_df["_unit_name"] = st.session_state.get("tenant_name") or ""

    # ── Pull latest strat data + compute PS scores ──────────────────────────
    strat_records = []
    try:
        latest = get_latest_strat_upload()
        if latest:
            db_rows = get_strat_records(latest["id"])
            strat_records = [_strat_db_row_to_record(r) for r in db_rows]
            # Tenant filter for non-super-admin
            if not is_super:
                tenant_id = st.session_state.get("tenant_id")
                if tenant_id:
                    tenants = get_all_tenants()
                    my = next((t for t in tenants if t.get("id") == tenant_id), None)
                    if my:
                        my_name = (my.get("name") or "").strip()
                        strat_records = [m for m in strat_records
                                         if (m.get("unit") or "").strip() == my_name]
    except Exception:
        pass

    score_lookup = _bench_compute_scores(members_df, strat_records)

    # ── Filter controls ─────────────────────────────────────────────────────
    sec_header("Bench Filters", tag="UNIT / FLIGHT · RANK · TIG · TIS · SCORES")

    # Canonical unit ordering — same list used by the Individual Profile and
    # Unit Overview pages. Units present in the data but NOT in this list
    # still show up at the bottom (alphabetical) so a stray tenant isn't
    # silently hidden.
    SQUADRON_UNIT_ORDER = [
        "195 WG HQ",
        "195 OG",
        "147 CBCS",
        "216 EWS",
        "261 COS",
        "195 ISRG",
        "149 IS",
        "222 CSS",
        "234 IS",
    ]

    # Available units from the loaded members, ordered: canonical units in
    # the prescribed order first, then any non-canonical ones alphabetically.
    units_in_data = {(r.get("_unit_name") or "").strip()
                     for r in members_df.to_dict("records")
                     if (r.get("_unit_name") or "").strip()}
    units_avail = [u for u in SQUADRON_UNIT_ORDER if u in units_in_data]
    units_avail += sorted(u for u in units_in_data if u not in SQUADRON_UNIT_ORDER)

    ranks_avail = [r for r in RANK_ORDER[:-1]
                   if r in {(row.get("Rank") or "").strip()
                            for row in members_df.to_dict("records")}]

    # Build cascading Unit / Flight options the same shape as the Individual
    # Profile page: "All Units", then each unit, then each unit's actual
    # flights indented underneath. Real squadrons rarely have every flight
    # populated, so we only show flights that ACTUALLY exist in the data
    # for that unit.
    def _flights_for_unit(u):
        rows = [r for r in members_df.to_dict("records")
                if (r.get("_unit_name") or "").strip() == u]
        flights = sorted({(r.get("Flight") or "").strip()
                          for r in rows
                          if (r.get("Flight") or "").strip()})
        return flights

    uf_options = [("all", None, None)]
    for unit_name in units_avail:
        uf_options.append(("unit", unit_name, None))
        for flight_name in _flights_for_unit(unit_name):
            uf_options.append(("flight", unit_name, flight_name))

    def _uf_fmt(opt):
        kind, unit_name, flight_name = opt
        if kind == "all":
            return "All Units"
        if kind == "unit":
            return unit_name
        # Two-line stacked: unit on top, indented flight beneath. The CSS
        # below renders \n as a real line break inside the selectbox.
        return f"{unit_name}\n\u00a0\u00a0\u00a0\u00a0↳ {flight_name}"

    # CSS to render the two-line option labels and to keep the cascading
    # selectbox visually consistent with the Individual Profile page.
    st.markdown("""
    <style>
    .st-key-bench_filter_unit_flight [data-baseweb="select"] *,
    .st-key-bench_filter_unit_flight [role="option"],
    .st-key-bench_filter_unit_flight [role="option"] * {
        white-space: pre-line !important;
        line-height: 1.25 !important;
    }
    .st-key-bench_filter_unit_flight [data-baseweb="select"] > div {
        min-height: 44px !important;
        height: auto !important;
        padding-top: 4px !important;
        padding-bottom: 4px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    fcol1, fcol2 = st.columns([3, 2])
    with fcol1:
        uf_sel = st.selectbox(
            "Select Unit / Flight",
            uf_options,
            format_func=_uf_fmt,
            key="bench_filter_unit_flight",
        )
    with fcol2:
        sel_ranks = st.multiselect("Rank", ranks_avail, default=ranks_avail,
                                   key="bench_filter_ranks")

    # Translate the cascade selection into per-row filter predicates that
    # the tile-build loop below already understands. "all" → no unit/flight
    # filtering. "unit" → restrict to that unit, all flights. "flight" →
    # restrict to that unit + that flight.
    uf_kind, uf_unit, uf_flight = uf_sel
    if uf_kind == "all":
        sel_units = list(units_avail)
        sel_flights = None  # None means "any flight is OK"
    elif uf_kind == "unit":
        sel_units = [uf_unit]
        sel_flights = None
    else:  # "flight"
        sel_units = [uf_unit]
        sel_flights = [uf_flight]

    rcol1, rcol2 = st.columns(2)
    with rcol1:
        tig_range = st.slider("Time in Grade (years)", 0, 30, (0, 30),
                              key="bench_filter_tig")
    with rcol2:
        tis_range = st.slider("Time in Service (years)", 0, 30, (0, 30),
                              key="bench_filter_tis")

    scol1, scol2 = st.columns(2)
    with scol1:
        strat_range = st.slider("Stratification Score", 0, 30, (0, 30),
                                key="bench_filter_strat",
                                help="Range of strat scores to include "
                                     "(MSgt/SMSgt only). Members without "
                                     "a strat score are always shown.")
    with scol2:
        ps_range = st.slider("Promotion Score", 0, _PS_MAX_TOTAL, (0, _PS_MAX_TOTAL),
                             key="bench_filter_ps",
                             help="Range of PS totals to include (SSgt+ "
                                  "only). Members without a PS total are "
                                  "always shown.")

    # ── Build tile data list, applying filters ──────────────────────────────
    tiles = []
    for row in members_df.to_dict("records"):
        rank = (row.get("Rank") or "").strip()
        unit = (row.get("_unit_name") or "").strip()
        flight = (row.get("Flight") or "").strip()
        if rank not in RANK_TIER_ORDER_DESC:
            continue
        if rank not in sel_ranks:
            continue
        if unit and unit not in sel_units:
            continue
        # sel_flights is None when no flight filter is active (e.g. when the
        # cascade is set to "All Units" or to a unit-level scope).
        if sel_flights is not None and (flight or "") not in sel_flights:
            continue

        # TIG/TIS filter
        tig_months = parse_date(row.get("DOR") or "")
        tig_months = months_since(tig_months) if tig_months else 0
        tis_months = parse_date(row.get("DOE") or "")
        tis_months = months_since(tis_months) if tis_months else 0
        tig_yrs = (tig_months or 0) // 12
        tis_yrs = (tis_months or 0) // 12
        if not (tig_range[0] <= tig_yrs <= tig_range[1]):
            continue
        if not (tis_range[0] <= tis_yrs <= tis_range[1]):
            continue

        first = (row.get("FirstName") or "").strip()
        last  = (row.get("LastName") or "").strip()
        full_name = f"{first} {last}".strip()
        dafsc = (row.get("DAFSC") or "").strip() or "—"

        scores = score_lookup.get((_bench_norm_name(full_name), rank.lower()), {})
        strat = scores.get("strat_score")
        ps    = scores.get("ps_total")

        # Score-range filter (members without a score in that bracket
        # always show — the slider only filters those WITH a score).
        if strat is not None and not (strat_range[0] <= strat <= strat_range[1]):
            continue
        if ps is not None and not (ps_range[0] <= ps <= ps_range[1]):
            continue

        tiles.append({
            "id":      row.get("_db_id"),
            "name":    full_name,
            "rank":    rank,
            "unit":    unit,
            "flight":  flight,
            "dafsc":   dafsc,
            "strat":   strat,
            "ps":      ps,
            "tig_yrs": int(tig_yrs),
            "tis_yrs": int(tis_yrs),
        })

    # ── Saved layout: scope determination ───────────────────────────────────
    # Bench is scoped to (tenant_id, flight). Super-admin always uses
    # tenant_id=None for the global "All Units" bench. For tenant users,
    # tenant_id = their tenant. Flight=None means unit-level. The
    # cascade selectbox tells us directly whether the manager is looking
    # at a flight-level scope.
    if is_super:
        bench_tenant = None
        bench_flight = None
    else:
        bench_tenant = st.session_state.get("tenant_id")
        bench_flight = uf_flight if uf_kind == "flight" else None

    saved_rows = []
    try:
        saved_rows = get_bench_layout(bench_tenant, bench_flight)
    except Exception as e:
        st.warning(f"Could not load saved bench layout: {e}")

    saved_by_member = {r["member_db_id"]: r for r in saved_rows}

    # ── Rank → row index for the pyramid ────────────────────────────────────
    # Higher rank → smaller y (closer to top). Row 0 is reserved for the
    # section header, so tiles start at row 1.
    _RANK_PRI = {r: i for i, r in enumerate(RANK_TIER_ORDER_DESC)}
    def _rank_pri(r):
        return _RANK_PRI.get(r, 99)

    SECTION_HEADER_ROW = 0
    # Each rank tier gets its own row. SMSgt sits highest.
    _RANK_ROW = {r: i + 1 for i, r in enumerate(RANK_TIER_ORDER_DESC)}
    # Minimum width of a section (in grid cells) — keeps tiny sections
    # from looking like a single lonely tile.
    SECTION_MIN_W = 4
    # Empty column between adjacent sections.
    SECTION_PAD = 1

    # ── Apply saved positions / compute auto positions ─────────────────────
    # Schema repurpose to avoid a DB migration: we store the absolute (x, y)
    # grid coords inside the existing two columns:
    #   tier_rank        → "xy:{x}:{y}" for manual placements (or "auto" otherwise)
    #   position_in_tier → unused for hierarchy view; kept = 0 for compatibility
    # Rows persisted in the OLD column-based format (e.g. tier_rank="195 OG|Bravo")
    # are silently treated as auto-placed so they migrate cleanly.
    def _parse_xy(tier_rank_str):
        """Return (x, y) tuple if tier_rank encodes 'xy:x:y', else None."""
        if not tier_rank_str:
            return None
        parts = str(tier_rank_str).split(":")
        if len(parts) == 3 and parts[0] == "xy":
            try:
                return int(parts[1]), int(parts[2])
            except ValueError:
                return None
        return None

    for t in tiles:
        s = saved_by_member.get(t["id"])
        xy = _parse_xy(s.get("tier_rank")) if s else None
        if s and s.get("manually_placed") and xy is not None:
            t["x"], t["y"] = xy
            t["manual"] = True
        else:
            t["x"], t["y"] = None, None  # filled by auto-layout below
            t["manual"] = False

    # ── Auto-layout (2D pyramid per section) ────────────────────────────────
    # Sort tiles into sections keyed by (unit, flight). Section ordering:
    # alphabetical by unit, then by flight (empty flight last so a "no-
    # flight" tile bucket doesn't sort to the front of every unit).
    sections_map = {}  # (unit, flight) → [tiles]
    for t in tiles:
        if t["manual"]:
            continue  # manual tiles get placed at saved coords below
        key = (t["unit"] or "", t["flight"] or "")
        sections_map.setdefault(key, []).append(t)

    def _section_sort_key(k):
        u, f = k
        # Canonical units first (in their prescribed order), then anything
        # else alphabetically. Within a unit, the empty-flight bucket sorts
        # last so a no-flight section doesn't slip in front of named flights.
        try:
            unit_pri = SQUADRON_UNIT_ORDER.index(u)
        except ValueError:
            unit_pri = len(SQUADRON_UNIT_ORDER) + 1  # non-canonical → after
        return (unit_pri, u.lower(), 1 if not f else 0, f.lower())
    section_keys = sorted(sections_map.keys(), key=_section_sort_key)

    # Tile auto-sort within a (section, rank) bucket: strat (MSgt/SMSgt) →
    # PS (SSgt+) → last name. Best on the left.
    def _tile_sort(t):
        rk = t.get("rank") or ""
        last = t["name"].split()[-1].lower() if t.get("name") else ""
        if rk in ("MSgt", "SMSgt") and t.get("strat") is not None:
            return (-t["strat"], last)
        if rk in ("SSgt", "TSgt", "MSgt", "SMSgt") and t.get("ps") is not None:
            return (-t["ps"], last)
        return (0, last)

    # Walk sections left-to-right. For each section, compute its width as
    # the max(rank tier population, SECTION_MIN_W). Tiles in each rank are
    # centered horizontally within the section's column band.
    section_meta = []   # list of {unit, flight, x_start, width}
    occupied = set()    # set of (x, y) cells claimed by manuals or autos
    # Pre-mark cells used by manual tiles so auto layout doesn't collide.
    for t in tiles:
        if t["manual"] and t["x"] is not None and t["y"] is not None:
            occupied.add((t["x"], t["y"]))

    next_x = 0
    for skey in section_keys:
        unit, flight = skey
        section_tiles = sections_map[skey]
        # Bucket by rank
        by_rank = {}
        for t in section_tiles:
            by_rank.setdefault(t.get("rank") or "", []).append(t)
        # Section width = max(rank-tier sizes, MIN). Round up to even so
        # centering works without half-cell offsets.
        max_rank = max((len(v) for v in by_rank.values()), default=0)
        sect_w = max(max_rank, SECTION_MIN_W)
        if sect_w % 2 == 1:
            sect_w += 1  # even width keeps the pyramid visually centered

        x_start = next_x
        section_meta.append({
            "unit":    unit,
            "flight":  flight,
            "x_start": x_start,
            "width":   sect_w,
        })

        # For each rank tier present, place its tiles centered.
        for rank, lst in by_rank.items():
            sorted_lst = sorted(lst, key=_tile_sort)
            row = _RANK_ROW.get(rank, _RANK_ROW.get("Amn", 7))
            n = len(sorted_lst)
            # First column inside the section so the cluster is centered.
            offset = (sect_w - n) // 2
            for i, t in enumerate(sorted_lst):
                col = x_start + offset + i
                # If the cell is occupied by a manual tile, hop right until
                # we find an empty one.
                while (col, row) in occupied:
                    col += 1
                t["x"], t["y"] = col, row
                occupied.add((col, row))

        next_x = x_start + sect_w + SECTION_PAD

    # Final canvas dims: columns = max occupied x + 1 (with a small right
    # buffer for room to drag tiles further). Rows = SECTION_HEADER_ROW
    # ... last rank row + a small bottom buffer.
    if occupied:
        max_x = max(c for (c, _) in occupied)
        max_y = max(r for (_, r) in occupied)
    else:
        max_x = SECTION_MIN_W - 1
        max_y = len(RANK_TIER_ORDER_DESC)
    # Also account for manual tiles that may have been dragged past the
    # auto-layout right edge.
    canvas_cols = max(max_x + 4, next_x + 2, SECTION_MIN_W * 2)
    # Rows: header (0) + rank rows (1..7) + a few extra for free-form moves.
    canvas_rows = max(max_y + 3, len(RANK_TIER_ORDER_DESC) + 2)

    # ── Unmatched strat records: in strat file but no roster member ─────────
    # The bench's source of truth is the member roster; strat scores are
    # decorative. Surface members who appear in the strat file but have no
    # matching roster row so the manager can clean up the data.
    matched_keys = set()
    for t in tiles:
        matched_keys.add((_bench_norm_name(t.get("name") or ""),
                          (t.get("rank") or "").strip().lower()))
    unmatched_strat = []
    for r in (strat_records or []):
        nm = (r.get("name") or "").strip()
        rk = (r.get("rank") or "").strip()
        if not nm or not rk:
            continue
        key = (_bench_norm_name(nm), rk.lower())
        if key in matched_keys:
            continue
        unmatched_strat.append({
            "name":   nm,
            "rank":   rk,
            "unit":   (r.get("unit") or "").strip(),
            "strat":  r.get("stratScore"),
            "submit": (r.get("submitStrat") or "").strip().upper(),
        })
    # Sort unmatched: highest strat first, blanks last, then by rank then name.
    unmatched_strat.sort(key=lambda u: (
        0 if u["strat"] is not None else 1,
        -(u["strat"] or 0),
        _rank_pri(u["rank"]),
        u["name"].lower(),
    ))

    # ── Compute new-member flags from latest-vs-prior strat upload ──────────
    # Use the same normalized key shape as the score lookup so the iframe's
    # roster-name → strat-name matching agrees with what _tile_html checks.
    new_keys = set()
    try:
        all_uploads = list_strat_uploads(limit=3)
        if len(all_uploads) >= 2:
            latest_records = get_strat_records(all_uploads[0]["id"])
            prior_records  = get_strat_records(all_uploads[1]["id"])
            latest_keys = {(_bench_norm_name(r.get("name") or ""),
                            (r.get("rank") or "").strip().lower())
                           for r in latest_records}
            prior_keys  = {(_bench_norm_name(r.get("name") or ""),
                            (r.get("rank") or "").strip().lower())
                           for r in prior_records}
            new_keys = latest_keys - prior_keys
    except Exception:
        pass

    # ── Save / Reset / Mode controls ────────────────────────────────────────
    sec_header("Bench Layout", tag="DRAG TO REARRANGE · MANAGER VIEW")
    last_modified_at, last_modified_by = (None, None)
    try:
        last_modified_at, last_modified_by = get_bench_last_modified(
            bench_tenant, bench_flight)
    except Exception:
        pass

    last_mod_label = "Never saved"
    if last_modified_at:
        ts = last_modified_at[:16].replace("T", " ")
        who = ""
        if last_modified_by:
            try:
                u = get_user_by_id(last_modified_by)
                who = u.get("username", "") if u else ""
            except Exception:
                pass
            who = f" by {who}" if who else ""
        last_mod_label = f"Last saved: {ts}{who}"

    reset_col, mode_col, status_col = st.columns([1, 1, 4])
    with reset_col:
        reset_clicked = st.button("↺ Reset to auto", disabled=not can_save,
                                  use_container_width=True,
                                  help="Wipe saved positions and revert to auto-placement")
    with mode_col:
        read_only = st.toggle("Read-only view", value=False, key="bench_read_only",
                              help="Disables drag — useful for presenting to leadership")
    with status_col:
        st.markdown(
            f'<div style="font-family:Barlow Condensed,sans-serif;font-size:12px;'
            f'letter-spacing:1px;text-transform:uppercase;color:#9dc4db;'
            f'padding:14px 0 0 0;">{last_mod_label}</div>',
            unsafe_allow_html=True,
        )

    # ── Handle Reset action ────────────────────────────────────────────────
    if reset_clicked and can_save:
        try:
            reset_bench_layout(bench_tenant, bench_flight)
            st.success("Bench layout reset to auto-placement.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not reset layout: {e}")

    # ── localStorage save signal handler ────────────────────────────────────
    # The iframe Save button writes the layout JSON to localStorage and sets
    # a signal key. We poll that signal on each rerun via streamlit_javascript
    # (which runs OUTSIDE the iframe so it can read the same-origin localStorage
    # the iframe wrote to). When we see a fresh token (one we haven't already
    # processed in this session), we read the JSON and persist it.
    #
    # IMPORTANT: After processing (or detecting an already-processed token),
    # we ALWAYS clear localStorage — leaving a stale signal there causes the
    # st_javascript poll to keep returning a non-empty value on every rerun,
    # which can manifest as a perceived "reload loop" / white-screen latency
    # whenever the user lands back on the bench tab.
    _signal = None
    try:
        _signal = st_javascript(
            "JSON.stringify({"
            " token: localStorage.getItem('bench_save_signal') || '', "
            " tenant: localStorage.getItem('bench_save_tenant') || '', "
            " flight: localStorage.getItem('bench_save_flight') || '' "
            "})",
            key="bench_save_signal_poll",
        )
    except Exception:
        _signal = None

    _signal_data = None
    if isinstance(_signal, str) and _signal.startswith("{"):
        try:
            _signal_data = _json.loads(_signal)
        except Exception:
            _signal_data = None

    _have_signal = bool(_signal_data and _signal_data.get("token"))
    _is_fresh    = (_have_signal
                    and _signal_data["token"] not in st.session_state.bench_processed_tokens)

    # Path 1: a brand-new save signal we haven't processed yet.
    if _is_fresh:
        if not can_save:
            st.error("Save denied — your role isn't permitted to save the bench.")
            st.session_state.bench_processed_tokens.add(_signal_data["token"])
        else:
            # Read the actual payload from localStorage.
            try:
                _payload_str = st_javascript(
                    "localStorage.getItem('bench_save_payload') || ''",
                    key="bench_save_payload_read",
                )
            except Exception:
                _payload_str = ""

            if isinstance(_payload_str, str) and _payload_str:
                try:
                    payload = _json.loads(_payload_str)
                except Exception as _ex:
                    payload = None
                    st.error(f"Could not parse saved layout: {_ex}")

                if payload is not None:
                    _t_raw = _signal_data.get("tenant", "")
                    _f_raw = _signal_data.get("flight", "")
                    _save_tenant = (int(_t_raw)
                                    if _t_raw not in ("", "null", None) else None)
                    _save_flight = (_f_raw
                                    if _f_raw not in ("", "null", None) else None)

                    rows_to_save = []
                    for entry in payload:
                        if not isinstance(entry, dict):
                            continue
                        mid = entry.get("member_db_id")
                        if mid is None:
                            continue
                        rows_to_save.append({
                            "member_db_id":     int(mid),
                            "tier_rank":        str(entry.get("tier_rank", "")),
                            "position_in_tier": int(entry.get("position_in_tier", 0)),
                            "manually_placed":  True,
                        })
                    try:
                        save_bench_layout(_save_tenant, _save_flight,
                                          rows_to_save, user_id)
                        st.success(f"Saved bench layout ({len(rows_to_save)} tiles).")
                        st.session_state.bench_processed_tokens.add(_signal_data["token"])
                        # NOTE: we deliberately do NOT call st.rerun() here.
                        # The hard reload from the iframe already brought us
                        # to a clean render; calling rerun would stack a
                        # second render on top and contribute to the
                        # perceived "loop" the user sees on the page.
                    except Exception as e:
                        st.error(f"Could not save layout: {e}")

    # Path 2: ALWAYS clear localStorage if any signal is present, whether
    # we just processed it or it was already in our processed set. This is
    # the loop-killer — without it the poll keeps re-reading the same stale
    # token forever and the page seems to "reload" constantly.
    if _have_signal:
        try:
            st_javascript(
                "(function(){"
                " localStorage.removeItem('bench_save_signal'); "
                " localStorage.removeItem('bench_save_payload'); "
                " localStorage.removeItem('bench_save_tenant'); "
                " localStorage.removeItem('bench_save_flight'); "
                " return 'cleared'; "
                "})()",
                key="bench_save_clear_always",
            )
        except Exception:
            pass

    # ── Render the bench iframe ─────────────────────────────────────────────
    # The iframe's "💾 Save layout" button writes the layout JSON to
    # localStorage and sets a signal key. The localStorage poll above
    # picks it up on the next rerun and persists.
    _render_bench_iframe(
        tiles, section_meta, canvas_cols, canvas_rows,
        new_keys, unmatched_strat,
        read_only=read_only,
        can_save=can_save,
        bench_tenant=bench_tenant,
        bench_flight=bench_flight,
    )


def _render_bench_iframe(tiles, section_meta, canvas_cols, canvas_rows,
                         new_member_keys, unmatched_strat,
                         read_only=False, can_save=False,
                         bench_tenant=None, bench_flight=None):
    """Render the 2D pyramid bench in a sandboxed iframe.

    Layout: a single CSS-Grid canvas where every member tile occupies one
    cell at an absolute (x, y) coordinate. Default arrangement is a unit /
    flight / rank pyramid — sections flow left-to-right; within each
    section the rank tiers stack top-down with higher ranks at the top
    and tiles centered horizontally inside the section's column band.

    Drag-and-drop is HTML5 native: tiles snap to the cell under the
    cursor on drop. If the target cell is occupied, the two tiles swap
    so a manager never accidentally erases or stacks a placement. Sections
    are visually grouped via a header row at y=0 and a faint background
    stripe behind each band — purely cosmetic; the canvas itself is one
    contiguous grid so tiles can be dragged anywhere.

    Tile visuals: white interior body, dark blue header (unit · flight
    on each tile), blue strat chip bottom-left when the member is matched
    against the latest strat upload, green PS chip bottom-right for SSgt+.

    Right-side "Not in database" panel lists strat-only members (in the
    upload, no matching roster entry) so the manager can fix the data.

    Save flow: clicking "💾 Save layout" in the iframe writes the layout
    JSON (one row per tile with member_db_id + x + y) to localStorage; the
    Streamlit-side poll persists it. The DB columns are reused without a
    schema migration: tier_rank stores "xy:{x}:{y}" and position_in_tier
    is unused (always 0). Old column-format saves are silently ignored.

    `new_member_keys` is a set of (norm_name, lower(rank)) for tiles that
    should display the gold "NEW" pill.
    """
    import json as _json
    import html as _html
    import uuid as _uuid

    CELL_W = 160  # pixels per grid column — wide enough that "SMSgt
                  # LastName" fits on one line for nearly all real names
                  # without truncation. Single-line layout means the tile
                  # height is always exactly CELL_H, which keeps every
                  # cell in a row visually aligned (CSS Grid would otherwise
                  # let a single tall tile push every neighbor's height
                  # out of alignment).
    CELL_H = 96   # pixels per grid row — fixed height. Tall enough to
                  # accommodate a 2-line section header (e.g. "195 WG HQ ·
                  # COMMAND SECTION" wrapping after the dot) plus the body
                  # and score footer. The CSS uses `repeat(N, minmax(0,
                  # CELL_H))` so even if a tile's content overflows it will
                  # be clipped, not cause its row to grow.
    HEADER_H = 30 # pixels for the section-header strip at row 0

    # ── Per-tile HTML ──────────────────────────────────────────────────────
    def _tile_html(t):
        is_new = ((_bench_norm_name(t.get("name") or ""),
                   (t.get("rank") or "").strip().lower()) in new_member_keys)
        new_pill = '<span class="bench-new-pill">NEW</span>' if is_new else ""
        unit = _html.escape(t.get("unit") or "")
        flight = _html.escape(t.get("flight") or "")
        # Render the blue tile header as two explicit lines: unit on top,
        # flight underneath. Always emit both lines (using a non-breaking
        # space when there's no flight) so every tile's blue strip is the
        # same height — natural wrap was causing visually-uneven tiles
        # because some labels fit on one line and others wrapped.
        header_html = (
            f'<div class="bench-tile-header">'
            f'<div class="bench-tile-header-line">{unit or "&nbsp;"}</div>'
            f'<div class="bench-tile-header-line">{flight or "&nbsp;"}</div>'
            f'</div>'
        )
        rank = _html.escape(t.get("rank") or "")
        name = _html.escape(t.get("name") or "")
        dafsc = _html.escape(t.get("dafsc") or "—")
        strat = t.get("strat")
        ps    = t.get("ps")
        rk = (t.get("rank") or "").strip()
        ps_eligible = rk in ("SSgt", "TSgt", "MSgt", "SMSgt")
        # Both scores render as whole integers (no decimals). Strat scores
        # come from the rubric upload and are usually integers but can be
        # floats (e.g. 28.0); PS totals are always integers but we cast
        # defensively.
        def _whole(v):
            try:
                return str(int(round(float(v))))
            except (TypeError, ValueError):
                return ""
        strat_html = (f'<div class="bench-tile-score strat">S {_whole(strat)}</div>'
                      if strat is not None else
                      '<div class="bench-tile-score blank"></div>')
        if ps_eligible:
            ps_str = _whole(ps) if ps is not None else "0"
            ps_html = f'<div class="bench-tile-score ps">P {ps_str}</div>'
        else:
            ps_html = '<div class="bench-tile-score blank"></div>'
        draggable = "false" if read_only else "true"
        # Tile cell in CSS grid coords: tile.y=1 corresponds to grid-row=2
        # (row 1 is the section-header strip). General: grid-row = y + 1.
        x = int(t.get("x") or 0)
        y = int(t.get("y") or 1)
        return (
            f'<div class="bench-tile" draggable="{draggable}" '
            f'data-id="{t.get("id")}" data-name="{name}" data-rank="{rank}" '
            f'data-x="{x}" data-y="{y}" '
            f'style="grid-column: {x + 1} / span 1; grid-row: {y + 1} / span 1;">'
            f'{header_html}'
            f'<div class="bench-tile-body">'
            f'<div class="bench-tile-rank-name">{rank} {name} {new_pill}</div>'
            f'<div class="bench-tile-dafsc">{dafsc}</div>'
            f'</div>'
            f'<div class="bench-tile-footer">{strat_html}{ps_html}</div>'
            f'</div>'
        )

    # ── Section header strips (CSS grid-row 1) ─────────────────────────────
    # Each (unit, flight) section gets a labeled bar that spans its column
    # band. We also drop a faint background stripe behind each section so
    # the bands are visible even after the manager drags people around.
    sections_html = ""
    for s in section_meta:
        unit = _html.escape(s["unit"] or "—")
        flight = _html.escape(s["flight"] or "")
        sep = " · " if s["flight"] else ""
        x_start = s["x_start"]
        width = s["width"]
        sections_html += (
            f'<div class="bench-section-header" '
            f'style="grid-column: {x_start + 1} / span {width}; '
            f'grid-row: 1 / span 1;">'
            f'<span class="bench-section-unit">{unit}</span>'
            f'<span class="bench-section-sep">{sep}</span>'
            f'<span class="bench-section-flight">{flight}</span>'
            f'</div>'
        )
        sections_html += (
            f'<div class="bench-section-stripe" '
            f'style="grid-column: {x_start + 1} / span {width}; '
            f'grid-row: 2 / span {canvas_rows - 1};"></div>'
        )

    tiles_html = "".join(_tile_html(t) for t in tiles)

    # ── Build "Not in database" side panel ─────────────────────────────────
    if unmatched_strat:
        items = []
        for u in unmatched_strat:
            nm = _html.escape(u.get("name") or "")
            rk = _html.escape(u.get("rank") or "")
            un = _html.escape(u.get("unit") or "—")
            sc = u.get("strat")
            sub = (u.get("submit") or "").upper()
            # Whole integer, no decimal — match the bench tile formatting.
            try:
                sc_disp = str(int(round(float(sc)))) if sc is not None else None
            except (TypeError, ValueError):
                sc_disp = None
            sc_html = (f'<span class="bench-orphan-score">S {sc_disp}</span>'
                       if sc_disp is not None else
                       '<span class="bench-orphan-score blank">—</span>')
            sub_html = (
                '<span class="bench-orphan-sub yes">SUBMITTED</span>'
                if sub == "YES" else
                '<span class="bench-orphan-sub no">NOT SUB</span>'
                if sub == "NO" else ""
            )
            items.append(
                f'<div class="bench-orphan-row">'
                f'<div class="bench-orphan-name">{rk} {nm}</div>'
                f'<div class="bench-orphan-meta">{un}</div>'
                f'<div class="bench-orphan-footer">{sc_html}{sub_html}</div>'
                f'</div>'
            )
        orphan_count = len(unmatched_strat)
        orphans_html = (
            f'<div class="bench-orphan-panel">'
            f'<div class="bench-orphan-header">'
            f'<span class="bench-orphan-title">Not in database</span>'
            f'<span class="bench-orphan-count">{orphan_count}</span>'
            f'</div>'
            f'<div class="bench-orphan-help">'
            f'In strat file but no matching member. Add them in '
            f'Administration to place them on the bench.'
            f'</div>'
            + "".join(items)
            + '</div>'
        )
    else:
        orphans_html = ""

    iframe_id = "bench_" + _uuid.uuid4().hex[:8]
    canvas_height = HEADER_H + (canvas_rows - 1) * CELL_H
    iframe_height = max(420, canvas_height + 200,
                        140 + max(0, len(unmatched_strat or [])) * 60)

    # Encode the Python-side values that the JS needs for the save handshake
    # and grid math.
    _bt_str = "" if bench_tenant is None else str(int(bench_tenant))
    _bf_str = "" if bench_flight is None else str(bench_flight)
    _can_save_js = "true" if (can_save and not read_only) else "false"
    _grid_dims_js = (f'var CELL_W={CELL_W}; var CELL_H={CELL_H}; '
                     f'var HEADER_H={HEADER_H}; '
                     f'var CANVAS_COLS={canvas_cols}; '
                     f'var CANVAS_ROWS={canvas_rows};')

    bench_html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  html, body {
    margin: 0; padding: 0; background: transparent;
    font-family: 'Barlow', sans-serif; color: #1f2a44;
  }
  .bench-container {
    background: #f4f5f7; border: 1px solid #d4d8e0;
    border-radius: 8px; padding: 16px; min-height: 200px;
  }
  .bench-toolbar {
    display: flex; align-items: center; gap: 12px;
    padding: 0 0 12px 0;
    margin-bottom: 12px;
    border-bottom: 1px solid #d4d8e0;
  }
  .bench-save-btn {
    background: #1a2a5e; color: #ffffff;
    border: 1px solid #14224a; border-radius: 4px;
    padding: 6px 16px; cursor: pointer;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 13px; font-weight: 700;
    letter-spacing: 1px; text-transform: uppercase;
    transition: background 0.15s, transform 0.1s;
  }
  .bench-save-btn:hover:not(:disabled) {
    background: #243a7e; transform: translateY(-1px);
  }
  .bench-save-btn:active:not(:disabled) { transform: translateY(0); }
  .bench-save-btn:disabled {
    background: #b8bdc9; color: #6a7080; border-color: #a0a6b3;
    cursor: not-allowed;
  }
  .bench-dirty-indicator {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 11px; letter-spacing: 1px; text-transform: uppercase;
    color: #c98a00; opacity: 0;
    transition: opacity 0.2s;
  }
  .bench-dirty-indicator.is-dirty { opacity: 1; }
  .bench-toolbar-help {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 11px; letter-spacing: 1px; text-transform: uppercase;
    color: #6a7080; margin-left: auto;
  }
  /* Two-pane layout: canvas on the left (scrolls), orphan panel on right. */
  .bench-layout {
    display: flex; gap: 16px; align-items: flex-start;
  }
  /* Canvas wrapper — scroll container for the 2D grid. */
  .bench-canvas-wrap {
    flex: 1; overflow-x: auto; overflow-y: auto;
    background: #ffffff;
    border: 1px solid #d4d8e0; border-radius: 6px;
    padding: 8px;
    /* Workbench texture: subtle grid lines so the manager can see snap
       cells while dragging. They brighten when a drag is in progress. */
    background-image:
      linear-gradient(to right, rgba(26,42,94,0.04) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(26,42,94,0.04) 1px, transparent 1px);
    background-size: __CELL_W__px __CELL_H__px;
    background-position: 8px __HEADER_OFFSET__px;
  }
  .bench-canvas-wrap.is-dragging {
    background-image:
      linear-gradient(to right, rgba(26,42,94,0.18) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(26,42,94,0.18) 1px, transparent 1px);
  }
  /* The grid itself. Row 1 = section-header band (shorter); rows 2..N
     hold the rank-tier rows.

     Note the `minmax(0, ...)` wrappers — CSS Grid by default treats a
     bare pixel value as a MINIMUM track size, so any cell whose content
     overflows would push the entire row taller and break the alignment
     of neighbor cells. minmax(0, X) forces the track to NEVER exceed
     X pixels regardless of content. Combined with `overflow: hidden`
     on the tile and section-header rules, content that doesn't fit is
     simply clipped — keeping the grid uniform. */
  .bench-canvas {
    display: grid;
    grid-template-columns: repeat(__CANVAS_COLS__, minmax(0, __CELL_W__px));
    grid-template-rows: minmax(0, __HEADER_H__px) repeat(__RANK_ROWS__, minmax(0, __CELL_H__px));
    position: relative;
    min-width: max-content;
  }
  /* Section header pills — one per (unit, flight) column band. */
  .bench-section-header {
    background: #1a2a5e; color: #ffffff;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 12px; font-weight: 700;
    letter-spacing: 1px; text-transform: uppercase;
    display: flex; align-items: center; justify-content: center;
    border-bottom: 2px solid #f0c030;
    border-radius: 4px 4px 0 0;
    margin: 0 1px;
    overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
    z-index: 2;
  }
  .bench-section-unit { color: #ffffff; }
  .bench-section-sep  { color: #9dc4db; margin: 0 4px; }
  .bench-section-flight { color: #f0c030; }
  /* Faint background stripe behind each section's column band so even
     after manual drags the section's territory is still visible. */
  .bench-section-stripe {
    background: rgba(26, 42, 94, 0.03);
    border-left: 1px solid rgba(26,42,94,0.07);
    border-right: 1px solid rgba(26,42,94,0.07);
    margin: 0 1px;
    z-index: 0;
    pointer-events: none;
  }
  /* Tile sits in its (x, y) cell. White interior, blue header. */
  .bench-tile {
    background: #ffffff;
    border: 1px solid #c8cfdb; border-radius: 6px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    display: flex; flex-direction: column;
    cursor: grab; user-select: none;
    transition: transform 0.12s, box-shadow 0.12s, border-color 0.12s;
    margin: 2px;
    overflow: hidden;
    z-index: 1;
  }
  .bench-tile[draggable="false"] { cursor: default; }
  .bench-tile:hover {
    transform: translateY(-1px);
    box-shadow: 0 3px 8px rgba(0,0,0,0.10);
    border-color: #1a2a5e;
  }
  .bench-tile.dragging { opacity: 0.4; cursor: grabbing; z-index: 5; }
  .bench-tile.drop-target { box-shadow: 0 0 0 2px #f0c030; }
  .bench-tile-header {
    background: #1a2a5e; color: #9dc4db;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 9px; font-weight: 700;
    letter-spacing: 0.5px; text-transform: uppercase;
    padding: 3px 6px;
    border-radius: 5px 5px 0 0;
    border-bottom: 1px solid #f0c030;
    text-align: center;
    line-height: 1.15;
    flex: 0 0 auto;
    /* Header is always exactly two lines tall (unit on line 1, flight on
       line 2) — no natural wrapping. This guarantees every tile has the
       same blue strip height, so the grid stays uniform whether or not
       the labels happen to be long. Each line truncates with ellipsis if
       it doesn't fit; doesn't expand the strip. */
    display: flex; flex-direction: column;
    overflow: hidden;
  }
  .bench-tile-header-line {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .bench-tile-header-line:first-child { color: #ffffff; }
  .bench-tile-header-line:last-child  { color: #f0c030; }
  .bench-tile-body {
    /* Fixed body height — body content (rank+name, DAFSC) sits inside a
       known box; overflow is clipped with ellipsis so a long name never
       blows out the cell height and pushes neighbors around. */
    flex: 1 1 auto;
    padding: 3px 6px 2px 6px;
    background: #ffffff;
    overflow: hidden;
    min-height: 0;
  }
  .bench-tile-rank-name {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 12px; font-weight: 700; color: #1a2a5e;
    line-height: 1.1;
    /* Single line + ellipsis. Wrapping was previously enabled to "show
       the full name" but it stretched some cells past CELL_H and made
       the grid look ragged. CELL_W has been bumped up so most real
       SNCO names fit; for unusually long ones, the truncation is
       visible (ellipsis) — better than a misaligned grid. */
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .bench-tile-dafsc {
    font-family: 'Barlow', sans-serif;
    font-size: 10px; color: #6a7080;
    font-variant-numeric: tabular-nums;
    overflow: hidden; text-overflow: ellipsis;
    white-space: nowrap;
    line-height: 1.1;
  }
  .bench-tile-footer {
    /* Sticks to the bottom edge via margin-top: auto. The body is no
       longer flexing, so without this the footer would sit immediately
       under the body — using auto-margin keeps the chips at the bottom
       of the tile while leaving content tight at the top. */
    display: flex; justify-content: space-between;
    padding: 3px 5px;
    background: #ffffff;
    border-top: 1px solid #eef0f4;
    border-radius: 0 0 5px 5px;
    margin-top: auto;
    flex: 0 0 auto;
  }
  .bench-tile-score {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 10px; font-weight: 700;
    padding: 1px 5px; border-radius: 3px;
    min-width: 30px; text-align: center;
  }
  /* Strat → blue chip, bottom-left. PS → green chip, bottom-right. */
  .bench-tile-score.strat { background: #1a2a5e; color: #ffffff; }
  .bench-tile-score.ps    { background: #22c55e; color: #ffffff; }
  .bench-tile-score.blank { background: transparent; }
  .bench-new-pill {
    display: inline-block;
    margin-left: 3px;
    padding: 0 4px;
    background: #f0c030;
    color: #1a2a5e;
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 1px;
    border-radius: 2px;
    vertical-align: middle;
  }
  /* Right-side "Not in database" panel. */
  .bench-orphan-panel {
    flex: 0 0 260px; width: 260px;
    background: #fff8e6;
    border: 1px solid #f0c030;
    border-radius: 6px;
    padding: 10px;
    max-height: 70vh; overflow-y: auto;
  }
  .bench-orphan-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 4px;
  }
  .bench-orphan-title {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 13px; font-weight: 700;
    letter-spacing: 1px; text-transform: uppercase;
    color: #8a6500;
  }
  .bench-orphan-count {
    background: #f0c030; color: #1a2a5e;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 11px; font-weight: 700;
    padding: 1px 8px; border-radius: 10px;
  }
  .bench-orphan-help {
    font-size: 11px; color: #8a6500;
    line-height: 1.3; margin-bottom: 8px;
  }
  .bench-orphan-row {
    background: #ffffff;
    border: 1px solid #f0d680; border-radius: 4px;
    padding: 5px 8px; margin-bottom: 5px;
  }
  .bench-orphan-name {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 13px; font-weight: 700; color: #1a2a5e;
    line-height: 1.15;
  }
  .bench-orphan-meta {
    font-size: 10px; color: #6a7080; margin-bottom: 2px;
  }
  .bench-orphan-footer {
    display: flex; gap: 6px; align-items: center;
  }
  .bench-orphan-score {
    background: #1a2a5e; color: #ffffff;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 10px; font-weight: 700;
    padding: 1px 6px; border-radius: 3px;
  }
  .bench-orphan-score.blank { background: transparent; color: #9aa1b0; }
  .bench-orphan-sub {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 9px; font-weight: 700;
    padding: 1px 5px; border-radius: 3px;
    letter-spacing: 0.5px;
  }
  .bench-orphan-sub.yes { background: #22c55e; color: #ffffff; }
  .bench-orphan-sub.no  { background: #b8bdc9; color: #ffffff; }
</style></head>
<body>
<div class="bench-container">
  <div class="bench-toolbar">
    <button type="button" class="bench-save-btn" id="benchSaveBtn"
            __SAVE_DISABLED__>💾 Save layout</button>
    <span class="bench-dirty-indicator" id="benchDirty">● unsaved changes</span>
    <span class="bench-toolbar-help">__HELP_TEXT__</span>
  </div>
  <div class="bench-layout">
    <div class="bench-canvas-wrap" id="benchCanvasWrap">
      <div class="bench-canvas" id="benchCanvas">
        __SECTIONS__
        __TILES__
      </div>
    </div>
    __ORPHANS__
  </div>
</div>
<script>
(function() {
  __GRID_DIMS__
  var draggedTile = null;
  var canSave = __CAN_SAVE_JS__;
  var benchTenant = "__BENCH_TENANT__";
  var benchFlight = "__BENCH_FLIGHT__";
  var isDirty = false;
  var canvas = document.getElementById("benchCanvas");
  var canvasWrap = document.getElementById("benchCanvasWrap");
  var saveBtn = document.getElementById("benchSaveBtn");
  var dirtyEl = document.getElementById("benchDirty");

  function markDirty() {
    isDirty = true;
    if (dirtyEl) dirtyEl.classList.add("is-dirty");
    attachUnloadGuard();
  }

  // Cursor (clientX, clientY) → (col, row) cell in the grid. Y has to
  // account for the shorter section-header strip at row 1.
  function cursorToCell(clientX, clientY) {
    var rect = canvas.getBoundingClientRect();
    var localX = clientX - rect.left;
    var localY = clientY - rect.top;
    var col = Math.floor(localX / CELL_W);
    if (col < 0) col = 0;
    if (col >= CANVAS_COLS) col = CANVAS_COLS - 1;
    var row;
    if (localY < HEADER_H) {
      row = 1;  // dropping ON the header strip is treated as the top rank row
    } else {
      row = 1 + Math.floor((localY - HEADER_H) / CELL_H);
    }
    if (row < 1) row = 1;
    if (row >= CANVAS_ROWS) row = CANVAS_ROWS - 1;
    return [col, row];
  }

  function tileAt(x, y) {
    var sel = ".bench-tile[data-x=\\"" + x + "\\"][data-y=\\"" + y + "\\"]";
    return canvas.querySelector(sel);
  }

  function moveTileTo(tile, x, y) {
    tile.setAttribute("data-x", String(x));
    tile.setAttribute("data-y", String(y));
    tile.style.gridColumn = (x + 1) + " / span 1";
    tile.style.gridRow = (y + 1) + " / span 1";
  }

  // Wire drag events for every tile.
  document.querySelectorAll(".bench-tile").forEach(function(tile) {
    tile.addEventListener("dragstart", function(e) {
      if (tile.getAttribute("draggable") === "false") {
        e.preventDefault(); return;
      }
      draggedTile = tile;
      tile.classList.add("dragging");
      canvasWrap.classList.add("is-dragging");
      e.dataTransfer.effectAllowed = "move";
      try { e.dataTransfer.setData("text/plain", tile.getAttribute("data-id")); } catch(_) {}
    });
    tile.addEventListener("dragend", function() {
      tile.classList.remove("dragging");
      canvasWrap.classList.remove("is-dragging");
      document.querySelectorAll(".bench-tile.drop-target").forEach(function(t){
        t.classList.remove("drop-target");
      });
      draggedTile = null;
    });
  });

  // The whole canvas is the drop zone — we compute the dest cell from
  // the cursor and snap. Swap on collision.
  if (canvas) {
    canvas.addEventListener("dragover", function(e) {
      if (!draggedTile) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      document.querySelectorAll(".bench-tile.drop-target").forEach(function(t){
        t.classList.remove("drop-target");
      });
      var cell = cursorToCell(e.clientX, e.clientY);
      var existing = tileAt(cell[0], cell[1]);
      if (existing && existing !== draggedTile) {
        existing.classList.add("drop-target");
      }
    });
    canvas.addEventListener("dragleave", function(e) {
      if (!canvas.contains(e.relatedTarget)) {
        document.querySelectorAll(".bench-tile.drop-target").forEach(function(t){
          t.classList.remove("drop-target");
        });
      }
    });
    canvas.addEventListener("drop", function(e) {
      e.preventDefault();
      if (!draggedTile) return;
      document.querySelectorAll(".bench-tile.drop-target").forEach(function(t){
        t.classList.remove("drop-target");
      });
      var cell = cursorToCell(e.clientX, e.clientY);
      var newX = cell[0], newY = cell[1];
      var oldX = parseInt(draggedTile.getAttribute("data-x"), 10);
      var oldY = parseInt(draggedTile.getAttribute("data-y"), 10);
      if (newX === oldX && newY === oldY) return;
      var occupant = tileAt(newX, newY);
      if (occupant && occupant !== draggedTile) {
        // Swap: occupant takes the dragged tile's old cell.
        moveTileTo(occupant, oldX, oldY);
      }
      moveTileTo(draggedTile, newX, newY);
      markDirty();
    });
  }

  // Gather positions into a JSON payload. Each row: db_id + x + y.
  // The Python handler stores tier_rank="xy:{x}:{y}" and position=0 to
  // reuse the existing schema columns.
  function collectLayout() {
    var payload = [];
    document.querySelectorAll(".bench-tile").forEach(function(tile) {
      var mid = tile.getAttribute("data-id");
      if (mid === "" || mid === "None" || mid === null) return;
      var x = parseInt(tile.getAttribute("data-x"), 10);
      var y = parseInt(tile.getAttribute("data-y"), 10);
      payload.push({
        member_db_id: parseInt(mid, 10),
        tier_rank: "xy:" + x + ":" + y,
        position_in_tier: 0
      });
    });
    return payload;
  }

  if (saveBtn && canSave) {
    saveBtn.addEventListener("click", function() {
      var payload = collectLayout();
      var json = JSON.stringify(payload);
      var token = Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
      try {
        localStorage.setItem("bench_save_payload", json);
        localStorage.setItem("bench_save_tenant", benchTenant || "");
        localStorage.setItem("bench_save_flight", benchFlight || "");
        localStorage.setItem("bench_save_signal", token);
        isDirty = false;
        if (dirtyEl) dirtyEl.classList.remove("is-dirty");
        detachUnloadGuard();
        // Show an in-iframe confirmation rather than reloading the parent.
        // The earlier `window.top.location.reload()` produced a white-flash
        // and a perceived "reload loop" — replacing it with a soft visual
        // confirmation eliminates both. The Python-side poll picks up the
        // localStorage signal on the very next Streamlit rerun (any user
        // click anywhere on the page), so the save IS persisted to the DB
        // — just deferred until the next interaction. The localStorage
        // payload survives a manual page refresh too, so even closing and
        // reopening the tab still completes the save.
        if (saveBtn) {
          var origLabel = saveBtn.innerHTML;
          saveBtn.innerHTML = "✓ Saved \u2014 syncing on next interaction";
          saveBtn.disabled = true;
          setTimeout(function() {
            saveBtn.innerHTML = origLabel;
            saveBtn.disabled = false;
          }, 2200);
        }
      } catch (err) {
        alert("Could not write layout to local storage. The browser may " +
              "be in a private/incognito mode that blocks storage. " +
              "Error: " + err);
      }
    });
  }

  // Lazy beforeunload handler. Attaching this on page load makes Chrome
  // fire the "Leave site? Changes you made may not be saved" popup on
  // EVERY Streamlit rerun (including the org-dropdown change, which
  // triggers a soft URL nav). Instead, attach the handler only when the
  // user has actually dragged something, and remove it on save.
  function beforeUnloadHandler(e) {
    if (isDirty && canSave) {
      e.preventDefault();
      e.returnValue = "";
    }
  }
  function attachUnloadGuard() {
    window.addEventListener("beforeunload", beforeUnloadHandler);
  }
  function detachUnloadGuard() {
    window.removeEventListener("beforeunload", beforeUnloadHandler);
  }
})();
</script>
</body></html>
"""
    if read_only:
        _help_text = "Read-only mode — drag and save are disabled"
        _save_disabled = "disabled"
    elif not can_save:
        _help_text = "Save requires super-admin, Commander, or SEL role"
        _save_disabled = "disabled"
    else:
        _help_text = ("Drag tiles anywhere on the workbench · "
                      "drop on another tile to swap · click Save to persist")
        _save_disabled = ""

    bench_html = (bench_html
                  .replace("__SECTIONS__", sections_html)
                  .replace("__TILES__", tiles_html)
                  .replace("__ORPHANS__", orphans_html)
                  .replace("__SAVE_DISABLED__", _save_disabled)
                  .replace("__HELP_TEXT__", _html.escape(_help_text))
                  .replace("__GRID_DIMS__", _grid_dims_js)
                  .replace("__CELL_W__", str(CELL_W))
                  .replace("__CELL_H__", str(CELL_H))
                  .replace("__HEADER_H__", str(HEADER_H))
                  .replace("__HEADER_OFFSET__", str(HEADER_H + 8))
                  .replace("__CANVAS_COLS__", str(canvas_cols))
                  .replace("__RANK_ROWS__", str(canvas_rows - 1))
                  .replace("__CAN_SAVE_JS__", _can_save_js)
                  .replace("__BENCH_TENANT__", _html.escape(_bt_str))
                  .replace("__BENCH_FLIGHT__", _html.escape(_bf_str)))
    _components.html(bench_html, height=iframe_height, scrolling=True)

    if read_only:
        st.caption("Read-only mode — drag is disabled. Toggle off to rearrange.")


def page_force_development():
    """Force Development page — three tabs: SNCO Stratification (Microsoft
    Forms upload + analysis), Promotion Scorecard (per-member scorecard
    rollups), and Enlisted Bench (drag-and-drop org chart for talent
    management)."""

    tab_strat, tab_score, tab_bench = st.tabs(
        ["SNCO Stratification", "Promotion Scorecard", "Enlisted Bench"]
    )
    with tab_strat:
        _render_snco_stratification_tab()
    with tab_score:
        _render_promotion_scorecard_tab()
    with tab_bench:
        _render_enlisted_bench_tab()


# ── Entry point ───────────────────────────────────────────────────────────────
def render_org_bar():
    """Org bar is rendered as fixed HTML in app.py. Nothing to do here."""
    pass



def run():
    render_org_bar()

    df = load_data()
    df["FullName"]     = df["Rank"] + " " + df["FirstName"].fillna("") + " " + df["LastName"].fillna("")
    df["TIGMonthsNum"] = df["DOR"].apply(parse_date).apply(months_since)
    df["TISMonthsNum"] = df["DOE"].apply(parse_date).apply(months_since)

    page = st.session_state.page

    if page == "Individual Profile":
        page_individual_profile(df)

    elif page == "Force Development":
        page_force_development()
        return  # nothing else to render — function handles its own layout

    elif page == "Unit Overview":
        # Static unit roster — order is fixed regardless of what's in the data.
        # The very first entry "All Units" is a special top-level scope; the
        # remaining names are individual squadrons in the order requested.
        # Unknown / blank tenants in the data are silently ignored.
        SQUADRON_UNIT_ORDER = [
            "195 WG HQ",
            "195 OG",
            "147 CBCS",
            "148 SOPS",
            "216 EWS",
            "261 COS",
            "195 ISRG",
            "149 IS",
            "222 ISS",
            "234 IS",
        ]

        try:
            from database import get_all_tenants as _gat
            _tenant_lookup = {t["id"]: t["name"] for t in _gat()}
        except Exception:
            _tenant_lookup = {}

        df_with_unit = df.copy()
        if "_tenant_id" in df_with_unit.columns:
            df_with_unit["_unit_name"] = df_with_unit["_tenant_id"].map(
                lambda tid: _tenant_lookup.get(tid) if pd.notna(tid) else None
            )
        else:
            df_with_unit["_unit_name"] = st.session_state.get("tenant_name") or None

        # Per-unit list of non-blank flight names (sorted alphabetically).
        def _flights_for(unit_name):
            sub = df_with_unit[df_with_unit["_unit_name"] == unit_name]
            flights = sub["Flight"].dropna().astype(str).str.strip()
            flights = flights[flights != ""]
            return sorted(flights.unique().tolist())

        # Build option list in the requested static order. Each option is a
        # tuple:
        #   ("none",   None,      None)        → placeholder
        #   ("all",    None,      None)        → All Units (every member)
        #   ("unit",   unit_name, None)        → unit header (all flights in unit)
        #   ("flight", unit_name, flight_name) → individual flight under that unit
        options = [("none", None, None), ("all", None, None)]
        for unit_name in SQUADRON_UNIT_ORDER:
            options.append(("unit", unit_name, None))
            for flight_name in _flights_for(unit_name):
                options.append(("flight", unit_name, flight_name))

        # Dropdown formatting:
        #   - "No option selected" / "All Units"      → shown as plain text
        #   - Unit header (e.g. "149 IS")             → shown as plain text
        #   - Flight under a unit (e.g. "Alpha")      → shown as a two-line
        #     stack:
        #         149 IS
        #             ↳ Alpha
        #     This way both the open dropdown row AND the closed selectbox
        #     display the unit context above the indented flight name.
        def _fmt(opt):
            kind, unit_name, flight_name = opt
            if kind == "none":
                return "No option selected"
            if kind == "all":
                return "All Units"
            if kind == "unit":
                return unit_name
            # Two-line stacked: unit on top, indented flight beneath.
            return f"{unit_name}\n\u00a0\u00a0\u00a0\u00a0↳ {flight_name}"

        # Allow the selectbox label / options / closed display to render newlines
        # so the two-line flight format above stacks visually as Unit + Flight.
        st.markdown("""
        <style>
        /* Squadron Overview selectbox: render \\n as a real line break in the
           closed display AND in dropdown rows. */
        .st-key-squadron_overview_unit_flight [data-baseweb="select"] *,
        .st-key-squadron_overview_unit_flight [role="option"],
        .st-key-squadron_overview_unit_flight [role="option"] * {
            white-space: pre-line !important;
            line-height: 1.25 !important;
        }
        /* Give the closed selectbox a touch more vertical room for two lines */
        .st-key-squadron_overview_unit_flight [data-baseweb="select"] > div {
            min-height: 44px !important;
            height: auto !important;
            padding-top: 4px !important;
            padding-bottom: 4px !important;
        }
        /* Dropdown options need extra height too */
        .st-key-squadron_overview_unit_flight ~ * [role="option"],
        [data-baseweb="popover"] [role="option"] {
            min-height: 36px !important;
            height: auto !important;
            padding-top: 6px !important;
            padding-bottom: 6px !important;
        }
        </style>
        """, unsafe_allow_html=True)

        sel = st.selectbox(
            "Select Unit / Flight",
            options,
            format_func=_fmt,
            key="squadron_overview_unit_flight",
        )
        sel_kind, sel_unit, sel_flight_name = sel

        # Mirror the selection into tenant_name (non-authoritative — the
        # banner reads selectbox state directly to avoid a re-render flash).
        if sel_kind == "none" or sel_kind == "all":
            st.session_state["tenant_name"] = "All Units"
        elif sel_kind in ("unit", "flight") and sel_unit:
            st.session_state["tenant_name"] = sel_unit

        if sel_kind == "none":
            # Nothing selected yet — show a friendly hint and stop here so we
            # don't try to render charts on an empty / undefined slice.
            st.markdown(
                '<div style="margin:6px 0 18px 0;padding:0;color:#9dc4db;'
                'font-family:Barlow Condensed,sans-serif;font-size:13px;'
                'letter-spacing:1.5px;text-transform:uppercase;">'
                'Select a unit or flight from the dropdown above to load the Unit Overview dashboard.</div>',
                unsafe_allow_html=True,
            )
            return

        if sel_kind == "all":
            fdf = df_with_unit.copy()
            sel_flight = "All Units"
        elif sel_kind == "unit":
            fdf = df_with_unit[df_with_unit["_unit_name"] == sel_unit].copy()
            sel_flight = f"{sel_unit} (All Flights)"
        else:
            fdf = df_with_unit[
                (df_with_unit["_unit_name"] == sel_unit)
                & (df_with_unit["Flight"].astype(str).str.strip() == sel_flight_name)
            ].copy()
            sel_flight = f"{sel_unit} / {sel_flight_name}"
        sec_header("Member Information")

        # Column ordering by group. Each group's columns share a header colour.
        # Group 1: Identity        Group 7: Leadership + Assignments
        # Group 2: Service dates   Group 8: Awards
        # Group 3: Eval/Promo      Group 9: Fitness
        # Group 4: Skill           Group 10: Prof Orgs
        # Group 5: PME             Group 11: Notes
        # Group 6: Education       Group 12: Last Modified
        pme_keys = [f for f, _ in PME_FIELDS]
        edu_keys = [f for f, _ in EDU_FIELDS]
        table_cols = (
            # Group 1: Identity — name first, then rank, AFSC, unit, flight
            ["FirstName", "LastName", "Rank", "DAFSC", "_unit_name", "Flight"]
            # Group 2
            + ["DOE", "TIS", "DOR", "TIG"]
            # Group 3
            + ["LastEval", "PromoRecomm", "LastACA"]
            # Group 4
            + ["SkillLevel"]
            # Group 5
            + pme_keys
            # Group 6
            + edu_keys
            # Group 7 (Leadership Roles before Assignments)
            + ["LeadershipRoles", "Assignments", "AssignmentsDate"]
            # Group 8
            + ["AwardsDecs", "AwardsDecsDate"]
            # Group 9
            + ["Fitness"]
            # Group 10
            + ["ProfOrgMbr"]
            # Group 11
            + ["SupervisorNotes", "RateeNotes"]
            # Group 12
            + ["LastEdit"]
        )

        # Raw series needed for conditional cell logic
        _tig_months = fdf["TIGMonthsNum"].reset_index(drop=True)
        _last_aca   = fdf["LastACA"].reset_index(drop=True)

        out_df = fdf[table_cols].fillna("").replace("nan", "").rename(columns=DISPLAY_MAP)

        # ── Group → pastel colour palette (theme-aligned) ──────────────────────
        GROUP_COLORS = {
            "identity":   "#BFD7EA",  # soft blue        — Group 1
            "service":    "#CBF2CC",  # soft green       — Group 2
            "eval":       "#EBDBFF",  # soft lavender    — Group 3
            "skill":      "#FFEEAB",  # soft yellow      — Group 4
            "pme":        "#FFE8C9",  # soft peach       — Group 5
            "edu":        "#EFCFFC",  # soft pink-purple — Group 6
            "leadership": "#A8E0C2",  # soft mint-green  — Group 7
            "awards":     "#F7DAEC",  # soft rose-pink   — Group 8
            "fitness":    "#ABE3FF",  # soft sky blue    — Group 9
            "proforg":    "#DAF7F1",  # soft aqua        — Group 10
            "notes":      "#FFD8B5",  # soft apricot     — Group 11
            "modified":   "#D6D6E8",  # soft lilac-grey  — Group 12
        }
        # PME and EDU columns aren't renamed by DISPLAY_MAP, so the displayed
        # header text is the raw key (e.g. "PME_ALS", "EDU_BACHELORS"). Match
        # against those keys, not the friendly labels.
        pme_keys_for_grp = [k for k, _ in PME_FIELDS]
        edu_keys_for_grp = [k for k, _ in EDU_FIELDS]
        col_to_group = {}
        for c in ["Rank", "First Name", "Last Name", "AFSC", "Unit", "Flight"]:
            col_to_group[c] = "identity"
        for c in ["Date of Entry", "Time in Service", "Date of Rank", "Time in Grade"]:
            col_to_group[c] = "service"
        for c in ["Last Eval", "Promotion Recommendation", "Last ACA"]:
            col_to_group[c] = "eval"
        col_to_group["Skill Level"] = "skill"
        for c in pme_keys_for_grp:
            col_to_group[c] = "pme"
        for c in edu_keys_for_grp:
            col_to_group[c] = "edu"
        for c in ["Leadership Roles", "Assignments", "Assignment Dates"]:
            col_to_group[c] = "leadership"
        for c in ["Awards/Decorations", "Award/Dec Dates"]:
            col_to_group[c] = "awards"
        col_to_group["Fitness"]                    = "fitness"
        col_to_group["Professional Organizations"] = "proforg"
        for c in ["Supervisor Notes", "Ratee Notes"]:
            col_to_group[c] = "notes"
        col_to_group["Last Modified"] = "modified"

        # ── Render: interactive HTML table with colored group headers,
        # click-to-sort, per-column filter dropdowns, and global search ───────
        cols_display = list(out_df.columns)

        import html as _html, uuid as _uuid

        # Header cells: each <th> uses its group's background colour and
        # contains a clickable label (with sort arrow) plus a <select> filter
        # populated client-side from that column's unique values.
        header_cells = ""
        for idx, col in enumerate(cols_display):
            grp = col_to_group.get(col)
            bg  = GROUP_COLORS.get(grp, "#2E3E73")
            header_cells += (
                f'<th data-col-idx="{idx}" '
                f'style="background-color:{bg};color:#03041F;font-weight:700;'
                f'padding:0;border:1px solid #444;white-space:nowrap;'
                f'position:sticky;top:0;z-index:2;">'
                f'<div class="wg-th-inner">'
                f'<div class="wg-th-label" data-col-idx="{idx}">'
                f'<span class="wg-th-name">{_html.escape(col)}</span>'
                f'<span class="wg-th-sort">⇅</span>'
                f'</div>'
                f'<button type="button" class="wg-th-filter" data-col-idx="{idx}" '
                f'aria-haspopup="listbox" aria-expanded="false">'
                f'<span class="wg-th-filter-label">(all)</span>'
                f'<span class="wg-th-filter-caret">▾</span>'
                f'</button>'
                f'</div></th>'
            )

        # Data rows. Conditional cell highlighting (TIG <24mo red, ACA stale
        # yellow) is applied inline. data-val is used by JS for sort/filter.
        data_rows = ""
        for row_i, (_, row) in enumerate(out_df.iterrows()):
            cells = ""
            for col_i, col in enumerate(cols_display):
                v = row[col]
                val = "" if pd.isna(v) else str(v)
                cell_style = "padding:5px 10px;border:1px solid #444;white-space:nowrap;"

                if col == "Time in Grade":
                    months = _tig_months.iloc[row_i] if row_i < len(_tig_months) else 0
                    try:
                        months_val = float(months) if months != "" else 0
                    except (TypeError, ValueError):
                        months_val = 0
                    if months_val < 24:
                        cell_style += "background-color:#FF6B6B;color:#03041F;"

                if col == "Last ACA":
                    d = parse_date(_last_aca.iloc[row_i] if row_i < len(_last_aca) else "")
                    if d and months_since(d) > 24:
                        cell_style += "background-color:#FFF799;color:#03041F;"

                cells += (
                    f'<td data-col-idx="{col_i}" data-val="{_html.escape(val)}" '
                    f'style="{cell_style}">{_html.escape(val)}</td>'
                )
            data_rows += f"<tr>{cells}</tr>"

        # Random ID so multiple instances on a page don't collide.
        tbl_id = "wg_tbl_" + _uuid.uuid4().hex[:8]

        # Iframe height computed to match the table tightly. Toolbar + table
        # header is ~85px; each data row is ~28px. We add a tiny 8px buffer
        # so the bottom border isn't clipped, and cap so the iframe doesn't
        # grow beyond a reasonable viewport height.
        nrows = max(1, len(out_df))
        iframe_height = min(640, 95 + nrows * 28)

        table_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {{
    margin: 0; padding: 0;
    font-family: 'Barlow', -apple-system, BlinkMacSystemFont, sans-serif;
    background: transparent;
    color: #111;
  }}
  .wg-tbl-toolbar {{
    display: flex; gap: 12px; align-items: center;
    padding: 4px 0 8px 0;
  }}
  .wg-tbl-clear {{
    padding: 6px 14px;
    background: #2a4090; color: #dde6f5;
    border: 1px solid rgba(240,192,48,0.3);
    border-radius: 4px;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 11px; font-weight: 700;
    letter-spacing: 1px; text-transform: uppercase;
    cursor: pointer; transition: all 0.15s ease;
  }}
  .wg-tbl-clear:hover {{
    background: #f0c030; color: #0e1a3d; border-color: #f0c030;
    transform: scale(1.03); box-shadow: 0 4px 16px rgba(240,192,48,0.4);
  }}
  .wg-tbl-count {{ font-size: 0.85rem; color: #555; }}
  .wg-tbl-scroll {{
    overflow: auto;
    max-height: {iframe_height - 55}px;
    border: 1px solid #444;
    border-radius: 4px;
  }}
  table.wg-tbl {{
    border-collapse: collapse;
    font-size: 0.82rem;
    width: 100%;
  }}
  table.wg-tbl thead th {{
    position: sticky; top: 0; z-index: 2;
    padding: 0;
    border: 1px solid #444;
    white-space: nowrap;
    font-weight: 700;
    color: #03041F;
  }}
  .wg-th-inner {{
    display: flex; flex-direction: column; gap: 4px;
    padding: 6px 8px;
  }}
  .wg-th-label {{
    display: flex; align-items: center; justify-content: space-between;
    cursor: pointer; user-select: none; gap: 6px;
  }}
  .wg-th-name {{ white-space: nowrap; }}
  .wg-th-sort {{ font-size: 0.72rem; opacity: 0.55; }}
  .wg-th-label.wg-sort-asc .wg-th-sort,
  .wg-th-label.wg-sort-desc .wg-th-sort {{ opacity: 1; }}
  .wg-th-filter {{
    font-size: 0.72rem;
    padding: 3px 6px;
    border: 1px solid rgba(0,0,0,0.35);
    border-radius: 3px;
    background-color: #ffffff;
    color: #111111;
    width: 100%;
    box-sizing: border-box;
    font-family: 'Barlow', sans-serif;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 4px;
    text-align: left;
    line-height: 1.3;
  }}
  .wg-th-filter:hover {{
    background-color: #f0f4ff;
    border-color: rgba(0,0,0,0.55);
  }}
  .wg-th-filter.wg-active {{
    background-color: #fff8d8;
    border-color: #c9a000;
  }}
  .wg-th-filter-label {{
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
  }}
  .wg-th-filter-caret {{
    font-size: 0.65rem;
    color: #555;
    flex-shrink: 0;
  }}
  /* Popover anchored to the body so it's not clipped by the table's
     overflow:auto scroll wrapper. Position is set via JS at open time. */
  .wg-popover {{
    position: absolute;
    z-index: 1000;
    background: #fff;
    border: 1px solid #444;
    border-radius: 4px;
    box-shadow: 0 6px 24px rgba(0,0,0,0.18);
    padding: 6px;
    min-width: 180px;
    max-width: 280px;
    font-family: 'Barlow', sans-serif;
    color: #111;
    display: none;
  }}
  .wg-popover.wg-open {{ display: block; }}
  .wg-popover-search {{
    width: 100%;
    box-sizing: border-box;
    padding: 4px 6px;
    margin-bottom: 4px;
    border: 1px solid #aaa;
    border-radius: 3px;
    font-size: 0.78rem;
  }}
  .wg-popover-actions {{
    display: flex;
    gap: 4px;
    margin-bottom: 4px;
  }}
  .wg-popover-actions button {{
    flex: 1;
    padding: 3px 4px;
    border: 1px solid #888;
    border-radius: 3px;
    background: #f5f5f5;
    color: #111;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    cursor: pointer;
  }}
  .wg-popover-actions button:hover {{
    background: #e6ecf7;
    border-color: #2a4090;
  }}
  .wg-popover-list {{
    max-height: 220px;
    overflow-y: auto;
    border: 1px solid #ddd;
    border-radius: 3px;
    padding: 2px 0;
  }}
  .wg-popover-list label {{
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 3px 6px;
    font-size: 0.78rem;
    cursor: pointer;
    user-select: none;
  }}
  .wg-popover-list label:hover {{ background: #f0f4ff; }}
  .wg-popover-list label.wg-hidden {{ display: none; }}
  .wg-popover-list input[type="checkbox"] {{
    margin: 0;
    cursor: pointer;
  }}
  .wg-popover-list .wg-empty {{
    padding: 8px;
    text-align: center;
    color: #888;
    font-size: 0.78rem;
    font-style: italic;
  }}
  .wg-popover-footer {{
    display: flex;
    gap: 4px;
    margin-top: 6px;
  }}
  .wg-popover-footer button {{
    flex: 1;
    padding: 4px 6px;
    border: 1px solid;
    border-radius: 3px;
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    cursor: pointer;
  }}
  .wg-popover-apply {{
    background: #2a4090;
    color: #fff;
    border-color: #2a4090;
  }}
  .wg-popover-apply:hover {{
    background: #f0c030;
    color: #0e1a3d;
    border-color: #f0c030;
  }}
  .wg-popover-cancel {{
    background: #fff;
    color: #444;
    border-color: #888;
  }}
  .wg-popover-cancel:hover {{ background: #f5f5f5; }}
  table.wg-tbl tbody td {{
    padding: 5px 10px;
    border: 1px solid #444;
    white-space: nowrap;
    color: #111;
  }}
  table.wg-tbl tbody tr.wg-row-hidden {{ display: none; }}
  table.wg-tbl tbody tr:nth-child(even):not(.wg-row-hidden) {{
    background: rgba(0,0,0,0.02);
  }}
</style>
</head>
<body>
  <div class="wg-tbl-toolbar">
    <button type="button" class="wg-tbl-clear">Clear filters</button>
    <span class="wg-tbl-count"></span>
  </div>
  <div class="wg-tbl-scroll">
    <table class="wg-tbl" id="{tbl_id}">
      <thead><tr>{header_cells}</tr></thead>
      <tbody>{data_rows}</tbody>
    </table>
  </div>
  <!-- Single popover element reused for every column's filter. Anchored
       absolutely at click time. Sits outside the scroll wrapper so it
       isn't clipped. -->
  <div class="wg-popover" id="wg-popover" role="dialog" aria-modal="false">
    <input type="text" class="wg-popover-search" placeholder="Search values..." />
    <div class="wg-popover-actions">
      <button type="button" class="wg-popover-selectall">Select all</button>
      <button type="button" class="wg-popover-clear">Clear</button>
    </div>
    <div class="wg-popover-list"></div>
    <div class="wg-popover-footer">
      <button type="button" class="wg-popover-cancel">Cancel</button>
      <button type="button" class="wg-popover-apply">Apply</button>
    </div>
  </div>
<script>
(function() {{
  var table   = document.getElementById("{tbl_id}");
  if (!table) return;
  var tbody   = table.querySelector("tbody");
  var rows    = Array.prototype.slice.call(tbody.querySelectorAll("tr"));
  var clear   = document.querySelector(".wg-tbl-clear");
  var counter = document.querySelector(".wg-tbl-count");
  var filterBtns = document.querySelectorAll(".wg-th-filter");
  var labels  = document.querySelectorAll(".wg-th-label");
  var popover = document.getElementById("wg-popover");
  var popSearch = popover.querySelector(".wg-popover-search");
  var popList   = popover.querySelector(".wg-popover-list");
  var popSelectAll = popover.querySelector(".wg-popover-selectall");
  var popClear     = popover.querySelector(".wg-popover-clear");
  var popApply     = popover.querySelector(".wg-popover-apply");
  var popCancel    = popover.querySelector(".wg-popover-cancel");

  // selectedByCol[ci] = Set of selected values, or null when "all" (no filter).
  var selectedByCol = {{}};
  // popContext = info about the column whose popover is currently open.
  var popContext = null;
  // pendingSelection = the Set being edited inside the open popover.
  var pendingSelection = null;

  // Three-state sort: asc -> desc -> none.
  var sortState = {{ col: null, dir: 0 }};
  labels.forEach(function(lbl) {{
    lbl.addEventListener("click", function(e) {{
      // Don't sort if the click was on the filter button.
      if (e.target.closest(".wg-th-filter")) return;
      var ci = parseInt(lbl.getAttribute("data-col-idx"), 10);
      if (sortState.col === ci) {{
        sortState.dir = sortState.dir === 1 ? -1 : (sortState.dir === -1 ? 0 : 1);
      }} else {{
        sortState.col = ci;
        sortState.dir = 1;
      }}
      labels.forEach(function(l) {{
        l.classList.remove("wg-sort-asc", "wg-sort-desc");
        var s = l.querySelector(".wg-th-sort");
        if (s) s.textContent = "\u21C5";
      }});
      if (sortState.dir !== 0) {{
        lbl.classList.add(sortState.dir === 1 ? "wg-sort-asc" : "wg-sort-desc");
        var s = lbl.querySelector(".wg-th-sort");
        if (s) s.textContent = sortState.dir === 1 ? "\u25B2" : "\u25BC";
      }} else {{
        sortState.col = null;
      }}
      applySort();
    }});
  }});

  // Filter-button clicks open the popover.
  filterBtns.forEach(function(btn) {{
    btn.addEventListener("click", function(e) {{
      e.stopPropagation();
      var ci = parseInt(btn.getAttribute("data-col-idx"), 10);
      openPopover(ci, btn);
    }});
  }});

  // Click anywhere else closes the popover (cancel).
  document.addEventListener("click", function(e) {{
    if (popContext && !popover.contains(e.target) &&
        !e.target.classList.contains("wg-th-filter")) {{
      closePopover(false);
    }}
  }});
  document.addEventListener("keydown", function(e) {{
    if (e.key === "Escape" && popContext) closePopover(false);
  }});
  // Scrolling the table or window dismisses the popover (cancel).
  document.querySelector(".wg-tbl-scroll").addEventListener("scroll", function() {{
    if (popContext) closePopover(false);
  }});
  window.addEventListener("scroll", function() {{
    if (popContext) closePopover(false);
  }}, true);

  popSearch.addEventListener("input", function() {{
    var q = (popSearch.value || "").trim().toLowerCase();
    popList.querySelectorAll("label").forEach(function(lbl) {{
      var v = (lbl.getAttribute("data-val") || "").toLowerCase();
      if (q && v.indexOf(q) === -1) lbl.classList.add("wg-hidden");
      else lbl.classList.remove("wg-hidden");
    }});
  }});
  popSelectAll.addEventListener("click", function() {{
    popList.querySelectorAll("label:not(.wg-hidden) input[type=checkbox]")
      .forEach(function(cb) {{
        cb.checked = true;
        pendingSelection.add(cb.value);
      }});
  }});
  popClear.addEventListener("click", function() {{
    popList.querySelectorAll("label:not(.wg-hidden) input[type=checkbox]")
      .forEach(function(cb) {{
        cb.checked = false;
        pendingSelection.delete(cb.value);
      }});
  }});
  popCancel.addEventListener("click", function() {{ closePopover(false); }});
  popApply.addEventListener("click", function() {{ closePopover(true); }});

  function openPopover(ci, anchorBtn) {{
    popContext = {{ ci: ci, anchor: anchorBtn }};

    // Compute available values: rows visible if we ignore THIS column's filter
    // but still apply all OTHER columns' filters. That's what makes filtering
    // cascade — selecting Squadron narrows the Flight options.
    var availableVals = computeAvailableValues(ci);

    // Current selection state for this column (clone so Cancel can revert).
    var current = selectedByCol[ci];
    pendingSelection = new Set(current ? Array.from(current) : availableVals);

    // Build checkbox list.
    popList.innerHTML = "";
    if (availableVals.length === 0) {{
      var empty = document.createElement("div");
      empty.className = "wg-empty";
      empty.textContent = "No values to filter";
      popList.appendChild(empty);
    }} else {{
      availableVals.forEach(function(v) {{
        var lbl = document.createElement("label");
        lbl.setAttribute("data-val", v);
        var cb = document.createElement("input");
        cb.type = "checkbox";
        cb.value = v;
        cb.checked = pendingSelection.has(v);
        cb.addEventListener("change", function() {{
          if (cb.checked) pendingSelection.add(v);
          else            pendingSelection.delete(v);
        }});
        var text = document.createElement("span");
        text.textContent = v;
        lbl.appendChild(cb);
        lbl.appendChild(text);
        popList.appendChild(lbl);
      }});
    }}

    popSearch.value = "";
    popList.querySelectorAll("label").forEach(function(l) {{ l.classList.remove("wg-hidden"); }});

    // Position popover beneath the filter button.
    var rect = anchorBtn.getBoundingClientRect();
    popover.classList.add("wg-open");
    var pw = popover.offsetWidth;
    var ph = popover.offsetHeight;
    var top  = rect.bottom + window.scrollY + 2;
    var left = rect.left   + window.scrollX;
    // Clamp to viewport.
    var vw = document.documentElement.clientWidth;
    if (left + pw > vw - 8) left = Math.max(8, vw - pw - 8);
    var vh = window.innerHeight;
    if (rect.bottom + ph > vh - 8 && rect.top - ph > 8) {{
      top = rect.top + window.scrollY - ph - 2; // open upward instead
    }}
    popover.style.left = left + "px";
    popover.style.top  = top + "px";
    anchorBtn.setAttribute("aria-expanded", "true");
    setTimeout(function() {{ popSearch.focus(); }}, 0);
  }}

  function closePopover(commit) {{
    if (!popContext) return;
    if (commit) {{
      var ci = popContext.ci;
      var availableVals = computeAvailableValues(ci);
      // If pending == all available values, treat as "no filter" (null).
      // Otherwise store the Set.
      if (pendingSelection.size === 0 || pendingSelection.size === availableVals.length) {{
        // Empty selection means "match nothing" — but Excel treats that as
        // "show no rows", which is unusual UX. We treat empty == no filter
        // (same as all selected). User can use Clear button on the toolbar.
        selectedByCol[ci] = null;
      }} else {{
        selectedByCol[ci] = new Set(pendingSelection);
      }}
      updateFilterButtonLabel(ci);
      applyFilters();
    }}
    popover.classList.remove("wg-open");
    if (popContext.anchor) popContext.anchor.setAttribute("aria-expanded", "false");
    popContext = null;
    pendingSelection = null;
  }}

  function computeAvailableValues(ci) {{
    // Unique values for column ci, taken only from rows that pass every
    // OTHER active filter. This is the cascading behavior.
    var seen = {{}}, values = [];
    rows.forEach(function(tr) {{
      // Apply all filters except ci.
      for (var key in selectedByCol) {{
        var k = parseInt(key, 10);
        if (k === ci) continue;
        var sel = selectedByCol[k];
        if (!sel) continue;
        var td = tr.children[k];
        var v = (td && td.getAttribute("data-val")) || "";
        if (!sel.has(v)) return;
      }}
      var td = tr.children[ci];
      if (!td) return;
      var v = td.getAttribute("data-val") || "";
      if (v === "" || seen[v]) return;
      seen[v] = true;
      values.push(v);
    }});
    values.sort(function(a, b) {{
      return a.localeCompare(b, undefined, {{numeric:true, sensitivity:"base"}});
    }});
    return values;
  }}

  function updateFilterButtonLabel(ci) {{
    var btn = document.querySelector('.wg-th-filter[data-col-idx="' + ci + '"]');
    if (!btn) return;
    var labelEl = btn.querySelector(".wg-th-filter-label");
    var sel = selectedByCol[ci];
    if (!sel) {{
      labelEl.textContent = "(all)";
      btn.classList.remove("wg-active");
    }} else {{
      var arr = Array.from(sel);
      if (arr.length === 1) labelEl.textContent = arr[0];
      else if (arr.length <= 3) labelEl.textContent = arr.join(", ");
      else labelEl.textContent = arr.length + " selected";
      btn.classList.add("wg-active");
    }}
  }}

  clear.addEventListener("click", function() {{
    selectedByCol = {{}};
    filterBtns.forEach(function(btn) {{
      var labelEl = btn.querySelector(".wg-th-filter-label");
      labelEl.textContent = "(all)";
      btn.classList.remove("wg-active");
    }});
    applyFilters();
  }});

  function applyFilters() {{
    var visible = 0;
    rows.forEach(function(tr) {{
      var show = true;
      for (var key in selectedByCol) {{
        var sel = selectedByCol[key];
        if (!sel) continue;
        var ci = parseInt(key, 10);
        var td = tr.children[ci];
        var v = (td && td.getAttribute("data-val")) || "";
        if (!sel.has(v)) {{ show = false; break; }}
      }}
      if (show) {{ tr.classList.remove("wg-row-hidden"); visible++; }}
      else      {{ tr.classList.add("wg-row-hidden"); }}
    }});
    counter.textContent = "Showing " + visible + " of " + rows.length;
  }}

  function applySort() {{
    if (sortState.col === null || sortState.dir === 0) {{
      rows.forEach(function(tr) {{ tbody.appendChild(tr); }});
      return;
    }}
    var ci = sortState.col, dir = sortState.dir;
    rows.slice().sort(function(a, b) {{
      var av = (a.children[ci] && a.children[ci].getAttribute("data-val")) || "";
      var bv = (b.children[ci] && b.children[ci].getAttribute("data-val")) || "";
      return av.localeCompare(bv, undefined, {{numeric:true, sensitivity:"base"}}) * dir;
    }}).forEach(function(tr) {{ tbody.appendChild(tr); }});
  }}

  applyFilters();
}})();
</script>
</body>
</html>
"""
        # _components.html runs the <script> in a sandboxed iframe so the JS
        # actually executes (st.html strips inline scripts).
        _render_table_export(out_df, "unit_member_information",
                             f"uo_{abs(hash(str(sel_flight))) % 10**8}")
        _components.html(table_html, height=iframe_height, scrolling=False)
        st.write(f"**Total Personnel:** {len(fdf)}")
        # sel_flight is always a context-rich label here ("All Units",
        # "149 IS (All Flights)", or "149 IS / Alpha").
        common_dashboard(fdf, sel_flight)
