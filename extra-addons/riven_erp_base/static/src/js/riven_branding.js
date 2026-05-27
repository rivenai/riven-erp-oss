/** @odoo-module **/
import { registry } from "@web/core/registry";

registry.category("services").add("riven_branding", {
    dependencies: ["title"],
    start(env, { title }) {
        title.setParts({ zopenerp: "Riven ERP" });
    },
});
