/** @odoo-module **/

import { registry } from "@web/core/registry";
import { dateFilter } from "@web/search/filters";   // caminho correto
import { DateTime } from "luxon";                   // biblioteca oficial

const customDateFilter = {
    ...dateFilter,
    options: [
        ...dateFilter.options,
        {
            id: "today",
            label: "Hoje",
            domain: (field) => [[field, "=", DateTime.now().toISODate()]],
        },
        {
            id: "yesterday",
            label: "Ontem",
            domain: (field) => [[field, "=", DateTime.now().minus({ days: 1 }).toISODate()]],
        },
        {
            id: "this_week",
            label: "Esta Semana",
            domain: (field) => {
                const start = DateTime.now().startOf("week").toISODate();
                const end = DateTime.now().endOf("week").toISODate();
                return [[field, ">=", start], [field, "<=", end]];
            },
        },
        {
            id: "last_week",
            label: "Semana Passada",
            domain: (field) => {
                const start = DateTime.now().minus({ weeks: 1 }).startOf("week").toISODate();
                const end = DateTime.now().minus({ weeks: 1 }).endOf("week").toISODate();
                return [[field, ">=", start], [field, "<=", end]];
            },
        },
    ],
};

registry.category("search_filters").add("date", customDateFilter);
