"""
database.py — Supabase connection and all query functions.
"""

from supabase import create_client, Client
import bcrypt
import secrets
from datetime import datetime, timezone, timedelta
import re


def _parse_dt(s: str) -> datetime:
    """Parse any ISO datetime string Supabase returns, regardless of format."""
    if not s:
        return datetime.now(timezone.utc)
    # Remove trailing microseconds beyond 6 digits, fix timezone colon
    s = re.sub(r'(\.\d{6})\d+', r'\1', s)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Last resort: strip timezone and assume UTC
        dt = datetime.fromisoformat(s[:19]).replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

SUPABASE_URL = "https://hjxxwposxhsreqphfzfa.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhqeHh3cG9zeGhzcmVxcGhmemZhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY5MTA4MjUsImV4cCI6MjA5MjQ4NjgyNX0.z9XkGdkfg7QX8QYAHS7-UWu0lTajW43mZlN73DnTUyQ"

SESSION_EXPIRY_HOURS = 4
INACTIVITY_MINUTES   = 30
LOCKOUT_AFTER_CONSEC = 3
DISABLE_AFTER_DAILY  = 5
LOCKOUT_MINUTES      = 15

def db() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Password helpers ──────────────────────────────────────────────────────────
def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_pw(plain: str, stored: str) -> bool:
    try:
        # Normalise hash — ensure it starts with exactly one $
        h = stored.lstrip("$")
        h = "$" + h
        if h.startswith("$2"):
            return bcrypt.checkpw(plain.encode(), h.encode())
        import hashlib
        return hashlib.sha256(plain.encode()).hexdigest() == stored
    except Exception:
        return False

def needs_rehash(stored: str) -> bool:
    h = "$" + stored.lstrip("$")
    return not h.startswith("$2")

# ── Tenant functions ──────────────────────────────────────────────────────────
def get_all_tenants():
    res = db().table("tenants").select("*").order("name").execute()
    return res.data or []

def get_tenant(tenant_id: int):
    res = db().table("tenants").select("*").eq("id", tenant_id).single().execute()
    return res.data

def get_tenant_by_name(name: str):
    res = db().table("tenants").select("*").eq("name", name).execute()
    return res.data[0] if res.data else None

def create_tenant(name: str, short_code: str):
    res = db().table("tenants").insert({"name": name, "short_code": short_code}).execute()
    return res.data[0] if res.data else None

def update_tenant(tenant_id: int, data: dict):
    db().table("tenants").update(data).eq("id", tenant_id).execute()

def delete_tenant(tenant_id: int):
    db().table("tenants").delete().eq("id", tenant_id).execute()

# ── Flight functions ──────────────────────────────────────────────────────────
# The `flights` table stores the canonical PER-TENANT list of selectable
# flight options that appear in Unit/Flight dropdowns across the dashboard
# (Select Unit/Flight cascade, Add/Edit Member form, Create Account form,
# Enlisted Bench filter, etc.). It is created by `migration_flights.sql`.
#
# IMPORTANT: this table is NOT the source of truth for members' actual
# flight assignments. The `members.flight` text column is what the user
# typed into the Add Member form for that specific member. Renaming or
# deleting a flight here does NOT cascade to member rows — the canonical
# option list and the actual member data are intentionally independent.
# Names must be unique within a tenant; different tenants can both have
# an "Alpha" flight without conflicting.
def get_flights_for_tenant(tenant_id: int):
    """Return all flights for a tenant, ordered by name."""
    res = db().table("flights").select("*").eq("tenant_id", tenant_id).order("name").execute()
    return res.data or []

def get_flight(flight_id: int):
    res = db().table("flights").select("*").eq("id", flight_id).single().execute()
    return res.data

def create_flight(tenant_id: int, name: str):
    """Insert a new flight under a tenant. The DB unique constraint
    (tenant_id, name) prevents duplicates within the same tenant — Supabase
    will raise on conflict."""
    res = db().table("flights").insert({
        "tenant_id": tenant_id,
        "name":      name,
    }).execute()
    return res.data[0] if res.data else None

def update_flight(flight_id: int, data: dict):
    """Update a flight (typically just renaming the option)."""
    db().table("flights").update(data).eq("id", flight_id).execute()

def delete_flight(flight_id: int):
    """Remove a flight from the canonical option list. Does NOT touch
    members.flight — members previously assigned this flight name keep
    that string on their record."""
    db().table("flights").delete().eq("id", flight_id).execute()

# ── User functions ────────────────────────────────────────────────────────────
def get_user(username: str):
    res = db().table("users").select("*").eq("username", username).execute()
    return res.data[0] if res.data else None

def get_user_by_id(user_id: int):
    res = db().table("users").select("*").eq("id", user_id).single().execute()
    return res.data

def get_users_for_tenant(tenant_id: int):
    res = db().table("users").select("*").eq("tenant_id", tenant_id).order("username").execute()
    return res.data or []

def get_all_users():
    res = db().table("users").select("*, tenants(name)").order("username").execute()
    return res.data or []

def create_user(data: dict):
    res = db().table("users").insert(data).execute()
    return res.data[0] if res.data else None

def update_user(user_id: int, data: dict):
    db().table("users").update(data).eq("id", user_id).execute()

def delete_user(user_id: int):
    db().table("users").delete().eq("id", user_id).execute()

def check_lockout(username: str):
    u = get_user(username)
    if not u:
        return False, ""
    if u.get("disabled"):
        return True, "This account has been disabled. Please contact an administrator."
    lockout_until = u.get("lockout_until")
    if lockout_until:
        until_dt = _parse_dt(lockout_until)
        now_dt   = datetime.now(timezone.utc)
        if until_dt.tzinfo is None:
            until_dt = until_dt.replace(tzinfo=timezone.utc)
        if now_dt < until_dt:
            remaining = int((until_dt - now_dt).total_seconds() // 60) + 1
            return True, f"Account temporarily locked. Try again in {remaining} minute(s)."
        else:
            db().table("users").update({
                "lockout_until": None, "consec_failures": 0
            }).eq("username", username).execute()
    return False, ""

def record_failed_attempt(username: str):
    u = get_user(username)
    if not u:
        return
    now   = datetime.now(timezone.utc)
    today = now.date().isoformat()
    daily_failures  = u.get("daily_failures", 0)
    daily_fail_date = u.get("daily_fail_date", "")
    if daily_fail_date != today:
        daily_failures  = 0
        daily_fail_date = today
    daily_failures  += 1
    consec_failures  = u.get("consec_failures", 0) + 1
    update_data = {
        "daily_failures":  daily_failures,
        "daily_fail_date": daily_fail_date,
        "consec_failures": consec_failures,
    }
    if daily_failures >= DISABLE_AFTER_DAILY:
        update_data["disabled"]        = True
        update_data["lockout_until"]   = None
        update_data["consec_failures"] = 0
    elif consec_failures >= LOCKOUT_AFTER_CONSEC:
        until = (now + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
        update_data["lockout_until"]   = until
        update_data["consec_failures"] = 0
    db().table("users").update(update_data).eq("username", username).execute()

def record_success(username: str):
    db().table("users").update({
        "consec_failures": 0, "lockout_until": None
    }).eq("username", username).execute()

def update_password(user_id: int, new_password: str, old_hash: str):
    history = db().table("users").select("password_history").eq("id", user_id).single().execute()
    hist = history.data.get("password_history") or []
    if old_hash:
        hist = ([old_hash] + hist)[:3]
    new_hash = hash_pw(new_password)
    db().table("users").update({
        "password":         new_hash,
        "password_history": hist
    }).eq("id", user_id).execute()

def check_password_history(user_id: int, new_password: str) -> bool:
    res = db().table("users").select("password_history").eq("id", user_id).single().execute()
    hist = res.data.get("password_history") or []
    return any(verify_pw(new_password, h) for h in hist)

# ── Session functions ─────────────────────────────────────────────────────────
def create_session(user_id: int, ip: str) -> str:
    token   = secrets.token_hex(32)
    now     = datetime.now(timezone.utc)
    expires = (now + timedelta(hours=SESSION_EXPIRY_HOURS)).isoformat()
    # Prune expired sessions
    db().table("sessions").delete().lt("expires_at", now.isoformat()).execute()
    db().table("sessions").insert({
        "user_id":     user_id,
        "token":       token,
        "ip_address":  ip,
        "expires_at":  expires,
        "last_active": now.isoformat(),
    }).execute()
    return token

def resolve_session(token: str, ip: str):
    if not token:
        return None
    res = db().table("sessions").select("*, users(*)").eq("token", token).execute()
    if not res.data:
        return None
    session = res.data[0]
    now = datetime.now(timezone.utc)

    # Check expiry
    expires = _parse_dt(session["expires_at"])
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if now > expires:
        db().table("sessions").delete().eq("token", token).execute()
        return None

    # Check inactivity
    last_active = _parse_dt(session["last_active"])
    if last_active.tzinfo is None:
        last_active = last_active.replace(tzinfo=timezone.utc)
    if (now - last_active).total_seconds() / 60 > INACTIVITY_MINUTES:
        db().table("sessions").delete().eq("token", token).execute()
        return None

    # Check IP
    stored_ip = session.get("ip_address", "unknown")
    if stored_ip != "unknown" and ip != "unknown" and stored_ip != ip:
        return None

    # Refresh last_active
    db().table("sessions").update({"last_active": now.isoformat()}).eq("token", token).execute()
    return session["users"]

def delete_session(token: str):
    db().table("sessions").delete().eq("token", token).execute()

# ── Member functions ──────────────────────────────────────────────────────────
def get_members(tenant_id: int):
    res = db().table("members").select("*").eq("tenant_id", tenant_id).execute()
    return res.data or []

def get_all_members():
    res = db().table("members").select("*, tenants(name)").execute()
    return res.data or []

def create_member(data: dict):
    res = db().table("members").insert(data).execute()
    return res.data[0] if res.data else None

def update_member(member_id: int, data: dict):
    db().table("members").update(data).eq("id", member_id).execute()

def delete_member(member_id: int):
    db().table("members").delete().eq("id", member_id).execute()


# ── Stratification persistence ────────────────────────────────────────────────
# Last-3 retention: when a 4th upload comes in, the oldest is deleted (cascade
# wipes its strat_records too).

def list_strat_uploads(limit: int = 3):
    """Return the most-recent `limit` strat uploads, newest first.
    Each row: {id, file_name, uploaded_at, uploaded_by, scope}."""
    res = (
        db().table("strat_uploads")
        .select("*")
        .order("uploaded_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def get_latest_strat_upload():
    """Return the newest upload row, or None if there are no uploads yet."""
    rows = list_strat_uploads(limit=1)
    return rows[0] if rows else None


def get_strat_records(upload_id: int):
    """Return all member-level records for a given upload."""
    res = (
        db().table("strat_records")
        .select("*")
        .eq("upload_id", upload_id)
        .execute()
    )
    return res.data or []


def create_strat_upload(file_name: str, uploaded_by: int, records: list,
                        retain: int = 3) -> int:
    """Persist a new GLOBAL strat upload + its parsed records, then prune
    older uploads down to `retain` total. Returns the new upload_id.

    `records` should be a list of dicts with the strat_records column names
    (see add_strat_and_bench_tables.sql for the schema).
    """
    # 1. Insert the upload metadata row.
    up_payload = {
        "file_name":   file_name,
        "uploaded_by": uploaded_by,
        "scope":       "global",
    }
    res = db().table("strat_uploads").insert(up_payload).execute()
    upload_id = res.data[0]["id"]

    # 2. Bulk-insert the records, tagging each with the new upload_id.
    if records:
        payload = []
        for r in records:
            row = dict(r)
            row["upload_id"] = upload_id
            payload.append(row)
        # Supabase Python client supports list-insert; chunk in batches of
        # 500 to avoid hitting payload-size limits on large rosters.
        BATCH = 500
        for i in range(0, len(payload), BATCH):
            db().table("strat_records").insert(payload[i:i+BATCH]).execute()

    # 3. Prune older uploads beyond `retain`. Cascade wipes their records.
    all_uploads = (
        db().table("strat_uploads")
        .select("id")
        .order("uploaded_at", desc=True)
        .execute()
    ).data or []
    if len(all_uploads) > retain:
        ids_to_delete = [u["id"] for u in all_uploads[retain:]]
        for uid in ids_to_delete:
            db().table("strat_uploads").delete().eq("id", uid).execute()

    return upload_id


def delete_strat_upload(upload_id: int):
    """Manually delete a specific upload (and cascade its records)."""
    db().table("strat_uploads").delete().eq("id", upload_id).execute()


# ── Bench layout (new schema) ─────────────────────────────────────────────────
# Saved layout = list of dicts with explicit member_db_id, tier_rank,
# position_in_tier, manually_placed. tenant_id may be None for super-admin
# "All Units" scope. flight=None means unit-level scope.

def get_bench_layout(tenant_id, flight=None) -> list:
    """Return all saved bench-layout rows for a (tenant, flight) scope."""
    q = db().table("bench_layouts").select("*")
    # Supabase's .eq doesn't accept None — build the filter chain conditionally.
    if tenant_id is None:
        q = q.is_("tenant_id", "null")
    else:
        q = q.eq("tenant_id", tenant_id)
    if flight is None:
        q = q.is_("flight", "null")
    else:
        q = q.eq("flight", flight)
    res = q.execute()
    return res.data or []


def save_bench_layout(tenant_id, flight, rows: list, modified_by: int):
    """Replace the saved bench layout for a (tenant, flight) scope.

    `rows` is a list of dicts with keys:
      member_db_id, tier_rank, position_in_tier, manually_placed
    Auto-placed members (manually_placed=False) generally don't need a row,
    but we accept them too — saves are idempotent.
    """
    # 1. Wipe existing rows in this scope.
    q = db().table("bench_layouts").delete()
    if tenant_id is None:
        q = q.is_("tenant_id", "null")
    else:
        q = q.eq("tenant_id", tenant_id)
    if flight is None:
        q = q.is_("flight", "null")
    else:
        q = q.eq("flight", flight)
    q.execute()

    # 2. Insert new rows.
    if not rows:
        return
    now_iso = datetime.now(timezone.utc).isoformat()
    payload = []
    for r in rows:
        payload.append({
            "tenant_id":        tenant_id,
            "flight":           flight,
            "member_db_id":     r["member_db_id"],
            "tier_rank":        r["tier_rank"],
            "position_in_tier": int(r.get("position_in_tier", 0)),
            "manually_placed":  bool(r.get("manually_placed", False)),
            "last_modified_by": modified_by,
            "last_modified_at": now_iso,
        })
    BATCH = 500
    for i in range(0, len(payload), BATCH):
        db().table("bench_layouts").insert(payload[i:i+BATCH]).execute()


def reset_bench_layout(tenant_id, flight=None):
    """Wipe the saved bench layout for a scope (rolls back to auto-placement)."""
    q = db().table("bench_layouts").delete()
    if tenant_id is None:
        q = q.is_("tenant_id", "null")
    else:
        q = q.eq("tenant_id", tenant_id)
    if flight is None:
        q = q.is_("flight", "null")
    else:
        q = q.eq("flight", flight)
    q.execute()


def get_bench_last_modified(tenant_id, flight=None):
    """Return (timestamp, user_id) of the most recent save in this scope, or
    (None, None) if no rows exist."""
    q = (
        db().table("bench_layouts")
        .select("last_modified_at, last_modified_by")
        .order("last_modified_at", desc=True)
        .limit(1)
    )
    if tenant_id is None:
        q = q.is_("tenant_id", "null")
    else:
        q = q.eq("tenant_id", tenant_id)
    if flight is None:
        q = q.is_("flight", "null")
    else:
        q = q.eq("flight", flight)
    rows = (q.execute().data or [])
    if not rows:
        return None, None
    return rows[0]["last_modified_at"], rows[0]["last_modified_by"]
