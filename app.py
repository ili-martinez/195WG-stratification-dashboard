"""
app.py — 195 WG Enlisted Development Dashboard (Multi-tenant, Supabase)
Run with: streamlit run app.py
"""

import sys, os, re, base64
from pathlib import Path
from datetime import datetime, timezone

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
os.chdir(_HERE)

import streamlit as st

st.set_page_config(
    page_title="195 WG Enlisted Development Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

from database import (
    get_user, verify_pw, needs_rehash, update_password,
    record_failed_attempt, record_success, check_lockout,
    create_session, resolve_session, delete_session,
    get_all_tenants, get_tenant,
    check_password_history,
    LOCKOUT_AFTER_CONSEC, DISABLE_AFTER_DAILY, LOCKOUT_MINUTES,
)

LOGO_FILE    = "195wg_logo.png"
PATCHES_FILE = "squadron_patches.png"
BENCH_VIEW_TITLES = {"Commander","SEL","Senior Enlisted Leader","First Sergeant","Flight Commander","Flight Chief"}

def validate_password(password):
    errors = []
    if len(password) < 12: errors.append("At least 12 characters.")
    if len(re.findall(r"\d", password)) < 2: errors.append("At least 2 numbers.")
    if len(re.findall(r"[^a-zA-Z0-9]", password)) < 2: errors.append("At least 2 special characters.")
    return errors

def get_client_ip():
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        from streamlit.runtime import get_instance
        ctx = get_script_run_ctx()
        if ctx:
            runtime = get_instance()
            info = runtime.get_client(ctx.session_id)
            if info: return info.request.remote_ip
    except Exception:
        pass
    return "unknown"

def get_cookie_token(): return st.query_params.get("t", "")
def get_cookie_page(): return st.query_params.get("p", "Individual Profile")
def set_cookie(token, page="Individual Profile"):
    st.query_params["t"] = token
    st.query_params["p"] = page
def update_cookie_page(page): st.query_params["p"] = page
def clear_cookie(): st.query_params.clear()

# ── Session state defaults ────────────────────────────────────────────────────
_defaults = {
    "logged_in": False, "role": "user", "username": "", "user_id": None,
    "tenant_id": None, "tenant_name": "", "title": "", "bench_view": False,
    "session_token": "", "page": "Individual Profile",
    "edit_open": False, "add_open": False, "member_search": "",
    "selected_flight": "", "selected_member": "", "locked_member": "", "locked_flight": "",
    "sa_tenant_id": None, "sa_view_all": False, "active_tenant_id": None,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Auto-login ────────────────────────────────────────────────────────────────
if not st.session_state.logged_in:
    _token = get_cookie_token()
    if _token:
        _user = resolve_session(_token, get_client_ip())
        if _user:
            _title = _user.get("title", "")
            st.session_state.update({
                "logged_in": True, "role": _user["role"],
                "username": _user["username"], "user_id": _user["id"],
                "tenant_id": _user.get("tenant_id"), "title": _title,
                "bench_view": (_user["role"] in ("admin","super_admin") or _title in BENCH_VIEW_TITLES),
                "session_token": _token, "page": get_cookie_page(),
            })
            if _user.get("tenant_id"):
                t = get_tenant(_user["tenant_id"])
                st.session_state.tenant_name = t["name"] if t else ""
elif st.session_state.logged_in:
    _token = st.session_state.get("session_token","")
    if _token:
        _user = resolve_session(_token, get_client_ip())
        if not _user:
            for k, v in _defaults.items():
                st.session_state[k] = v
            clear_cookie()
            st.rerun()

# Migrate old page names to the renamed Unit Overview page so stale
# cookies / bookmarks don't land on a blank route.
if st.session_state.get("page") in ("Flight Dashboard", "Squadron Dashboard", "Squadron Overview"):
    st.session_state.page = "Unit Overview"
    update_cookie_page("Unit Overview")

# Unit Overview and Individual Profile both have in-page hierarchical
# Unit/Flight dropdowns that take over the org bar's role (the org bar itself
# is hidden on these pages). For super-admins, force All Units mode so those
# dropdowns can always show every unit's flights and members.
if (
    st.session_state.get("page") in ("Unit Overview", "Individual Profile", "Force Development")
    and st.session_state.get("role") == "super_admin"
    and not st.session_state.get("sa_view_all", False)
):
    st.session_state.sa_view_all     = True
    st.session_state.sa_tenant_id    = None
    st.session_state.active_tenant_id = None
    st.session_state.tenant_name     = "All Units"

# ── Login page ────────────────────────────────────────────────────────────────
def show_login():
    logo    = Path(LOGO_FILE)
    patches = Path(PATCHES_FILE)

    # ── Google Fonts + theme styles ───────────────────────────────────────────
    st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800&family=Barlow:wght@300;400;500;600&display=swap" rel="stylesheet">

<style>
/* ── Design tokens ────────────────────────────────────────────────────────── */
:root {
  --navy:      #1a2a5e;
  --navy-dark: #0e1a3d;
  --navy-mid:  #1f3272;
  --navy-lt:   #2a4090;
  --gold:      #f0c030;
  --gold-dk:   #c9960a;
  --gold-lt:   #f8d96a;
  --steel:     #7a93c0;
  --ice:       #dde6f5;
  --card-bg:   #162050;
  --border:    rgba(240,192,48,0.22);
}

/* ── Streamlit chrome resets ─────────────────────────────────────────────── */
#MainMenu, footer, header { visibility: hidden; }
/* Hide Streamlit keyboard shortcut button - target every possible selector */
[data-testid="stSidebarCollapsedControl"],
[data-testid="stToolbarActions"],
button[aria-label="Keyboard shortcuts"],
button[title="Keyboard shortcuts"],
div[data-testid="stActionButtonIcon"],
.stActionButton,
#MainMenu { display: none !important; visibility: hidden !important; }

/* Body matches banner color — any gap Streamlit adds above looks like banner */
html, body { background: #1f3272 !important; }

/* Zero out container padding — but NOT block-container (used for centering) */
[data-testid="stAppViewContainer"] > .main {
  padding-top: 0 !important;
  padding-left: 0 !important;
  padding-right: 0 !important;
  max-width: 100% !important;
}

/* block-container: centers form in the space between the two banners */
.block-container {
  padding-top: 250px !important;
  padding-bottom: 99px !important;
  padding-left: 0 !important;
  padding-right: 0 !important;
  max-width: 100% !important;
  min-height: 100vh !important;
  display: flex !important;
  flex-direction: column !important;
  justify-content: center !important;
  box-sizing: border-box !important;
}



/* ── Full-width banner ───────────────────────────────────────────────────── */
.wg-banner {
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  width: 100% !important;
  height: 113px;
  background: linear-gradient(160deg, #1f3272 0%, #0e1a3d 100%);
  border-bottom: 3px solid var(--gold);
  padding: 0 48px;
  display: flex;
  align-items: center;
  gap: 24px;
  overflow: hidden;
  box-sizing: border-box;
  z-index: 9999;
}

/* emblem */
.wg-emblem {
  width: 88px; height: 88px; flex-shrink: 0;
  filter: drop-shadow(0 2px 12px rgba(0,0,0,.55));
  z-index: 1;
}
.wg-emblem img { width: 100%; height: 100%; object-fit: contain; }

/* text */
.wg-hdr-text {
  display: flex;
  flex-direction: column;
  justify-content: center;
  z-index: 1;
}
.wg-eyebrow {
  font-family: 'Barlow Condensed', sans-serif;
  font-size: 16px;
  letter-spacing: 3.5px;
  text-transform: uppercase;
  color: var(--gold);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.wg-eyebrow::before,
.wg-eyebrow::after {
  content: '';
  display: inline-block;
  width: 28px; height: 1px;
  background: var(--gold-dk);
}
.wg-title {
  font-family: 'Barlow Condensed', sans-serif;
  font-size: 42px;
  font-weight: 800;
  letter-spacing: 2.5px;
  text-transform: uppercase;
  color: #ffffff;
  line-height: 1.05;
  margin: 0;
}
.wg-title em { color: var(--gold); font-style: normal; }
.wg-subtitle {
  font-family: 'Barlow Condensed', sans-serif;
  font-size: 17px;
  color: var(--steel);
  letter-spacing: 2.5px;
  text-transform: uppercase;
  margin-top: 7px;
  font-weight: 400;
}


.wg-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 32px 36px 28px;
  width: 100%;
  max-width: 400px;
  position: relative;
  box-shadow: 0 8px 40px rgba(0,0,0,.45);
}
.wg-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: var(--gold);
  border-radius: 10px 10px 0 0;
}
.wg-card-title {
  font-family: 'Barlow Condensed', sans-serif;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 2.5px;
  text-transform: uppercase;
  color: #1a2a5e;
  margin-bottom: 20px;
  text-align: center;
}

/* ── Light-mode overrides ────────────────────────────────────────────────── */
[data-theme="light"] .wg-card {
  background: #f0f4ff;
  border-color: rgba(26,42,94,0.15);
  box-shadow: 0 8px 40px rgba(26,42,94,.10);
}
[data-theme="light"] .wg-card-title { color: var(--navy-mid); }
[data-theme="light"] .wg-subtitle   { color: #4a6090; }

/* ── Page background ─────────────────────────────────────────────────────── */
[data-theme="dark"]  .main .block-container { background: var(--navy-dark) !important; }
[data-theme="light"] .main .block-container { background: #e8edf8 !important; }

/* ── Streamlit form widget overrides ─────────────────────────────────────── */
div[data-testid="stForm"] {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
}
div[data-testid="stForm"] label {
  font-family: 'Barlow Condensed', sans-serif !important;
  font-size: 11px !important;
  font-weight: 700 !important;
  letter-spacing: 1.8px !important;
  text-transform: uppercase !important;
  color: var(--steel) !important;
}
[data-theme="light"] div[data-testid="stForm"] label {
  color: var(--navy-mid) !important;
}

/* Gold primary button */
div[data-testid="stForm"] button[kind="primaryFormSubmit"] {
  background: var(--gold) !important;
  border-color: var(--gold) !important;
  color: var(--navy-dark) !important;
  -webkit-text-fill-color: var(--navy-dark) !important;
  font-family: 'Barlow Condensed', sans-serif !important;
  font-size: 13px !important;
  font-weight: 700 !important;
  letter-spacing: 1.5px !important;
  text-transform: uppercase !important;
  border-radius: 5px !important;
  transition: all .2s !important;
}
div[data-testid="stForm"] button[kind="primaryFormSubmit"]:hover {
  background: var(--gold-lt) !important;
  border-color: var(--gold-lt) !important;
  transform: scale(1.03) !important;
  box-shadow: 0 4px 16px rgba(240,192,48,.45) !important;
}
</style>
""", unsafe_allow_html=True)

    # ── Banner ────────────────────────────────────────────────────────────────
    logo_b64 = ""
    if logo.exists():
        with open(str(logo), "rb") as _lf:
            logo_b64 = base64.b64encode(_lf.read()).decode()

    logo_img = (
        f'<div style="width:88px;height:88px;flex-shrink:0;background-image:url(\'data:image/png;base64,{logo_b64}\');background-size:contain;background-repeat:no-repeat;background-position:center;pointer-events:none;filter:drop-shadow(0 2px 12px rgba(0,0,0,.55));"></div>'
        if logo_b64 else
        '<div style="width:88px;height:88px;"></div>'
    )

    st.markdown(f"""
<div class="wg-banner">
  <div class="wg-emblem">{logo_img}</div>
  <div class="wg-hdr-text">
    <div class="wg-eyebrow">California Air National Guard</div>
    <div class="wg-title"><em>195 WG</em> Enlisted Development Dashboard</div>
    <div class="wg-subtitle">Developing Airmen.&nbsp;&nbsp;Building Leaders.</div>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Login card ───────────────────────────────────────────────────────────
    _, center, _ = st.columns([1, 1.1, 1])
    with center:
        st.markdown('<div class="wg-card-title">Sign In</div>', unsafe_allow_html=True)

        with st.form("login_form", enter_to_submit=True):
            username  = st.text_input("Username", key="login_user")
            password  = st.text_input("Password", type="password", key="login_pass")
            submitted = st.form_submit_button("Login", type="primary", use_container_width=True)

        if submitted:
            is_locked, lock_msg = check_lockout(username)
            if is_locked:
                st.error(lock_msg)
            else:
                user = get_user(username)
                if user and verify_pw(password, user["password"]):
                    record_success(username)
                    if needs_rehash(user["password"]):
                        update_password(user["id"], password, user["password"])
                    token  = create_session(user["id"], get_client_ip())
                    _title = user.get("title", "")
                    st.session_state.update({
                        "logged_in": True, "role": user["role"],
                        "username": username, "user_id": user["id"],
                        "tenant_id": user.get("tenant_id"), "title": _title,
                        "bench_view": (user["role"] in ("admin","super_admin") or _title in BENCH_VIEW_TITLES),
                        "session_token": token, "page": "Individual Profile",
                    })
                    if user.get("tenant_id"):
                        t = get_tenant(user["tenant_id"])
                        st.session_state.tenant_name = t["name"] if t else ""
                    set_cookie(token, "Individual Profile")
                    st.rerun()
                else:
                    record_failed_attempt(username)
                    user = get_user(username)
                    if not user:
                        st.error("Invalid username or password.")
                    elif user.get("disabled"):
                        st.error("Account disabled. Please contact an administrator.")
                    elif user.get("lockout_until"):
                        st.warning(f"Account locked for {LOCKOUT_MINUTES} minutes.")
                    else:
                        consec = user.get("consec_failures", 0)
                        daily  = user.get("daily_failures", 0)
                        warn   = min(LOCKOUT_AFTER_CONSEC - consec, DISABLE_AFTER_DAILY - daily)
                        st.error(f"Invalid credentials. {warn} attempt(s) remaining.")

    # ── Squadron patches runner (pinned to bottom) ───────────────────────────
    if patches.exists():
        with open(str(patches), "rb") as _pf:
            _b64 = base64.b64encode(_pf.read()).decode()
        st.markdown(
            f'''<div style="
                position: fixed;
                bottom: 0; left: 0; right: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 14px 0 12px;
                background: linear-gradient(160deg, #1f3272 0%, #0e1a3d 100%);
                border-top: 3px solid #f0c030;
                z-index: 100;
                box-shadow: 0 -4px 24px rgba(0,0,0,0.4);
            ">
                <img src="data:image/png;base64,{_b64}"
                     style="height:80px;width:auto;opacity:0.95;" />
            </div>''',
            unsafe_allow_html=True
        )

if not st.session_state.logged_in:
    show_login()
    st.stop()

import dashboard      as _dash
import administration as _admin

apply_theme = _dash.apply_theme
show_logo   = _dash.show_logo
apply_theme()

# ── Inject top banner ─────────────────────────────────────────────────────────
import base64 as _b64
_logo_path = Path(LOGO_FILE)
_logo_b64 = ""
if _logo_path.exists():
    with open(str(_logo_path), "rb") as _lf:
        _logo_b64 = _b64.b64encode(_lf.read()).decode()
_logo_img = (
    f'<div style="width:100%;height:100%;background-image:url(\'data:image/png;base64,{_logo_b64}\');background-size:contain;background-repeat:no-repeat;background-position:center;pointer-events:none;"></div>'
    if _logo_b64 else ""
)
_banner_html = """__BANNER_CSS__
<div class="wg-top-banner">
  <div class="wg-top-banner-emblem">__LOGO__</div>
  <div>
    <div class="wg-top-banner-eyebrow">California Air National Guard</div>
    <div class="wg-top-banner-title"><em>195 WG</em> Enlisted Development Dashboard</div>
    <div class="wg-top-banner-sub">Developing Airmen.&nbsp;&nbsp;Building Leaders.</div>
  </div>
</div>
""".replace("__BANNER_CSS__", """
<style>
/* ── Hide Streamlit chrome ── */
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
header { display: none !important; height: 0 !important; }

/* Hide keyboard shortcut button and collapse toggle */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stToolbarActions"],
[data-testid="stStatusWidget"],
button[aria-label="Keyboard shortcuts"],
button[title="Keyboard shortcuts"],
/* Streamlit 1.50 keyboard button is in the sidebar header area */
[data-testid="stSidebar"] > div:first-child > div:first-child > div:last-child { 
    display: none !important; 
}

/* ── Top banner — starts after sidebar ── */
.wg-top-banner {
    position: fixed !important;
    top: 0 !important;
    left: 260px !important;
    right: 0 !important;
    z-index: 9999 !important;
    height: 113px;
    background: linear-gradient(160deg, #1f3272 0%, #0e1a3d 100%);
    border-bottom: 3px solid #f0c030;
    display: flex;
    align-items: center;
    gap: 20px;
    padding: 0 32px;
    box-sizing: border-box;
}
.wg-top-banner-emblem {
    width: 76px; height: 76px; flex-shrink: 0;
    filter: drop-shadow(0 2px 8px rgba(0,0,0,.5));
}
.wg-top-banner-eyebrow {
    font-family:'Barlow Condensed',sans-serif;
    font-size: 11px; letter-spacing: 3px; text-transform: uppercase;
    color: #f0c030; margin-bottom: 4px;
    display: flex; align-items: center; gap: 8px;
}
.wg-top-banner-eyebrow::before, .wg-top-banner-eyebrow::after {
    content: ''; display: inline-block; width: 20px; height: 1px; background: #c9960a;
}
.wg-top-banner-title {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 28px; font-weight: 800; letter-spacing: 2px;
    text-transform: uppercase; color: #fff; line-height: 1.05; margin: 0;
}
.wg-top-banner-title em { color: #f0c030; font-style: normal; }
.wg-top-banner-sub {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 12px; color: #7a93c0; letter-spacing: 2px;
    text-transform: uppercase; margin-top: 3px;
}

/* ── Sidebar — force visible after login ── */
[data-testid="stSidebar"],
section[data-testid="stSidebar"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    transform: none !important;
    left: 0 !important;
    z-index: 100 !important;
    width: 260px !important;
    min-width: 260px !important;
}
[data-testid="stSidebar"] > div:first-child {
    width: 260px !important;
    min-width: 260px !important;
}
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
    display: none !important;
}

/* ── Reset ALL login page CSS overrides ── */
html, body {
    background: unset !important;
}
.block-container {
    padding-top: 80px !important;
    padding-bottom: 0 !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
    min-height: unset !important;
    display: block !important;
    flex-direction: unset !important;
    justify-content: unset !important;
    max-width: 100% !important;
}
</style>
""").replace("__LOGO__", _logo_img)
st.markdown(_banner_html, unsafe_allow_html=True)

# When the org bar is hidden (Individual Profile / Unit Overview / Force
# Development / Administration), tighten the gap between the top banner and
# the first page element. The banner is 116px tall (113px height + 3px gold
# border) and is fixed-position. (Administration was added here after the
# top org-bar was removed — without this the page would have ~80px of
# unwanted whitespace before the "Administration" h1.)
if (
    st.session_state.get("page") in ("Individual Profile", "Unit Overview", "Force Development", "Administration")
    and st.session_state.get("logged_in", False)
):
    st.markdown("""
    <style>
    /* Streamlit header zero-out */
    header[data-testid="stHeader"] {
        height: 0 !important;
        min-height: 0 !important;
        background: transparent !important;
    }
    [data-testid="stAppViewContainer"] > .main {
        padding-top: 0 !important;
    }

    /* Prevent horizontal scrolling on the page itself. Without this, any
       wide content (e.g. Plotly charts with many bars, or wide iframes)
       can force the entire page to overflow horizontally and require
       scrolling — which then visually disconnects the fixed sidebar. */
    html, body {
        overflow-x: hidden !important;
        max-width: 100vw !important;
    }
    section[data-testid="stMain"],
    section[data-testid="stMain"] .block-container {
        overflow-x: hidden !important;
        max-width: 100% !important;
    }
    /* Plotly chart containers must respect their parent column's width.
       By default the SVG can be wider than its container. Force them to
       fit. */
    div[data-testid="stPlotlyChart"],
    div.stPlotlyChart,
    .stPlotlyChart {
        max-width: 100% !important;
        overflow: hidden !important;
    }
    div[data-testid="stPlotlyChart"] > div,
    div[data-testid="stPlotlyChart"] .js-plotly-plot,
    div[data-testid="stPlotlyChart"] .plotly,
    div[data-testid="stPlotlyChart"] .svg-container {
        max-width: 100% !important;
    }
    /* Component iframes (the Force Development tables, Unit Overview
       Member Information table) should also fit. The table inside scrolls
       horizontally if it needs to — but the iframe wrapper itself shouldn't
       extend the page. */
    iframe[title="streamlit_components.v1.html.html"] {
        max-width: 100% !important;
        width: 100% !important;
    }
    /* The element-container that wraps each component iframe also needs to
       clip — Streamlit sometimes sets it to the iframe's intrinsic width. */
    div[data-testid="stElementContainer"]:has(iframe[title="streamlit_components.v1.html.html"]):not([width="1px"]) {
        max-width: 100% !important;
        width: 100% !important;
        overflow-x: hidden !important;
    }
    /* Constrain horizontal blocks (st.columns containers) to fit their parent. */
    div[data-testid="stHorizontalBlock"] {
        max-width: 100% !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"],
    div[data-testid="stHorizontalBlock"] > div {
        max-width: 100% !important;
        min-width: 0 !important;
    }
    /* The vertical block (the page's main content stream) too. */
    section[data-testid="stMain"] div[data-testid="stVerticalBlock"] {
        max-width: 100% !important;
    }

    /* The block-container's padding-top positions the first visible widget
       below the fixed banner. Banner is 116px tall (113 + 3 gold). */
    section[data-testid="stMain"] .block-container,
    div.block-container {
        padding-top: 122px !important;
        padding-bottom: 0 !important;
    }

    /* THE FIX: kill the flex gap on the top-level vertical block.
       The diagnostic showed 8 zero-height children × 16px gap = 128px of
       wasted vertical space above the first real widget. We need extreme
       specificity because Streamlit's emotion-generated class on the
       same element sets `gap: 1rem` and might tie or beat a single
       attribute selector. */
    section[data-testid="stMain"] div.block-container > div[data-testid="stVerticalBlock"],
    div[data-testid="stAppViewContainer"] section[data-testid="stMain"] div.block-container > div[data-testid="stVerticalBlock"] {
        gap: 0 !important;
        row-gap: 0 !important;
    }

    /* Belt-and-suspenders: collapse margins on top-of-page wrappers that
       contain only style tags or hidden state divs (these are the ones that
       were eating vertical space). Charts, plotly, and other real content
       containers keep their natural spacing so we don't squash everything. */
    section[data-testid="stMain"] div.block-container > div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"]:has(style),
    section[data-testid="stMain"] div.block-container > div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"]:has(#wg-active-state),
    section[data-testid="stMain"] div.block-container > div[data-testid="stVerticalBlock"] > div[data-testid="stElementContainer"]:has(div.wg-top-banner) {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }

    /* Components iframe wrapper — the active-button polling iframe is 1px×1px
       and contributes vertical flex gap. Hide ONLY that one. We identify it
       by the wrapper's width="1px" attribute. Full-size component iframes
       (like the Unit Overview Member Information table) are left alone. */
    div[data-testid="stElementContainer"][width="1px"]:has(iframe[title="streamlit_components.v1.html.html"]) {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ── Org bar (REMOVED) ────────────────────────────────────────────────────────
# Previously this rendered a horizontal "ORG :" button bar on the
# Administration page for super-admins, letting them flip the global
# tenant scope. It was redundant: the user list on the Administration
# page already shows ALL users for super-admins regardless of scope,
# and Individual Profile / Unit Overview have their own in-page Unit /
# Flight cascading dropdowns. Removing it cleans up the top of the
# Administration page.
#
# `sa_view_all` and `sa_tenant_id` are still set elsewhere by those
# in-page dropdowns, so other pages that read them are unaffected.


import streamlit.components.v1 as _components
# Hide the components iframe via CSS — but give it a real size so Streamlit
# actually renders it (zero-height components are skipped).
st.markdown("""
<style>
/* Hide the JS-only 1px polling iframe (used to set data-active attributes
   on sidebar / org / form buttons). Full-size component iframes — like the
   Unit Overview Member Information table — are not affected. */
div[data-testid="stElementContainer"][width="1px"] iframe[title="streamlit_components.v1.html.html"] {
    display: none !important; height: 0 !important;
}
</style>
""", unsafe_allow_html=True)
_components.html("""
<script>
(function init() {
    try {
        var doc = window.parent.document;
        // Hide keyboard button
        doc.querySelectorAll('button').forEach(function(btn) {
            var txt = btn.textContent.toLowerCase().trim();
            if (txt.startsWith('keyb') || btn.getAttribute('aria-label') === 'Keyboard shortcuts') {
                btn.style.cssText = 'display:none!important';
                if (btn.parentElement) btn.parentElement.style.cssText = 'display:none!important';
            }
        });
        // Reset any stHorizontalBlock that isn't the org bar back to normal flow
        var blocks = doc.querySelectorAll('[data-testid="stHorizontalBlock"]');
        blocks.forEach(function(b, i) {
            if (i > 0) {
                b.style.removeProperty('position');
                b.style.removeProperty('top');
                b.style.removeProperty('left');
                b.style.removeProperty('right');
                b.style.removeProperty('height');
                b.style.removeProperty('z-index');
                b.style.removeProperty('overflow');
            }
        });

        // ── Active-button highlighting ─────────────────────────────────────
        // The Python side renders a hidden #wg-active-state element with
        // data-* attributes telling us which page / org / form is active.
        // We tag the matching buttons with data-active="true" so CSS can
        // style them yellow.
        var stateEl = doc.getElementById('wg-active-state');
        if (stateEl) {
            var activePage = (stateEl.getAttribute('data-page')      || '').trim();
            var activeOrg  = (stateEl.getAttribute('data-org')       || '').trim();
            var editOpen   = (stateEl.getAttribute('data-edit-open') || '').trim() === 'true';
            var addOpen    = (stateEl.getAttribute('data-add-open')  || '').trim() === 'true';

            function btnText(btn) {
                return (btn.textContent || '').replace(/\\s+/g, ' ').trim();
            }
            function setActive(btn, on) {
                if (!btn) return;
                if (on) btn.setAttribute('data-active', 'true');
                else    btn.removeAttribute('data-active');
            }

            // 1) Sidebar nav: tag the button whose text equals the active page.
            var sidebar = doc.querySelector('[data-testid="stSidebar"]');
            if (sidebar) {
                sidebar.querySelectorAll('button').forEach(function(btn) {
                    setActive(btn, btnText(btn) === activePage);
                });
            }

            // 2) Top org bar: tag the button whose text equals the active org.
            //    We try multiple strategies in parallel because the org bar's
            //    DOM structure has been finicky:
            //      a) Look up buttons by their Streamlit key class
            //         (.st-key-_org_0, _org_1, …).
            //      b) Walk siblings forward from #wg-org-bar-anchor.
            //      c) Fallback: any button outside the sidebar whose text
            //         exactly equals activeOrg.
            if (activeOrg) {
                var orgFound = false;

                // Strategy (a): .st-key-_org_N
                for (var i = 0; i < 50; i++) {
                    var wrap = doc.querySelector('.st-key-_org_' + i);
                    if (!wrap) break;
                    var b = wrap.querySelector('button');
                    if (b) {
                        var match = btnText(b) === activeOrg;
                        setActive(b, match);
                        if (match) orgFound = true;
                    }
                }

                // Strategy (b): walk siblings from the anchor
                if (!orgFound) {
                    var anchor = doc.getElementById('wg-org-bar-anchor');
                    if (anchor) {
                        var sib = anchor.nextElementSibling;
                        var hops = 0;
                        while (sib && hops < 6) {
                            if (sib.matches && sib.matches('[data-testid="stHorizontalBlock"]')) {
                                sib.querySelectorAll('button').forEach(function(btn) {
                                    var match = btnText(btn) === activeOrg;
                                    setActive(btn, match);
                                    if (match) orgFound = true;
                                });
                                break;
                            }
                            sib = sib.nextElementSibling;
                            hops++;
                        }
                    }
                }

                // Strategy (c): any button (outside the sidebar) whose text
                // matches activeOrg. Last-resort fallback.
                if (!orgFound) {
                    var sidebarEl = doc.querySelector('[data-testid="stSidebar"]');
                    doc.querySelectorAll('button').forEach(function(btn) {
                        if (sidebarEl && sidebarEl.contains(btn)) return;
                        if (btnText(btn) === activeOrg) {
                            setActive(btn, true);
                            orgFound = true;
                        }
                    });
                }
            }

            // 3) Edit Member / Add Member: tag based on whether their view is open.
            doc.querySelectorAll('button').forEach(function(btn) {
                var t = btnText(btn);
                if (t === 'Edit Member')                       setActive(btn, editOpen);
                else if (t === '✚ Add Member' ||
                         t === '✚  Add Member' ||
                         t === '+ Add Member')                  setActive(btn, addOpen);
            });
        }
    } catch (e) {
        console.error('wg active-button init error:', e);
    }
    setTimeout(init, 200);
})();
</script>
""", height=1, width=1)

def logout():
    delete_session(st.session_state.get("session_token",""))
    for k, v in _defaults.items():
        st.session_state[k] = v
    clear_cookie()
    st.rerun()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    role = st.session_state.role

    # ── Brand block ───────────────────────────────────────────────────────────
    # Determine display names. For super-admins on Individual Profile and
    # Unit Overview, derive the unit name DIRECTLY from each page's
    # Unit/Flight selectbox session state — this is already updated by
    # Streamlit before this banner renders, so we avoid the one-frame lag (and
    # the visible white-flash) that st.rerun() would cause.
    parent_org = "195 WG"
    page = st.session_state.get("page", "")
    if role == "super_admin":
        # Look up the page-specific selectbox state for unit context
        _sel = None
        if page == "Individual Profile":
            _sel = st.session_state.get("individual_unit_flight")
        elif page == "Unit Overview":
            _sel = st.session_state.get("squadron_overview_unit_flight")
        elif page == "Force Development":
            _sel = st.session_state.get("force_dev_unit")
        if isinstance(_sel, tuple) and len(_sel) == 3:
            _kind, _unit, _flight = _sel
            if _kind in ("unit", "flight") and _unit:
                unit_display = _unit
            else:
                # "none" or "all" → show All Units
                unit_display = "All Units"
        else:
            unit_display = st.session_state.get("tenant_name") or "All Units"
    else:
        unit_display = st.session_state.tenant_name or "—"

    st.markdown(
        f'<div style="padding:16px 8px 8px 8px;line-height:1.3;">'
        f'<div style="font-family:Barlow Condensed,sans-serif;font-size:1.5rem;font-weight:800;letter-spacing:2px;text-transform:uppercase;color:#ffffff;">{parent_org}</div>'
        f'<div style="font-family:Barlow Condensed,sans-serif;font-size:1.0rem;font-weight:600;color:#f0c030;letter-spacing:1px;">{unit_display}</div>'
        f'</div>',
        unsafe_allow_html=True)

    st.markdown("<hr style='margin:0.4rem 0;border-color:rgba(240,192,48,0.2);'>", unsafe_allow_html=True)

    st.markdown('<div class="sidebar-nav">', unsafe_allow_html=True)

    if st.button("Individual Profile", use_container_width=True):
        st.session_state.page = "Individual Profile"; update_cookie_page("Individual Profile"); st.rerun()
    if st.button("Unit Overview", use_container_width=True):
        st.session_state.page = "Unit Overview"; update_cookie_page("Unit Overview"); st.rerun()

    # Force Development is restricted to leadership roles: super-admins, plus
    # users whose title is Commander, SEL, or Senior Enlisted Leader.
    _fd_titles = {"Commander", "SEL", "Senior Enlisted Leader"}
    _user_title = st.session_state.get("title", "")
    if role == "super_admin" or _user_title in _fd_titles:
        if st.button("Force Development", use_container_width=True):
            st.session_state.page = "Force Development"; update_cookie_page("Force Development"); st.rerun()

    if role in ("admin","super_admin"):
        st.markdown("<hr style='margin:0.5rem 0;border-color:rgba(240,192,48,0.2);'>", unsafe_allow_html=True)
        if st.button("Administration", use_container_width=True):
            st.session_state.page = "Administration"; update_cookie_page("Administration"); st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<br>" * 6, unsafe_allow_html=True)
    st.markdown("<hr style='margin:0.3rem 0;border-color:rgba(240,192,48,0.2);'>", unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:0.75rem;text-align:center;margin-bottom:4px;color:#7a93c0;font-family:Barlow Condensed,sans-serif;letter-spacing:1px;">' +
        f'Logged in as {st.session_state.username}</div>',
        unsafe_allow_html=True)
    if st.button("Logout", use_container_width=True):
        logout()

# ── Handle org query param ────────────────────────────────────────────────────
_org_p = st.query_params.get("org", "")
if _org_p and st.session_state.role == "super_admin":
    if _org_p == "all":
        st.session_state.sa_view_all = True
        st.session_state.sa_tenant_id = None
        st.session_state.tenant_name = "All Units"
    else:
        try:
            _oid = int(_org_p)
            _ot = get_tenant(_oid)
            if _ot:
                st.session_state.sa_view_all = False
                st.session_state.sa_tenant_id = _oid
                st.session_state.tenant_name = _ot["name"]
        except Exception:
            pass
    del st.query_params["org"]
    st.rerun()

# ── Active tenant ─────────────────────────────────────────────────────────────
if role == "super_admin":
    st.session_state.active_tenant_id = None if st.session_state.sa_view_all else st.session_state.sa_tenant_id
else:
    st.session_state.active_tenant_id = st.session_state.tenant_id

# Keep sidebar unit display in sync
if role == "super_admin":
    if st.session_state.sa_view_all:
        st.session_state.tenant_name = "All Units"
    elif st.session_state.sa_tenant_id and not st.session_state.tenant_name:
        from database import get_tenant as _gt
        _t = _gt(st.session_state.sa_tenant_id)
        if _t: st.session_state.tenant_name = _t["name"]

# ── Route ─────────────────────────────────────────────────────────────────────
if st.session_state.page == "Administration" and role in ("admin","super_admin"):
    _admin.run()
else:
    _dash.run()
