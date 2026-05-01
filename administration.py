"""
administration.py — Account and tenant management.
Supports super_admin (all tenants) and admin (own tenant) roles.
"""

import re, json
import streamlit as st
from database import (
    get_users_for_tenant, get_all_users, get_user, get_user_by_id,
    create_user, update_user, delete_user,
    update_password, check_password_history,
    get_all_tenants, get_tenant, create_tenant, update_tenant, delete_tenant,
    get_flights_for_tenant, get_flight, create_flight, update_flight, delete_flight,
    hash_pw, verify_pw,
    LOCKOUT_AFTER_CONSEC, DISABLE_AFTER_DAILY,
)
from datetime import datetime, timezone

RANK_ORDER = ["Amn","A1C","SrA","SSgt","TSgt","MSgt","SMSgt","CMSgt"]
TITLE_OPTIONS = [
    "", "Commander", "SEL", "First Sergeant", "Flight Commander",
    "Flight Chief", "Supervisor", "Other"
]
BENCH_VIEW_TITLES = {"Commander","SEL","Senior Enlisted Leader","First Sergeant","Flight Commander","Flight Chief"}
PASSWORD_HINT = "At least 12 characters, 2 numbers, 2 special characters."

def validate_password(password):
    errors = []
    if len(password) < 12: errors.append("At least 12 characters.")
    if len(re.findall(r"\d", password)) < 2: errors.append("At least 2 numbers.")
    if len(re.findall(r"[^a-zA-Z0-9]", password)) < 2: errors.append("At least 2 special characters.")
    return errors

def _parse_utc(s):
    if not s: return None
    try:
        dt = datetime.fromisoformat(str(s))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None

def _get_css():
    return """<style>
.adm-table{width:100%;border-collapse:collapse;font-size:0.95rem;}
.adm-table th{font-weight:700;padding:4px 12px 8px 4px;text-align:left;border-bottom:2px solid rgba(128,128,128,0.25);}
.adm-table td{padding:7px 12px 7px 4px;vertical-align:middle;}
.adm-table tr{border-bottom:1px solid rgba(128,128,128,0.1);}
[data-testid="stButton"] button[kind="primary"]{display:flex!important;align-items:center!important;justify-content:center!important;line-height:1!important;}
</style>"""

def run():
    st.markdown(_get_css(), unsafe_allow_html=True)
    role         = st.session_state.get("role","user")
    current_user = st.session_state.get("username","")
    my_tenant_id = st.session_state.get("tenant_id")

    st.markdown("# Administration")

    for k in ["pending_delete","pending_edit","pending_lock","add_account_open",
              "pending_tenant_edit","pending_tenant_delete","add_tenant_open",
              "expanded_tenant_flights","pending_flight_edit","pending_flight_delete",
              "add_flight_open"]:
        if k not in st.session_state:
            # Boolean toggles default to False; everything else (pending ids
            # like "edit user X" or "delete tenant Y") defaults to None.
            if k in ("add_account_open", "add_tenant_open", "add_flight_open"):
                st.session_state[k] = False
            else:
                st.session_state[k] = None

    # ── Super admin: tenant + flight management ──────────────────────────────
    if role == "super_admin":
        st.subheader("Units / Tenants")

        tenants = get_all_tenants()

        # Header row for the units table.
        unit_col_w = [3, 2, 1.2, 1, 1]
        hcols = st.columns(unit_col_w)
        for hc, lbl in zip(hcols, ["**Unit Name**", "**Short Code**",
                                    "**Flights**", "**Edit**", "**Delete**"]):
            hc.markdown(lbl)
        st.markdown(
            "<div style='border-bottom:2px solid rgba(128,128,128,0.25);"
            "margin:0 0 4px 0;'></div>",
            unsafe_allow_html=True,
        )

        for t in tenants:
            tid = t["id"]

            # ── Inline EDIT row ────────────────────────────────────────────
            if st.session_state.pending_tenant_edit == tid:
                ec1, ec2, ec3, ec4 = st.columns([3, 2, 1, 1])
                # Inputs read their value purely from session_state — the
                # session_state keys were seeded by the Edit button handler
                # below. Passing `value=` here in addition to `key=` is the
                # canonical Streamlit anti-pattern and would either trigger a
                # warning or silently keep stale input across edit sessions.
                e_name = ec1.text_input("Unit Name",
                                        key=f"et_name_{tid}",
                                        label_visibility="collapsed")
                e_code = ec2.text_input("Short Code",
                                        key=f"et_code_{tid}",
                                        label_visibility="collapsed")
                with ec3:
                    if st.button("Save", type="primary", key=f"et_save_{tid}"):
                        if not e_name.strip() or not e_code.strip():
                            st.error("Both fields required.")
                        else:
                            update_tenant(tid, {
                                "name":       e_name.strip(),
                                "short_code": e_code.strip().upper(),
                            })
                            st.session_state.pending_tenant_edit = None
                            # Drop the input session_state so a future edit on
                            # this same tenant re-seeds from the (now updated)
                            # DB values.
                            st.session_state.pop(f"et_name_{tid}", None)
                            st.session_state.pop(f"et_code_{tid}", None)
                            st.success(f"Unit '{e_name}' updated.")
                            st.rerun()
                with ec4:
                    if st.button("Cancel", type="primary", key=f"et_cancel_{tid}"):
                        st.session_state.pending_tenant_edit = None
                        # Same cleanup on Cancel — without this, typed-but-
                        # not-saved input would persist into the next edit
                        # session for this tenant.
                        st.session_state.pop(f"et_name_{tid}", None)
                        st.session_state.pop(f"et_code_{tid}", None)
                        st.rerun()
                continue

            # ── Inline DELETE confirmation ────────────────────────────────
            if st.session_state.pending_tenant_delete == tid:
                st.markdown(
                    f"<div style='background:rgba(201,31,44,0.08);"
                    f"border-left:3px solid #C91F2C;padding:8px 14px;"
                    f"margin:4px 0 8px;border-radius:4px;font-size:0.9rem;'>"
                    f"Delete <b>{t['name']}</b>? All members, users, and flights "
                    f"under this unit will be deleted. This cannot be undone.</div>",
                    unsafe_allow_html=True,
                )
                cc1, cc2, _ = st.columns([1, 1, 8])
                with cc1:
                    if st.button("Confirm Delete", type="primary",
                                 key=f"dt_confirm_{tid}"):
                        delete_tenant(tid)
                        st.session_state.pending_tenant_delete = None
                        st.success(f"Unit '{t['name']}' deleted.")
                        st.rerun()
                with cc2:
                    if st.button("Cancel", type="primary",
                                 key=f"dt_cancel_{tid}"):
                        st.session_state.pending_tenant_delete = None
                        st.rerun()
                continue

            # ── Standard display row ──────────────────────────────────────
            rcols = st.columns(unit_col_w)
            rcols[0].write(t["name"])
            rcols[1].write(t["short_code"])

            # Flights button — toggles a sub-table showing this tenant's
            # canonical flight options. The button label includes the count
            # so admins can see at a glance which units have flights set up.
            try:
                _flight_count = len(get_flights_for_tenant(tid))
            except Exception:
                _flight_count = 0
            _expand_label = ("Hide" if st.session_state.expanded_tenant_flights == tid
                             else f"View ({_flight_count})")
            with rcols[2]:
                if st.button(_expand_label, type="primary", key=f"flt_toggle_{tid}"):
                    if st.session_state.expanded_tenant_flights == tid:
                        st.session_state.expanded_tenant_flights = None
                    else:
                        st.session_state.expanded_tenant_flights = tid
                        # Reset flight pendings when switching units
                        st.session_state.pending_flight_edit = None
                        st.session_state.pending_flight_delete = None
                        st.session_state.add_flight_open = False
                    st.rerun()

            with rcols[3]:
                if st.button("Edit", type="primary", key=f"et_btn_{tid}"):
                    # Pre-seed the input session_state with the canonical DB
                    # values so the inline edit form reliably shows the CURRENT
                    # data — not whatever the user typed last time before
                    # cancelling. Without this, the text_input keys
                    # (et_name_<tid> / et_code_<tid>) stay populated with stale
                    # input across edit sessions.
                    st.session_state[f"et_name_{tid}"] = t["name"]
                    st.session_state[f"et_code_{tid}"] = t["short_code"]
                    st.session_state.pending_tenant_edit = tid
                    # Clear any other pending state so we don't end up with two
                    # prompts open at once (e.g. a delete confirmation that
                    # was left open on a different unit).
                    st.session_state.pending_tenant_delete = None
                    st.session_state.pending_flight_edit = None
                    st.session_state.pending_flight_delete = None
                    st.session_state.add_flight_open = False
                    st.session_state.add_tenant_open = False
                    st.rerun()
            with rcols[4]:
                if st.button("✕", type="primary", key=f"dt_btn_{tid}",
                             help=f"Delete {t['name']}"):
                    st.session_state.pending_tenant_delete = tid
                    # Same reasoning as above — clear other pendings.
                    st.session_state.pending_tenant_edit = None
                    st.session_state.pending_flight_edit = None
                    st.session_state.pending_flight_delete = None
                    st.session_state.add_flight_open = False
                    st.session_state.add_tenant_open = False
                    st.rerun()

            # ── Expanded: per-tenant Flights management table ──────────────
            if st.session_state.expanded_tenant_flights == tid:
                # Use a plain Streamlit container instead of trying to wrap
                # the inner widgets with a `<div>` opened in one st.markdown
                # call and closed in another — Streamlit renders each
                # st.markdown as its own element, so the open/close pair was
                # never actually wrapping anything (and the background/
                # border-left styling never landed where it should). The
                # section header below is enough of a visual cue that the
                # following block is a sub-table.
                with st.container():
                    st.markdown(f"**{t['name']} — Flights**  "
                                f"<span style='font-size:0.78rem;opacity:0.65;'>"
                                f"Canonical list of selectable flight options for "
                                f"this unit. Members keep their own flight "
                                f"assignments; this list controls what appears in "
                                f"flight dropdowns across the dashboard."
                                f"</span>", unsafe_allow_html=True)

                    flights = get_flights_for_tenant(tid)

                    # Flights table header
                    flt_col_w = [4, 1, 1]
                    fhcols = st.columns(flt_col_w)
                    for hc, lbl in zip(fhcols, ["**Flight Name**", "**Edit**", "**Delete**"]):
                        hc.markdown(lbl)
                    if flights:
                        st.markdown(
                            "<div style='border-bottom:1px solid rgba(128,128,128,0.2);"
                            "margin:0 0 4px 0;'></div>",
                            unsafe_allow_html=True,
                        )

                    if not flights:
                        st.markdown(
                            "<div style='font-size:0.85rem;opacity:0.65;"
                            "padding:6px 0 4px 0;'>No flights configured. "
                            "Add the first one below.</div>",
                            unsafe_allow_html=True,
                        )

                    for f in flights:
                        fid = f["id"]

                        # Inline EDIT row
                        if st.session_state.pending_flight_edit == fid:
                            fc1, fc2, fc3 = st.columns([4, 1, 1])
                            # See the matching comment on the tenant edit row —
                            # session_state is pre-seeded by the Edit button so
                            # we don't pass `value=` here.
                            f_new = fc1.text_input("Flight Name",
                                                   key=f"ef_name_{fid}",
                                                   label_visibility="collapsed")
                            with fc2:
                                if st.button("Save", type="primary",
                                             key=f"ef_save_{fid}"):
                                    if not f_new.strip():
                                        st.error("Flight name required.")
                                    else:
                                        try:
                                            update_flight(fid, {"name": f_new.strip()})
                                            st.session_state.pending_flight_edit = None
                                            st.session_state.pop(f"ef_name_{fid}", None)
                                            st.success(f"Flight renamed to '{f_new.strip()}'.")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Could not rename: {e}")
                            with fc3:
                                if st.button("Cancel", type="primary",
                                             key=f"ef_cancel_{fid}"):
                                    st.session_state.pending_flight_edit = None
                                    st.session_state.pop(f"ef_name_{fid}", None)
                                    st.rerun()
                            continue

                        # Inline DELETE confirmation
                        if st.session_state.pending_flight_delete == fid:
                            st.markdown(
                                f"<div style='background:rgba(201,31,44,0.08);"
                                f"border-left:3px solid #C91F2C;padding:8px 14px;"
                                f"margin:4px 0 8px;border-radius:4px;font-size:0.85rem;'>"
                                f"Remove flight option <b>{f['name']}</b> from the "
                                f"dropdown? Members currently assigned to this flight "
                                f"keep their assignment; only the option list is changed."
                                f"</div>",
                                unsafe_allow_html=True,
                            )
                            dc1, dc2, _ = st.columns([1, 1, 6])
                            with dc1:
                                if st.button("Confirm", type="primary",
                                             key=f"df_confirm_{fid}"):
                                    delete_flight(fid)
                                    st.session_state.pending_flight_delete = None
                                    st.success(f"Flight '{f['name']}' removed from option list.")
                                    st.rerun()
                            with dc2:
                                if st.button("Cancel", type="primary",
                                             key=f"df_cancel_{fid}"):
                                    st.session_state.pending_flight_delete = None
                                    st.rerun()
                            continue

                        # Standard display row
                        fcols = st.columns(flt_col_w)
                        fcols[0].write(f["name"])
                        with fcols[1]:
                            if st.button("Edit", type="primary",
                                         key=f"ef_btn_{fid}"):
                                # Pre-seed input from current DB value so the
                                # edit form opens with fresh data, not whatever
                                # was typed in a prior canceled edit.
                                st.session_state[f"ef_name_{fid}"] = f["name"]
                                st.session_state.pending_flight_edit = fid
                                # Don't allow a stale delete confirmation to
                                # also be open at the same time.
                                st.session_state.pending_flight_delete = None
                                st.session_state.add_flight_open = False
                                st.rerun()
                        with fcols[2]:
                            if st.button("✕", type="primary",
                                         key=f"df_btn_{fid}",
                                         help=f"Delete {f['name']}"):
                                st.session_state.pending_flight_delete = fid
                                st.session_state.pending_flight_edit = None
                                st.session_state.add_flight_open = False
                                st.rerun()

                    # Add Flight inline form
                    st.markdown(
                        "<div style='border-top:1px dashed rgba(128,128,128,0.25);"
                        "margin:6px 0 6px 0;'></div>",
                        unsafe_allow_html=True,
                    )
                    if not st.session_state.add_flight_open:
                        if st.button("+ Add Flight", type="primary",
                                     key=f"add_flt_open_{tid}"):
                            st.session_state.add_flight_open = True
                            # Don't leave a half-open flight edit / delete prompt
                            # sitting above the new Add Flight form.
                            st.session_state.pending_flight_edit = None
                            st.session_state.pending_flight_delete = None
                            st.rerun()
                    else:
                        afc1, afc2, afc3 = st.columns([4, 1, 1])
                        new_fname = afc1.text_input(
                            "New Flight Name",
                            key=f"new_flt_name_{tid}",
                            placeholder="e.g. Cyber Ops, Mission Defense, …",
                            label_visibility="collapsed",
                        )
                        with afc2:
                            if st.button("Add", type="primary",
                                         key=f"new_flt_save_{tid}"):
                                if not new_fname.strip():
                                    st.error("Flight name required.")
                                else:
                                    try:
                                        create_flight(tid, new_fname.strip())
                                        st.session_state.add_flight_open = False
                                        # Wipe the input so the next "+ Add Flight"
                                        # opens with an empty box, not the just-
                                        # saved name.
                                        st.session_state.pop(f"new_flt_name_{tid}", None)
                                        st.success(f"Flight '{new_fname.strip()}' added.")
                                        st.rerun()
                                    except Exception as e:
                                        # Most likely a duplicate (UNIQUE constraint).
                                        st.error(f"Could not add flight: {e}")
                        with afc3:
                            if st.button("Cancel", type="primary",
                                         key=f"new_flt_cancel_{tid}"):
                                st.session_state.add_flight_open = False
                                st.session_state.pop(f"new_flt_name_{tid}", None)
                                st.rerun()

        # ── Add Unit (inline form, toggled by + Add Unit button) ──────────
        st.markdown(
            "<div style='border-top:1px dashed rgba(128,128,128,0.3);"
            "margin:8px 0 8px 0;'></div>",
            unsafe_allow_html=True,
        )
        if not st.session_state.add_tenant_open:
            if st.button("+ Add Unit", type="primary", key="add_tenant_open_btn"):
                st.session_state.add_tenant_open = True
                # Don't leave a half-open edit / delete prompt sitting above
                # the Add Unit form.
                st.session_state.pending_tenant_edit = None
                st.session_state.pending_tenant_delete = None
                st.session_state.pending_flight_edit = None
                st.session_state.pending_flight_delete = None
                st.session_state.add_flight_open = False
                st.rerun()
        else:
            anc1, anc2, anc3, anc4 = st.columns([3, 2, 1, 1])
            n_name = anc1.text_input("New Unit Name",
                                     key="new_tenant_name",
                                     placeholder="e.g. 195 WG HQ",
                                     label_visibility="collapsed")
            n_code = anc2.text_input("Short Code",
                                     key="new_tenant_code",
                                     placeholder="e.g. 195WGHQ",
                                     label_visibility="collapsed")
            with anc3:
                if st.button("Add", type="primary", key="create_tenant_btn"):
                    if not n_name.strip() or not n_code.strip():
                        st.error("Both fields required.")
                    else:
                        try:
                            create_tenant(n_name.strip(), n_code.strip().upper())
                            st.session_state.add_tenant_open = False
                            # Reset inputs so reopening Add Unit gives an
                            # empty form, not the just-saved values.
                            st.session_state.pop("new_tenant_name", None)
                            st.session_state.pop("new_tenant_code", None)
                            st.success(f"Unit '{n_name.strip()}' created.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Could not create unit: {e}")
            with anc4:
                if st.button("Cancel", type="primary", key="cancel_create_tenant_btn"):
                    st.session_state.add_tenant_open = False
                    st.session_state.pop("new_tenant_name", None)
                    st.session_state.pop("new_tenant_code", None)
                    st.rerun()

        st.markdown("---")

    # ── Accounts table ────────────────────────────────────────────────────────
    st.subheader("Accounts")
    if role == "super_admin":
        users = get_all_users()
    else:
        users = get_users_for_tenant(my_tenant_id) if my_tenant_id else []

    if not users:
        st.info("No accounts found.")
    else:
        COL_W = [2, 2, 2, 1.5, 1.5, 1.8, 1.2, 1.5, 2.2]
        hcols = st.columns(COL_W)
        for hc, lbl in zip(hcols, ["**Username**","**First Name**","**Last Name**",
                                    "**Rank**","**Flight**","**Title**","**Role**","**Status**","**Actions**"]):
            hc.markdown(lbl)
        st.markdown("<hr style='margin:2px 0 6px 0;opacity:0.2;'>", unsafe_allow_html=True)

        for u in users:
            uname       = u["username"]
            uid         = u["id"]
            is_self     = (uname == current_user)
            is_disabled = u.get("disabled", False)
            lu_dt       = _parse_utc(u.get("lockout_until",""))
            is_locked   = bool(lu_dt and datetime.now(timezone.utc) < lu_dt)

            row = st.columns(COL_W)
            row[0].write(uname)
            row[1].write(u.get("first_name",""))
            row[2].write(u.get("last_name",""))
            row[3].write(u.get("rank",""))
            row[4].write(u.get("flight",""))
            row[5].write(u.get("title",""))
            row[6].write(u.get("role","user"))

            if is_disabled:
                row[7].markdown("<span style='color:#ee0055;font-weight:600;'>● Disabled</span>", unsafe_allow_html=True)
            elif is_locked:
                row[7].markdown("<span style='color:#ff9900;font-weight:600;'>● Locked</span>", unsafe_allow_html=True)
            else:
                row[7].markdown("<span style='color:#22dd22;'>● Active</span>", unsafe_allow_html=True)

            with row[8]:
                if is_self:
                    edit_clicked  = st.button("✎", key=f"adm_edit_{uid}", help="Edit my account", type="primary")
                    lock_clicked  = False
                    trash_clicked = False
                else:
                    lock_icon = "↺" if (is_locked or is_disabled) else "⊘"
                    c1, c2, c3 = st.columns(3)
                    edit_clicked  = c1.button("✎", key=f"adm_edit_{uid}", help="Edit", type="primary")
                    lock_clicked  = c2.button(lock_icon, key=f"adm_lock_{uid}", help="Disable/Enable", type="primary")
                    trash_clicked = c3.button("✕", key=f"adm_trash_{uid}", help="Delete", type="primary")

            if edit_clicked:
                st.session_state.pending_edit   = uid if st.session_state.pending_edit != uid else None
                st.session_state.pending_delete = None
                st.session_state.pending_lock   = None
                st.rerun()
            if lock_clicked:
                st.session_state.pending_lock   = uid if st.session_state.pending_lock != uid else None
                st.session_state.pending_edit   = None
                st.session_state.pending_delete = None
                st.rerun()
            if trash_clicked:
                st.session_state.pending_delete = uid if st.session_state.pending_delete != uid else None
                st.session_state.pending_edit   = None
                st.session_state.pending_lock   = None
                st.rerun()

            # Delete confirmation
            if st.session_state.pending_delete == uid:
                st.markdown(f"<div style='background:rgba(201,31,44,0.08);border-left:3px solid #C91F2C;padding:8px 14px;margin:4px 0 8px;border-radius:4px;font-size:0.9rem;'>Delete <b>{uname}</b>? Cannot be undone.</div>", unsafe_allow_html=True)
                dc1, dc2, _ = st.columns([1,1,8])
                with dc1:
                    if st.button("Delete", type="primary", key=f"confirm_del_{uid}"):
                        delete_user(uid)
                        st.session_state.pending_delete = None
                        st.success(f"Account '{uname}' deleted.")
                        st.rerun()
                with dc2:
                    if st.button("Cancel", type="primary", key=f"cancel_del_{uid}"):
                        st.session_state.pending_delete = None; st.rerun()

            # Lock / unlock
            if st.session_state.pending_lock == uid:
                if is_disabled:
                    st.markdown(f"<div style='background:rgba(74,102,172,0.10);border-left:3px solid #4A66AC;padding:8px 14px;margin:4px 0 8px;border-radius:4px;font-size:0.9rem;'>Re-enable <b>{uname}</b>?</div>", unsafe_allow_html=True)
                    lc1, lc2, _ = st.columns([1,1,8])
                    with lc1:
                        if st.button("Re-enable", type="primary", key=f"confirm_enable_{uid}"):
                            update_user(uid, {"disabled":False,"lockout_until":None,"consec_failures":0,"daily_failures":0,"daily_fail_date":""})
                            st.session_state.pending_lock = None
                            st.success(f"Account '{uname}' re-enabled."); st.rerun()
                    with lc2:
                        if st.button("Cancel", type="primary", key=f"cancel_enable_{uid}"):
                            st.session_state.pending_lock = None; st.rerun()
                elif is_locked:
                    st.markdown(f"<div style='background:rgba(74,102,172,0.10);border-left:3px solid #4A66AC;padding:8px 14px;margin:4px 0 8px;border-radius:4px;font-size:0.9rem;'>Unlock <b>{uname}</b>?</div>", unsafe_allow_html=True)
                    lc1, lc2, _ = st.columns([1,1,8])
                    with lc1:
                        if st.button("Unlock", type="primary", key=f"confirm_unlock_{uid}"):
                            update_user(uid, {"lockout_until":None,"consec_failures":0})
                            st.session_state.pending_lock = None
                            st.success(f"Account '{uname}' unlocked."); st.rerun()
                    with lc2:
                        if st.button("Cancel", type="primary", key=f"cancel_lock_{uid}"):
                            st.session_state.pending_lock = None; st.rerun()
                else:
                    st.markdown(f"<div style='background:rgba(201,31,44,0.08);border-left:3px solid #C91F2C;padding:8px 14px;margin:4px 0 8px;border-radius:4px;font-size:0.9rem;'>Disable <b>{uname}</b>?</div>", unsafe_allow_html=True)
                    lc1, lc2, _ = st.columns([1,1,8])
                    with lc1:
                        if st.button("Disable", type="primary", key=f"confirm_disable_{uid}"):
                            update_user(uid, {"disabled":True,"lockout_until":None,"consec_failures":0})
                            st.session_state.pending_lock = None
                            st.success(f"Account '{uname}' disabled."); st.rerun()
                    with lc2:
                        if st.button("Cancel", type="primary", key=f"cancel_disable_{uid}"):
                            st.session_state.pending_lock = None; st.rerun()

            # Edit form
            if st.session_state.pending_edit == uid:
                st.markdown("<div style='background:rgba(31,42,138,0.07);border-left:3px solid #4A66AC;padding:12px 14px;margin:4px 0 10px;border-radius:4px;'>", unsafe_allow_html=True)
                st.markdown(f"**Edit — {uname}**" + (" *(my account)*" if is_self else ""))
                ea, eb, ec, ed = st.columns(4)
                e_first  = ea.text_input("First Name", value=u.get("first_name",""), key=f"ef_{uid}")
                e_last   = eb.text_input("Last Name",  value=u.get("last_name",""),  key=f"el_{uid}")
                rank_opts = [""] + RANK_ORDER
                cur_rank  = u.get("rank","")
                e_rank   = ec.selectbox("Rank", rank_opts,
                                        index=rank_opts.index(cur_rank) if cur_rank in rank_opts else 0,
                                        format_func=lambda x: "-- Select --" if x=="" else x,
                                        key=f"er_{uid}")
                # Flight options come from the canonical flights table for
                # the user's tenant. Falls back to a small starter list if
                # the tenant has no flights configured yet, so the dropdown
                # isn't completely empty for a brand-new unit. The user's
                # current flight value is preserved in the option list even
                # if it's no longer in the canonical list (so we don't
                # silently lose their assignment when an admin removes a
                # flight option).
                _u_tid = u.get("tenant_id")
                _flt_rows = (get_flights_for_tenant(_u_tid)
                             if _u_tid is not None else [])
                _canon = [f["name"] for f in _flt_rows]
                cur_flight = u.get("flight","")
                if cur_flight and cur_flight not in _canon:
                    _canon = _canon + [cur_flight]
                flight_opts = [""] + _canon
                e_flight = ed.selectbox("Flight", flight_opts,
                                        index=flight_opts.index(cur_flight) if cur_flight in flight_opts else 0,
                                        format_func=lambda x: "-- Select --" if x=="" else x,
                                        key=f"efl_{uid}")
                cur_title = u.get("title","")
                if is_self:
                    et_col, _ = st.columns(2)
                    e_title  = et_col.selectbox("Title", TITLE_OPTIONS,
                                                index=TITLE_OPTIONS.index(cur_title) if cur_title in TITLE_OPTIONS else 0,
                                                key=f"eti_{uid}")
                    e_role   = u.get("role","user")
                    st.markdown("**Change Password**")
                    pw1, pw2, pw3 = st.columns(3)
                    e_cur_pw = pw1.text_input("Current Password", type="password", key=f"ecur_{uid}")
                    e_pw     = pw2.text_input("New Password",     type="password", key=f"epw_{uid}")
                    e_pw2    = pw3.text_input("Confirm New Password", type="password", key=f"epw2_{uid}")
                    pw2.markdown(f'<div style="font-size:0.75rem;opacity:0.55;margin-top:-8px;">{PASSWORD_HINT}</div>', unsafe_allow_html=True)
                    e_cur_pw2 = None
                else:
                    et_col, ef_col, eg_col = st.columns(3)
                    e_title  = et_col.selectbox("Title", TITLE_OPTIONS,
                                                index=TITLE_OPTIONS.index(cur_title) if cur_title in TITLE_OPTIONS else 0,
                                                key=f"eti_{uid}")
                    role_opts = ["user","admin"] if role != "super_admin" else ["user","admin","super_admin"]
                    e_role   = ef_col.selectbox("Role", role_opts,
                                                index=role_opts.index(u.get("role","user")) if u.get("role","user") in role_opts else 0,
                                                key=f"ero_{uid}")
                    e_pw     = eg_col.text_input("New Password (blank = no change)", type="password", key=f"epw_{uid}")
                    eg_col.markdown(f'<div style="font-size:0.78rem;opacity:0.65;margin-top:-8px;">{PASSWORD_HINT}</div>', unsafe_allow_html=True)
                    e_cur_pw = None; e_pw2 = None

                # Tenant assignment for super admin editing others
                if role == "super_admin" and not is_self:
                    all_tenants = get_all_tenants()
                    tenant_opts = [(None,"-- None (Super Admin) --")] + [(t["id"],t["name"]) for t in all_tenants]
                    cur_tid     = u.get("tenant_id")
                    cur_idx     = next((i for i,(tid,_) in enumerate(tenant_opts) if tid==cur_tid), 0)
                    sel_tenant  = st.selectbox("Unit", [n for _,n in tenant_opts], index=cur_idx, key=f"etenant_{uid}")
                    e_tenant_id = next((tid for tid,n in tenant_opts if n==sel_tenant), None)
                else:
                    e_tenant_id = u.get("tenant_id")

                sc1, sc2, _ = st.columns([1,1,8])
                with sc1:
                    if st.button("Save", type="primary", key=f"save_edit_{uid}"):
                        upd = {"first_name":e_first.strip(),"last_name":e_last.strip(),
                               "rank":e_rank,"flight":e_flight,"title":e_title,
                               "role":e_role,"tenant_id":e_tenant_id}
                        if e_pw and e_pw.strip():
                            if is_self:
                                if not verify_pw(e_cur_pw, u["password"]):
                                    st.error("Current password incorrect."); st.stop()
                                if e_pw != e_pw2:
                                    st.error("Passwords do not match."); st.stop()
                            pw_errs = validate_password(e_pw.strip())
                            if pw_errs:
                                for err in pw_errs: st.error(err)
                                st.stop()
                            if check_password_history(uid, e_pw.strip()):
                                st.error("Password used recently."); st.stop()
                            update_password(uid, e_pw.strip(), u["password"])
                        update_user(uid, upd)
                        st.session_state.pending_edit = None
                        st.success(f"Account '{uname}' updated."); st.rerun()
                with sc2:
                    if st.button("Cancel", type="primary", key=f"cancel_edit_{uid}"):
                        st.session_state.pending_edit = None; st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    # ── Create account ────────────────────────────────────────────────────────
    if st.button("+ Create Account", type="primary", key="open_create_acct_btn"):
        st.session_state.add_account_open = not st.session_state.add_account_open
        st.rerun()

    # When the form is collapsed, the page ended flush against the button —
    # leaving very little visual breathing room before the bottom of the
    # viewport / next section. Drop a fixed-height spacer so the button has
    # a comfortable margin below it whether or not the form is open.
    if not st.session_state.add_account_open:
        st.markdown(
            "<div style='height:80px;'></div>",
            unsafe_allow_html=True,
        )

    if st.session_state.add_account_open:
        st.markdown("**Create New Account**")

        c1, c2 = st.columns(2)
        new_username = c1.text_input("Username", key="new_acct_username")
        role_opts    = ["user","admin"] if role != "super_admin" else ["user","admin","super_admin"]
        new_role     = c2.selectbox("Role", role_opts, key="new_acct_role")

        c3, c4 = st.columns(2)
        new_password  = c3.text_input("Password", type="password", key="new_acct_pw")
        new_password2 = c4.text_input("Confirm Password", type="password", key="new_acct_pw2")
        c3.markdown(f'<div style="font-size:0.78rem;opacity:0.65;margin-top:-8px;">{PASSWORD_HINT}</div>', unsafe_allow_html=True)

        # Row 1 of the identity block: First Name, Last Name, Rank, Title.
        # Title was previously below on its own row; moving it next to Rank
        # makes the form fit on two rows total instead of three and keeps
        # related identity fields together.
        c5, c6, c7, c8 = st.columns(4)
        new_first  = c5.text_input("First Name", key="new_acct_first")
        new_last   = c6.text_input("Last Name",  key="new_acct_last")
        new_rank   = c7.selectbox("Rank", [""]+RANK_ORDER,
                                  format_func=lambda x: "-- Select --" if x=="" else x,
                                  key="new_acct_rank")
        new_title  = c8.selectbox("Title", TITLE_OPTIONS,
                                  format_func=lambda x: "-- Select --" if x=="" else x,
                                  key="new_acct_title")

        # Row 2 of the identity block: Unit on the left, Flight on the right.
        c9, c10 = st.columns(2)

        # Tenant (Unit) selection — sits on the LEFT of the row.
        if role == "super_admin":
            all_tenants  = get_all_tenants()
            tenant_opts  = [(None,"-- None (Super Admin) --")] + [(t["id"],t["name"]) for t in all_tenants]
            sel_tenant_n = c9.selectbox("Unit", [n for _,n in tenant_opts], key="new_acct_tenant")
            new_tenant_id = next((tid for tid,n in tenant_opts if n==sel_tenant_n), None)
        else:
            # Non-super-admin: tenant is fixed to their own; render a small
            # placeholder note in c9 so the row still feels balanced.
            new_tenant_id = my_tenant_id
            c9.markdown(
                "<div style='font-size:0.78rem;opacity:0.65;margin-top:24px;'>"
                "Unit fixed to your tenant.</div>",
                unsafe_allow_html=True,
            )

        # Flight options come from the canonical flights table for the
        # chosen Unit. If no Unit is selected (super-admin scope = None)
        # or the unit has no flights configured yet, the dropdown shows
        # only the "-- Select --" placeholder.
        if new_tenant_id is not None:
            _flt_rows = get_flights_for_tenant(new_tenant_id)
            _flight_opts = [""] + [f["name"] for f in _flt_rows]
        else:
            _flight_opts = [""]
        new_flight = c10.selectbox("Flight", _flight_opts,
                                   format_func=lambda x: "-- Select --" if x=="" else x,
                                   key="new_acct_flight")

        sc1, sc2, _ = st.columns([1,1,8])
        with sc1:
            if st.button("Save", type="primary", key="create_acct_btn"):
                errors = []
                if not new_username.strip(): errors.append("Username required.")
                elif get_user(new_username.strip()): errors.append(f"Username '{new_username}' already exists.")
                if not new_password: errors.append("Password required.")
                else:
                    errors += validate_password(new_password)
                    if new_password != new_password2: errors.append("Passwords do not match.")
                for err in errors: st.error(err)
                if not errors:
                    create_user({
                        "tenant_id":   new_tenant_id,
                        "username":    new_username.strip(),
                        "password":    hash_pw(new_password),
                        "role":        new_role,
                        "title":       new_title,
                        "first_name":  new_first.strip(),
                        "last_name":   new_last.strip(),
                        "rank":        new_rank,
                        "flight":      new_flight,
                        "disabled":    False,
                        "consec_failures": 0,
                        "daily_failures":  0,
                    })
                    st.session_state.add_account_open = False
                    st.success(f"Account '{new_username}' created."); st.rerun()
        with sc2:
            if st.button("Cancel", type="primary", key="cancel_create_acct_btn"):
                st.session_state.add_account_open = False; st.rerun()
