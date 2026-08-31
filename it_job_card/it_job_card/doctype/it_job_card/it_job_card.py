# Copyright (c) 2026, one and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowtime, nowdate


class ITJobCard(Document):
	def before_insert(self):
		# Web form has login_required=1 and no longer shows the visitor field,
		# so this is what actually sets it. Desk users can still override.
		if not self.visitor:
			self.visitor = frappe.session.user
		if not self.visit_date:
			self.visit_date = nowdate()
		# Users never fill this in directly — captured the moment the card is created
		if not self.start_time:
			self.start_time = nowtime()

	def validate(self):
		# Fires on every save, including workflow-driven status changes.
		# Only sets end_time once — won't overwrite it on later edits.
		if self.status == "Completed" and not self.end_time:
			self.end_time = nowtime()

import frappe
from frappe.utils import getdate, add_days, today, nowdate

WEEKDAY_MAP = {
	0: "Monday", 1: "Tuesday", 2: "Wednesday",
	3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday",
}


def send_visit_reminders():
	settings = frappe.get_single("IT Job Card Settings")

	if not settings.send_reminder:
		return

	if not settings.it_team_role:
		frappe.log_error("IT Job Card Settings: send_reminder is on but no it_team_role is set")
		return

	team_emails = frappe.get_all(
		"Has Role",
		filters={"role": settings.it_team_role, "parenttype": "User"},
		pluck="parent",
	)
	if not team_emails:
		return

	lead_days = settings.send_reminder_ondays_before or 0
	target_date = add_days(getdate(), lead_days)
	target_weekday = WEEKDAY_MAP[target_date.weekday()]

	# NOTE: settings.reminder_time controls when the scheduler *should* fire,
	# but Frappe's "daily" scheduler event runs on its own internal tick
	# (usually once shortly after midnight), not at an arbitrary configured
	# clock time. To actually honor reminder_time, register this under
	# "all" or "cron" in hooks.py instead, e.g.:
	#   "cron": {"0 8 * * *": ["it_job_card.tasks.send_visit_reminders"]}
	# and read settings.reminder_time only if you want the cron string
	# itself to be admin-editable (more work — a fixed cron entry is
	# simpler if 8am is fine to hardcode).

	schedules = frappe.get_all(
		"IT Visit Schedule",
		filters={"active": 1, "weekday": target_weekday},
		fields=["name", "division", "frequency", "last_reminded_on"],
	)

	for sched in schedules:
		# Avoid duplicate sends if the daily job runs more than once for the same date
		if sched.last_reminded_on == getdate():
			continue

		# Biweekly/monthly frequency check would go here — e.g. compare
		# against the last completed IT Job Card for this schedule_reference
		# rather than a naive date-diff, since visits can slip.

		frappe.sendmail(
			recipients=team_emails,
			subject=f"Upcoming IT visit needed — {sched.division} on {target_date.strftime('%A, %d %b')}",
			message=f"""
				<p>A planned IT visit to <b>{sched.division}</b> is due on
				<b>{target_date.strftime('%A, %d %b %Y')}</b>.</p>
				<p>Whoever's available, please take it and log it via an IT Job Card
				once completed.</p>
			""",
			reference_doctype="IT Visit Schedule",
			reference_name=sched.name,
		)

		frappe.db.set_value("IT Visit Schedule", sched.name, "last_reminded_on", getdate())

	frappe.db.commit()