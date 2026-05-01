"""
migration.py
Migrates existing career_dashboard_data_latest.csv into Supabase for the 149 IS tenant.
Run AFTER schema.sql and AFTER data_generator.py (so tenants exist).

Usage:
    python3 migration.py
"""

import csv
from database import db, get_tenant_by_name

CSV_FILE = "career_dashboard_data_latest.csv"

FIELD_MAP = {
    "Rank":             "rank",
    "FirstName":        "first_name",
    "LastName":         "last_name",
    "Flight":           "flight",
    "LastEval":         "last_eval",
    "PromoRecomm":      "promo_recomm",
    "LastACA":          "last_aca",
    "DOE":              "doe",
    "TIG":              "tig",
    "DOR":              "dor",
    "TIS":              "tis",
    "SkillLevel":       "skill_level",
    "Fitness":          "fitness",
    "PME_ALS":          "pme_als",
    "PME_NCOA":         "pme_ncoa",
    "PME_SNCOA":        "pme_sncoa",
    "PME_EJPME1":       "pme_ejpme1",
    "PME_EJPME2":       "pme_ejpme2",
    "PME_SNCOE":        "pme_sncoe",
    "PME_EDO":          "pme_edo",
    "PME_CMSOC":        "pme_cmsoc",
    "PME_CLC":          "pme_clc",
    "PME_DSCA1":        "pme_dsca1",
    "PME_DSCA2":        "pme_dsca2",
    "EDU_ASSOCIATES":   "edu_associates",
    "EDU_BACHELORS":    "edu_bachelors",
    "EDU_MASTERS":      "edu_masters",
    "EDU_DOCTORATE":    "edu_doctorate",
    "Assignments":      "assignments",
    "AssignmentsDate":  "assignments_date",
    "AwardsDecs":       "awards_decs",
    "AwardsDecsDate":   "awards_decs_date",
    "ProfOrgMbr":       "prof_org_mbr",
    "LeadershipRoles":  "leadership_roles",
    "SupervisorNotes":  "supervisor_notes",
    "RateeNotes":       "ratee_notes",
    "LastEdit":         "last_edit",
}

def run():
    tenant = get_tenant_by_name("149 IS")
    if not tenant:
        print("ERROR: '149 IS' tenant not found. Run schema.sql first.")
        return

    tenant_id = tenant["id"]
    print(f"Migrating CSV data into tenant '149 IS' (id={tenant_id})...")

    # Clear existing members for this tenant to avoid duplicates
    db().table("members").delete().eq("tenant_id", tenant_id).execute()
    print("  Cleared existing 149 IS members.")

    with open(CSV_FILE, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows   = list(reader)

    members = []
    for row in rows:
        member = {"tenant_id": tenant_id}
        for csv_col, db_col in FIELD_MAP.items():
            val = row.get(csv_col, "").strip()
            # Normalise blank/nan
            if val.lower() in ("nan", ""):
                val = ""
            member[db_col] = val
        members.append(member)

    # Insert in batches
    batch_size = 20
    inserted   = 0
    for i in range(0, len(members), batch_size):
        batch = members[i:i+batch_size]
        try:
            db().table("members").insert(batch).execute()
            inserted += len(batch)
        except Exception as e:
            print(f"  ⚠ Batch error: {e}")

    print(f"  ✓ {inserted}/{len(rows)} members migrated into 149 IS.")
    print("\n✅ Migration complete!")

if __name__ == "__main__":
    run()
