import frappe

def get_context(context):
	# do your magic here
	pass



@frappe.whitelist()
def get_it_team_users(doctype=None, txt="", searchfield=None, start=0, page_len=20, filters=None):
    role = frappe.db.get_single_value("IT Job Card Settings", "it_role")
    if not role:
        return []

    start = frappe.utils.cint(start)
    page_len = frappe.utils.cint(page_len) or 20

    rows = frappe.db.sql(
        """
        SELECT u.name, u.full_name
        FROM `tabUser` u
        INNER JOIN `tabHas Role` hr
            ON hr.parent = u.name AND hr.parenttype = 'User'
        WHERE hr.role = %(role)s
            AND u.enabled = 1
            AND (u.name LIKE %(txt)s OR u.full_name LIKE %(txt)s)
        ORDER BY u.full_name
        LIMIT %(page_len)s OFFSET %(start)s
        """,
        {"role": role, "txt": f"%{txt}%", "start": start, "page_len": page_len},
    )

    # Web form link search feeds the raw return value straight into the
    # autocomplete widget — it needs objects with `value` and `label` keys.
    return [{"value": name, "label": full_name} for name, full_name in rows]