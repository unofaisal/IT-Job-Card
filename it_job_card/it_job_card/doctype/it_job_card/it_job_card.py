# Copyright (c) 2026, one and contributors
# For license information, please see license.txt

# Copyright (c) 2026, one and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowtime, nowdate, getdate, add_days, today


class ITJobCard(Document):
	def before_insert(self):
		# Web form has login_required=1 and no longer shows the visitor field,
		# so this is what actually sets it. Desk users can still override.
		if not self.visitor:
			self.visitor = frappe.session.user
		
		# start_time is NOT set here — it's tied to the "Start Visit" workflow
		# action (status becoming "In Progress"), see validate() below. Setting
		# it on creation meant it fired on Save regardless of whether anyone
		# ever clicked the button, which is misleading.

	def validate(self):
		# Fires on every save, including workflow-driven status changes.
		# Only sets each timestamp once — won't overwrite it on later edits.		
		if self.status == "In Progress" and not self.start_time:
			if not self.visit_date:
				self.visit_date = nowdate()
			self.start_time = nowtime()
		if self.status == "Completed" and not self.end_time:
			self.end_time = nowtime()
			self._just_completed = True

		before = self.get_doc_before_save()
		if before and before.status == "Completed" and "System Manager" not in frappe.get_roles():
			frappe.throw("This job card is completed and can no longer be edited.")

	def on_update(self):
		if getattr(self, "_just_completed", False):
			self.send_completion_email()

	def has_webform_permission(self):
		"""Web form route permission — checked by
		WebForm.has_web_form_permission() AFTER the owner check.
		Frappe admins may open any Job Card; everyone else is owner-only."""
		return frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()

	def send_completion_email(self):
		send_mail = frappe.db.get_single_value("IT Job Card Settings", "it_role")

		if not send_mail:
			return
		admin_emails = ["s.darji@apex-steel.com"]

		cc = []
		if self.supervisor_email:
			cc = [self.supervisor_email]
			admin_emails = [e for e in admin_emails if e != self.supervisor_email]

		if not admin_emails:
			return

		kwargs = dict(
			recipients=admin_emails,
			cc=cc,
			subject=f"IT Job Card Completed — {self.division or 'Visit'} ({self.name})",
			message=self.get_completion_email_html(),
			with_container=True,  # branded card: logo/name, styled container, standard footer
			reference_doctype=self.doctype,
			reference_name=self.name,
		)

		# 2026 redesigned wrapper (rounded auth-email card) — only used when
		# the build has it; older builds fall back to standard.html
		try:
			from frappe.utils.jinja import get_template

			get_template("templates/emails/auth_email.html")
			kwargs["wrapper"] = "templates/emails/auth_email.html"
		except Exception:
			pass

		frappe.sendmail(**kwargs)

	def get_it_admin_emails(self):
		role = frappe.db.get_single_value("IT Job Card Settings", "it_role")
		if not role:
			return []

		user_names = set(
			frappe.get_all("Has Role", filters={"parenttype": "User", "role": role}, pluck="parent")
		)
		if not user_names:
			return []

		users = frappe.get_all(
			"User", filters={"name": ("in", list(user_names)), "enabled": 1}, fields=["email", "name"]
		)
		return [u.email or u.name for u in users]

	def get_completion_email_html(self):
		from frappe.utils import escape_html, format_date, get_time

		def e(v):
			return escape_html(v) if v else "-"

		# HTML collapses whitespace, so newlines must become <br> to survive
		# in email. Escape FIRST so any typed < > & stays harmless.
		def e_multiline(v):
			if not v:
				return "-"
			return (
				escape_html(v)
				.replace("\r\n", "\n")
				.replace("\r", "\n")
				.replace("\n", "<br>")
			)

		# Time fields arrive either as "10:30:00" strings or timedelta
		# objects from the DB — get_time() normalizes both.
		def fmt_time(v):
			return get_time(v).strftime("%I:%M %p") if v else "-"

		visit_date = format_date(self.visit_date) if self.visit_date else "-"
		visitor_name = frappe.db.get_value("User", self.visitor, "full_name") or self.visitor or "-"

		card_url = f"{frappe.utils.get_url()}/job-card/{self.name}"

		description_html = ""
		if self.job_description:
			description_html = f"""
			<p><b>Job Description</b></p>
			<div class="gray-container">{e_multiline(self.job_description)}</div>"""

		# All classes below are Frappe's own email classes (email.bundle.css);
		# they are inlined into the message automatically at send time.
		return f"""
		<h1 class="email-title" style="font-size:20px;font-weight:600;line-height:1.4;color:#171717;margin:0 0 16px;">Job Card Completed</h1>
		<div class="email-body">
			<p>The IT visit to <b>{e(self.division)}</b> on <b>{visit_date}</b> has been marked completed and signed off.</p>

			<table class="table table-bordered">
				<tr><td style="width:130px;"><b>Division</b></td><td>{e(self.division)}</td></tr>
				<tr><td><b>Visit Date</b></td><td>{visit_date}</td></tr>
				<tr><td><b>Visitor</b></td><td>{e(visitor_name)}</td></tr>
				<tr><td><b>Start Time</b></td><td>{fmt_time(self.start_time)}</td></tr>
				<tr><td><b>End Time</b></td><td>{fmt_time(self.end_time)}</td></tr>
			</table>
			{description_html}
			<div class="email-action">
				<a class="email-btn email-btn-primary btn btn-primary" href="{card_url}">View Job Card</a>
			</div>
		</div>
		"""



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