/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { Component, useState, useSubEnv } from "@odoo/owl";
import { CodeConfigurator } from "./code_configurator";

export class CodeDialog extends Component {
    static template = "yc_code_scanner_mobile.CodeDialog";
    static components = {
        Dialog,
        CodeConfigurator,
    };
    static props = ["facingMode", "devices", "supportedCodes", "deviceUid", "barcodeReader", "qrCodeScanner", "codeType", "close", "onResult", "onError"];

    setup() {
        this.state = useState({
            deviceUid: '',
            barcodeReader: '',
            qrCodeScanner: '',
            codeType: 0,
            errorMessage: _t("Check your browser permissions"),
        });
        this.env.dialogData.dismiss = () => this._dismiss();
        this.state.deviceUid = this.props.devices[0].id
        this.state.barcodeReader = this.props.supportedCodes[0].label

        useSubEnv({
            updateSelectedDeviceData: this._updateSelectedDeviceData.bind(this),
            updateSelectedBarcodeReaderData: this._updateSelectedBarcodeReaderData.bind(this),
            updateSelectedScanTypeData: this._updateSelectedScanTypeData.bind(this),
            updateqrCodeScannerData: this._updateqrCodeScannerData.bind(this),
            onResult: this.onResult.bind(this),
            onError: this.onError.bind(this),
        });

    }

    async _updateqrCodeScannerData(qrCodeScanner) {
        this.state.qrCodeScanner = qrCodeScanner
        this.props.qrCodeScanner = qrCodeScanner
    }

    async _updateSelectedDeviceData(deviceUid) {
        this.state.deviceUid = deviceUid
        this.props.deviceUid = deviceUid
    }

    async _updateSelectedBarcodeReaderData(barcodeReader) {
        this.state.barcodeReader = barcodeReader
        this.props.barcodeReader = barcodeReader
    }

    async _updateSelectedScanTypeData(scanType) {
        this.state.codeType = parseInt(scanType)
        this.props.codeType = parseInt(scanType)
    }

    /**
     * Detection success handler
     *
     * @param {string} result found code
     */
    onResult(result) {
        this.props.close();
        this.props.onResult(result);
    }

    /**
     * Detection error handler
     *
     * @param {Error} error
     */
    onError(error) {
        this.props.close();
        this.props.onError(error);
    }

    async close(qrCodeScanner) {
        if (this.state.codeType === 1) {
            await window.Quagga.stop();
        } else if (this.state.codeType === 0) {
            await this.state.qrCodeScanner.stop();
        }
        this.props.close(qrCodeScanner);
    }

    async _cancel() {
        if (this.state.codeType === 1) {
            await window.Quagga.stop();
        } else if (this.state.codeType === 0) {
            await this.state.qrCodeScanner.stop();
        }
        return this.props.close();
    }

    async _dismiss() {
        if (this.state.codeType === 1) {
            await window.Quagga.stop();
        } else if (this.state.codeType === 0) {
            await this.state.qrCodeScanner.stop();
        }
        return this.props.close();
    }
}
