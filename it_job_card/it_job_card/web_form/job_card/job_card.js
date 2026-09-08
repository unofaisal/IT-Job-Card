frappe.ready(function () {
    const MODULE = "it_job_card.it_job_card.web_form.job_card.job_card";

    // ------------------------------------------------------------------
    // Link-field search wiring
    // ------------------------------------------------------------------
    try {
        if (frappe.web_form && typeof frappe.web_form.set_query === "function") {
            frappe.web_form.set_query("visitor", function () {
                return {
                    query: `${MODULE}.get_it_team_users`,
                };
            });

            // The web form's autocomplete forwards ONLY `txt` to custom
            // query methods — filters and extra keys returned here are
            // dropped client-side (verified: frappe.form_dict server-side
            // is {txt, query, cmd}). The live division value is shipped to
            // the server separately — see push_division_context() below.
            frappe.web_form.set_query("supervisor_incharge", function () {
                return {
                    query: `${MODULE}.get_division_supervisors`,
                };
            });
        } else {
            console.warn(
                "frappe.web_form.set_query not available on this version — link fields will show unfiltered options."
            );
        }
    } catch (e) {
        console.warn("Could not set up web form link queries:", e);
    }

    // ------------------------------------------------------------------
    // Division → Supervisor filtering
    //
    // The supervisor link query runs server-side but only ever receives
    // `txt`, so the current division is stored per-user in the cache via
    // set_division_context() before any search can happen.
    // ------------------------------------------------------------------
    function push_division_context() {
        frappe.call({
            method: `${MODULE}.set_division_context`,
            args: { division: frappe.web_form.get_value("division") || "" },
        });
    }

    // Remember the last seen division so a real user change can be told
    // apart from the form programmatically populating values in edit
    // mode — otherwise a saved supervisor would get wiped on load.
    let last_division = (frappe.web_form.doc && frappe.web_form.doc.division) || null;

    frappe.web_form.on("division", function (field, value) {
        if (value === last_division) return; // just the form loading
        last_division = value;

        // a supervisor chosen under the old division is no longer valid
        if (frappe.web_form.get_value("supervisor_incharge")) {
            frappe.web_form.set_value("supervisor_incharge", "");
        }
        push_division_context();
    });

    // Seed or clear the server-side context on page load.
    if (frappe.web_form.doc && frappe.web_form.doc.name) {
        // edit mode → seed from the saved document
        push_division_context();
    } else {
        // new form → clear any stale context left over from an earlier
        // visit, so the supervisor dropdown stays empty until a division
        // is picked
        frappe.call({
            method: `${MODULE}.set_division_context`,
            args: { division: "" },
        });
    }

    // Note: supervisor_email is intentionally NOT fetched here anymore.
    // It is not a web form field, and web forms only submit rendered
    // fields — so neither fetch_from nor client-side set_value could
    // persist it. It is now set server-side in ITJobCard.validate().

    render_workflow_actions();
});

// ------------------------------------------------------------------
// Workflow actions (unchanged from your original file)
// ------------------------------------------------------------------

const STATUS_COLORS = {
    "Open": "blue",
    "In Progress": "orange",
    "On Hold": "gray",
    "Completed": "green",
    "Cancelled": "red",
    "Rejected": "red",
};

function render_workflow_actions() {
    const doc = frappe.web_form.doc;
    if (!doc || !doc.name) return;

    // Edit button lives in .web-form-actions (inside .title), NOT .right-area
    let $toolbar = $(".web-form-actions");
    if (!$toolbar.length) return;

    update_status_badge(doc);

    // Cosmetic only — real lock is server-side in ITJobCard.validate()
    if (doc.status === "Completed") {
        $toolbar.find(".edit-button").hide();
    }

    frappe.call({
        method: "frappe.model.workflow.get_transitions",
        args: {
            doc: JSON.stringify({
                doctype: "IT Job Card",
                name: doc.name,
            }),
        },
    }).then((r) => {
        // Re-query — the form can re-render the header while the call is
        // in flight, which would leave the earlier $toolbar detached.
        $toolbar = $(".web-form-actions");
        update_status_badge(doc); // idempotent; re-apply in case the form reset it

        let transitions = r.message || [];

        let $group = $toolbar.find("#it-job-card-workflow-actions");
        if (!$group.length) {
            $group = $('<span id="it-job-card-workflow-actions"></span>');
            $toolbar.prepend($group);
        }
        $group.empty();
        if (!transitions.length) return;

        transitions.forEach((t, i) => {
            let is_primary = i === 0;
            $(`<button type="button" class="btn btn-${is_primary ? "primary" : "default"} btn-sm" style="margin-right: 6px;">${t.action}</button>`)
                .on("click", () => apply_transition(t.action))
                .appendTo($group);
        });
    });
}

function update_status_badge(doc) {
    const status = doc.status;
    const color = STATUS_COLORS[status] || "gray";
    $(".title .indicator-pill")
        .attr("class", `indicator-pill ${color}`)
        .text(status);
}

function apply_transition(action) {
    frappe.call({
        method: "frappe.model.workflow.apply_workflow",
        args: {
            doc: JSON.stringify({
                doctype: "IT Job Card",
                name: frappe.web_form.doc.name,
            }),
            action: action,
        },
    }).then(() => {
        frappe.show_alert({ message: `Status updated: ${action}`, indicator: "green" });
        window.location.reload();
    }).catch(() => {
        frappe.show_alert({ message: "Could not update status — check you have the IT Team role.", indicator: "red" });
    });
}