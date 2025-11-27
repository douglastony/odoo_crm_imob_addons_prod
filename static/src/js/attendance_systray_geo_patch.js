/** @odoo-module **/
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

async function getGeolocation() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            return reject(new Error("Geolocalização não suportada."));
        }
        navigator.geolocation.getCurrentPosition(
            (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
            (err) => reject(new Error("Erro ao obter localização: " + err.message)),
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    });
}

const systrayCategory = registry.category("systray");
const originalItem = systrayCategory.get("hr_attendance.attendance_menu");

if (originalItem && originalItem.Component) {
    patch(originalItem.Component, {
        setup() {
            this.rpc = useService("rpc");
            this.notification = useService("notification");
        },
        async onClick() {
            try {
                const geo = await getGeolocation();
                await this.rpc("/hr_attendance/systray_check_in_out", {
                    latitude: geo.latitude,
                    longitude: geo.longitude,
                });
                await this._updateStatus?.();
            } catch (err) {
                this.notification.add(err.message || "Falha ao obter localização.", { type: "warning" });
                await this.rpc("/hr_attendance/systray_check_in_out", {});
                await this._updateStatus?.();
            }
        },
    });
}
