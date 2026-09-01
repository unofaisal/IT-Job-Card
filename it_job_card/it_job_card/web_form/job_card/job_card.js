frappe.ready(function() {
    render_workflow_actions();
});

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