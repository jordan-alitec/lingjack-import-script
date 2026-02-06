/** @odoo-module **/
import { Component, useState, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { BarcodeVideoScanner, isBarcodeScannerSupported } from "@web/core/barcode/barcode_video_scanner";
import { rpc } from "@web/core/network/rpc";

class LocationScanner extends Component {
    static template = "lj_barcode_qty_demand.LocationScanner";

    static props = {
        action: { type: Object },
        actionId: { type: Number, optional: true },
        updateActionState: { type: Function, optional: true },
    };

    static components = { BarcodeVideoScanner };

    setup() {
        const action = this.props.action || {};
        this.params = action.params || {};
        this.picking_id = this.params.picking_id || false;
        this.location_selected = this.params.location_selected || 'location';

        this.state = useState({
            scanning: true,
            ready: false,
            // map incoming selection to scanner type
            locationType: this.location_selected === 'destination_location' ? 'destination' : 'source',
        });

        this.cameraSupported = isBarcodeScannerSupported();

        this.timeoutHandle = setTimeout(() => {
            this.env.services.notification.add("No barcode detected. Please try again.", { type: "warning" });
            this.close();
        }, 60000);

        this.barcodeProps = {
            delayBetweenScan: 800,
            facingMode: "environment",
            onResult: (barcode) => this._handleScan(barcode),
            onReady: () => { this.state.ready = true; },
            onError: (err) => {
                this.env.services.notification.add(err.message, { type: "warning" });
            },
            cssClass: "o_barcode_camera_video",
        };

        // cleanup on unmount
        onWillUnmount(() => {
            if (this.timeoutHandle) {
                clearTimeout(this.timeoutHandle);
                this.timeoutHandle = null;
            }
        });
    }

    async _handleScan(rawBarcode) {
        if (!rawBarcode) {
            this.env.services.notification.add("Empty barcode received", { type: "warning" });
            return;
        }
        const cleaned = rawBarcode.trim();

        try {
            const rpcResult = await rpc('/web/load/location/by_barcode', {
                rawBarcode: cleaned,
                picking_id: this.picking_id,
                location_type: this.state.locationType,
            });

            if (!rpcResult) {
                this.env.services.notification.add("Invalid response from server", { type: "warning" });
                return;
            }

            if (!rpcResult.success) {
                // server returned an error message
                this.env.services.notification.add(rpcResult.error || "Invalid or unknown barcode", { type: "warning" });
                return;
            }

            // SUCCESS
            const loc = rpcResult.location || {};
            const written_field = rpcResult.written_field || 'Location';
            this.env.services.notification.add(
                `Location Set: ${loc.name || 'unknown'} (${loc.barcode || ''}) — updated ${written_field}`,
                { type: "success" }
            );

            // close the wizard
            this.close();
        } catch (err) {
            console.error(err);
            this.env.services.notification.add(err.message || "Scanner error", { type: "danger" });
        }
    }

    close() {
        if (this.timeoutHandle) {
            clearTimeout(this.timeoutHandle);
            this.timeoutHandle = null;
        }
        this.env.services.action.doAction({ type: "ir.actions.act_window_close" });
    }
}

registry.category("actions").add("lj_barcode_qty_demand.location_scanner", LocationScanner);
export default LocationScanner;
