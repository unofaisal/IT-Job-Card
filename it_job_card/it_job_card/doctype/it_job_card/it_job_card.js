// Copyright (c) 2026, one and contributors
// For license information, please see license.txt

frappe.ui.form.on("IT Job Card", {
	refresh(frm) {
		set_visitor_query(frm);
		set_supervisor_query(frm);
	},

	division(frm) {
		if (frm.doc.supervisor_incharge) {
			frm.set_value("supervisor_incharge", "");
		}
		set_supervisor_query(frm);
	},
});

function set_visitor_query(frm) {
	frm.set_query("visitor", function () {
		return {
			query: "it_job_card.it_job_card.doctype.it_job_card.it_job_card.get_it_team_users",
		};
	});
}

function set_supervisor_query(frm) {
	frm.set_query("supervisor_incharge", function () {
		return {
			query: "it_job_card.it_job_card.doctype.it_job_card.it_job_card.get_division_supervisors",
			filters: {
				division: frm.doc.division,
			},
		};
	});
}
