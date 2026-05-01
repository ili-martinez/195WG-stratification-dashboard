"""
data_generator.py
Generates 50 realistic fake members per tenant and inserts into Supabase.
Run once after schema.sql has been executed.

Usage:
    python3 data_generator.py
"""

import random
from datetime import date, timedelta
from database import db, get_all_tenants, hash_pw

random.seed(42)

RANKS        = ["Amn","A1C","SrA","SSgt","TSgt","MSgt","SMSgt"]
RANK_WEIGHTS = [8, 8, 10, 10, 10, 8, 6]
FLIGHTS      = ["Alpha","Bravo","Charlie","Delta"]

FIRST_NAMES = [
    "Alex","Jordan","Taylor","Morgan","Casey","Riley","Quinn","Avery","Parker","Drew",
    "Cameron","Skyler","Blake","Reese","Logan","Peyton","Hayden","Dakota","Finley","Jamie",
    "Chris","Sam","Jesse","Leslie","Pat","Terry","Robin","Dana","Kerry","Shawn",
    "Michael","James","Robert","David","John","William","Charles","Joseph","Thomas","Daniel",
    "Sarah","Jessica","Ashley","Emily","Amanda","Melissa","Stephanie","Nicole","Elizabeth","Jennifer",
    "Marcus","Brandon","Kevin","Justin","Tyler","Nathan","Aaron","Adam","Eric","Ryan",
    "Brianna","Kayla","Christina","Amber","Danielle","Rachel","Megan","Lauren","Brittany","Heather",
    "Damon","Iliana","Carlos","Maria","Ahmed","Fatima","Jin","Yuki","Andre","Natasha",
    "Victor","Diana","Felix","Gloria","Hugo","Iris","Jake","Karen","Lance","Mia",
]

LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Wilson","Martinez",
    "Anderson","Taylor","Thomas","Jackson","White","Harris","Martin","Thompson","Young","Robinson",
    "Clark","Lewis","Lee","Walker","Hall","Allen","Wright","Scott","Green","Baker",
    "Adams","Nelson","Carter","Mitchell","Perez","Roberts","Turner","Phillips","Campbell","Parker",
    "Evans","Edwards","Collins","Stewart","Morris","Rogers","Reed","Cook","Morgan","Bell",
    "Murphy","Bailey","Rivera","Cooper","Richardson","Cox","Ward","Peterson","Howard","Gray",
    "James","Watson","Brooks","Kelly","Sanders","Price","Bennett","Wood","Barnes","Ross",
    "Henderson","Coleman","Jenkins","Perry","Powell","Long","Patterson","Hughes","Flores","Washington",
    "Nguyen","Patel","Kim","Chen","Singh","Kumar","Ali","Hassan","Lopez","Gonzalez",
]

ASSIGNMENTS  = ["TDY/Exercise","Deployment","Mobilization","Stat Tour","ADOS","WIT Team","Group Staff","Wing Staff","Joint Tour"]
AWARDS       = ["NGB/MAJCOM Level Individual Award","Federal/State Decoration","Wing/Group/Squadron Airman of the Quarter or Year"]
PROF_ORGS    = ["Booster Club","Rising 6","Top 3","CAL EANGUS","Other"]
NOTES_SUP    = [
    "Maintain standards and continue development toward next milestone.",
    "Outstanding performer — prioritize for next assignment opportunity.",
    "Continue PME completion and leadership development.",
    "Recommended for accelerated promotion consideration.",
    "Focus on skill level upgrade and professional development.",
    "Strong contributor to unit mission and flight operations.",
    "Encourage pursuit of higher education and volunteer opportunities.",
]
NOTES_RAT = [
    "Focused on growth, PME completion, and assignment opportunities.",
    "Committed to mission and unit development.",
    "Working toward next promotion milestone.",
    "Actively engaged in professional military education.",
    "Seeking assignment and leadership opportunities.",
    "Dedicated to self-improvement and team success.",
    "Pursuing education and community involvement.",
]

def rand_date(start_year=2020, end_year=2026):
    start = date(start_year, 1, 1)
    end   = date(end_year, 4, 1)
    return start + timedelta(days=random.randint(0, (end - start).days))

def fmt_date(d):
    return d.strftime("%-m/%-d/%y") if hasattr(d, "strftime") else ""

def fmt_date_long(d):
    return d.strftime("%m/%d/%Y") if hasattr(d, "strftime") else ""

def tig_tis_str(months):
    y = months // 12
    m = months % 12
    return f"{y}y {m}m"

def skill_for_rank(rank):
    return {"Amn":"1","A1C":"3","SrA":"5","SSgt":"7","TSgt":"7","MSgt":"9","SMSgt":"9"}.get(rank,"5")

def pme_for_rank(rank):
    tier = RANKS.index(rank)
    return {
        "pme_als":    "Yes" if tier >= 2 and random.random() > 0.3  else "No",
        "pme_ncoa":   "Yes" if tier >= 3 and random.random() > 0.3  else "No",
        "pme_sncoa":  "Yes" if tier >= 5 and random.random() > 0.4  else "No",
        "pme_ejpme1": "Yes" if tier >= 3 and random.random() > 0.4  else "No",
        "pme_ejpme2": "Yes" if tier >= 5 and random.random() > 0.5  else "No",
        "pme_sncoe":  "Yes" if tier >= 5 and random.random() > 0.6  else "No",
        "pme_edo":    "Yes" if tier >= 5 and random.random() > 0.6  else "No",
        "pme_cmsoc":  "No",
        "pme_clc":    "No",
        "pme_dsca1":  "Yes" if tier >= 1 and random.random() > 0.5  else "No",
        "pme_dsca2":  "Yes" if tier >= 2 and random.random() > 0.6  else "No",
    }

def edu_for_rank(rank):
    tier = RANKS.index(rank)
    doc  = "Yes" if tier >= 5 and random.random() > 0.92 else "No"
    mas  = "Yes" if (doc == "Yes" or (tier >= 4 and random.random() > 0.7)) else "No"
    bac  = "Yes" if (mas == "Yes" or (tier >= 2 and random.random() > 0.55)) else "No"
    ass  = "Yes" if (bac == "Yes" or random.random() > max(0.2, 0.6 - tier * 0.05)) else "No"
    return {
        "edu_associates": ass,
        "edu_bachelors":  bac,
        "edu_masters":    mas,
        "edu_doctorate":  doc,
    }

def gen_assignments():
    if random.random() < 0.4:
        return "", ""
    chosen = random.sample(ASSIGNMENTS, k=random.randint(1, 3))
    dates  = [fmt_date_long(rand_date(2022, 2026)) for _ in chosen]
    return "; ".join(chosen), "; ".join(f"{a}: {d}" for a, d in zip(chosen, dates))

def gen_awards():
    if random.random() < 0.5:
        return "", ""
    chosen = random.sample(AWARDS, k=random.randint(1, 2))
    dates  = [fmt_date_long(rand_date(2023, 2026)) for _ in chosen]
    return "; ".join(chosen), "; ".join(f"{a}: {d}" for a, d in zip(chosen, dates))

def gen_prof_org(rank):
    tier = RANKS.index(rank)
    opts = ["CAL EANGUS","Other"]
    if tier <= 4: opts += ["Booster Club","Rising 6"]
    if tier >= 5: opts += ["Top 3"]
    return random.choice(opts) if random.random() > 0.4 else ""

def gen_leadership(rank):
    tier = RANKS.index(rank)
    if tier < 3 or random.random() < 0.4:
        return ""
    roles = [f"Supervisor {random.randint(1,4)} years"]
    if tier >= 4 and random.random() > 0.5:
        roles.append(f"Program Manager {random.randint(1,3)} years")
    if tier >= 5 and random.random() > 0.5:
        roles.append(f"Flight Chief {random.randint(1,3)} years")
    if tier >= 5 and random.random() > 0.7:
        roles.append(f"Senior Enlisted Leader {random.randint(1,2)} years")
    return "; ".join(roles)

def generate_members(tenant_id: int, tenant_name: str, n: int = 50):
    used = set()
    members = []
    attempts = 0
    while len(members) < n and attempts < n * 10:
        attempts += 1
        rank   = random.choices(RANKS, weights=RANK_WEIGHTS)[0]
        fn     = random.choice(FIRST_NAMES)
        ln     = random.choice(LAST_NAMES)
        key    = f"{fn}:{ln}"
        if key in used:
            continue
        used.add(key)

        tis_months = random.randint(6, 240)
        tig_months = random.randint(1, min(tis_months, 84))
        doe        = date.today() - timedelta(days=tis_months * 30)
        dor        = date.today() - timedelta(days=tig_months * 30)
        last_eval  = rand_date(2024, 2026)
        last_aca   = rand_date(2022, 2026)
        promo      = random.choices(["Promote","Must Promote","Promote Now"], weights=[60,25,15])[0]
        fitness    = random.choices(["Satisfactory","Excellent"], weights=[60,40])[0]
        assigns, assigns_date = gen_assignments()
        awards, awards_date   = gen_awards()

        member = {
            "tenant_id":        tenant_id,
            "rank":             rank,
            "first_name":       fn,
            "last_name":        ln,
            "flight":           random.choice(FLIGHTS),
            "last_eval":        fmt_date(last_eval),
            "promo_recomm":     promo,
            "last_aca":         fmt_date(last_aca),
            "doe":              fmt_date(doe),
            "tig":              tig_tis_str(tig_months),
            "dor":              fmt_date(dor),
            "tis":              tig_tis_str(tis_months),
            "skill_level":      skill_for_rank(rank),
            "fitness":          fitness,
            "assignments":      assigns,
            "assignments_date": assigns_date,
            "awards_decs":      awards,
            "awards_decs_date": awards_date,
            "prof_org_mbr":     gen_prof_org(rank),
            "leadership_roles": gen_leadership(rank),
            "supervisor_notes": random.choice(NOTES_SUP),
            "ratee_notes":      random.choice(NOTES_RAT),
            "last_edit":        fmt_date(rand_date(2025, 2026)),
            **pme_for_rank(rank),
            **edu_for_rank(rank),
        }
        members.append(member)
    return members

def generate_admin_user(tenant_id: int, tenant_name: str):
    short = tenant_name.lower().replace(" ","_")
    return {
        "tenant_id":  tenant_id,
        "username":   f"admin_{short}",
        "password":   hash_pw(f"Admin@{tenant_name.replace(' ','')}!1"),
        "role":       "admin",
        "first_name": "Admin",
        "last_name":  tenant_name,
        "rank":       "MSgt",
        "flight":     "Alpha",
        "title":      "Flight Chief",
    }

def run():
    tenants = get_all_tenants()
    if not tenants:
        print("No tenants found. Run schema.sql first.")
        return

    print(f"Found {len(tenants)} tenants. Generating data...")

    for tenant in tenants:
        tid  = tenant["id"]
        name = tenant["name"]
        print(f"\n  {name} (id={tid})")

        # Create admin user for tenant
        admin = generate_admin_user(tid, name)
        try:
            db().table("users").insert(admin).execute()
            print(f"    ✓ Admin user: {admin['username']} / Admin@{name.replace(' ','')}!1")
        except Exception as e:
            print(f"    ⚠ Admin user already exists or error: {e}")

        # Generate and insert members in batches
        members = generate_members(tid, name, 50)
        batch_size = 20
        inserted = 0
        for i in range(0, len(members), batch_size):
            batch = members[i:i+batch_size]
            try:
                db().table("members").insert(batch).execute()
                inserted += len(batch)
            except Exception as e:
                print(f"    ⚠ Batch insert error: {e}")
        print(f"    ✓ {inserted} members inserted")

    print("\n✅ Data generation complete!")
    print("\nAdmin accounts created:")
    tenants = get_all_tenants()
    for t in tenants:
        short = t["name"].lower().replace(" ","_")
        print(f"  admin_{short} / Admin@{t['name'].replace(' ','')}!1")
    print("\nSuper admin: superadmin / SuperAdmin@149IS!1")

if __name__ == "__main__":
    run()
