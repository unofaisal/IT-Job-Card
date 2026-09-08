import json

import frappe


def get_context(context):
    # do your magic here
    pass


# ---------------------------------------------------------------------------
# Web form list permissions
# ---------------------------------------------------------------------------
# The list page fetches rows via frappe.www.list.get_list_data, which loads
# this module's get_list_context() and merges its `filters` into the query.
# Frappe admins (System Manager / Administrator) see all job cards; everyone
# else sees only their own. Applied server-side — the user cannot clear it
# from the browser.


def _is_frappe_admin():
    return frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()


def get_list_context(context):
    if not _is_frappe_admin():
        context.filters = {"owner": frappe.session.user}
    return context


# ---------------------------------------------------------------------------
# Link-field search helpers for the /job-card web form
#
# NOTE: the web-form link autocomplete calls a custom query method with
# `txt` only — nothing else from the set_query() return object is sent.
# Dynamic form state (the selected division) is pushed out-of-band via
# set_division_context().
# ---------------------------------------------------------------------------


@frappe.whitelist()
def set_division_context(division=None):
    """Store the web form's current Division for this user."""
    frappe.cache().hset("it_job_card:division", frappe.session.user, division or "")


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
        {"role": role, "txt": f"%{txt or ''}%", "start": start, "page_len": page_len},
    )
    return [{"value": name, "label": full_name} for name, full_name in rows]


@frappe.whitelist()
def get_division_supervisors(
    doctype=None, txt="", searchfield=None, start=0, page_len=20, filters=None, **kwargs
):
    if isinstance(filters, str):
        try:
            filters = json.loads(filters)
        except (TypeError, ValueError):
            filters = None

    division = kwargs.get("division") or (filters or {}).get("division")
    if not division:
        division = frappe.cache().hget("it_job_card:division", frappe.session.user)

    if not division:
        return []

    start = frappe.utils.cint(start)
    page_len = frappe.utils.cint(page_len) or 20

    rows = frappe.db.sql(
        """
        SELECT name, full_name
        FROM `tabApex Supervisor`
        WHERE division = %(division)s
            AND (name LIKE %(txt)s OR full_name LIKE %(txt)s)
        ORDER BY full_name
        LIMIT %(page_len)s OFFSET %(start)s
        """,
        {"division": division, "txt": f"%{txt or ''}%", "start": start, "page_len": page_len},
    )
    return [{"value": name, "label": full_name} for name, full_name in rows]