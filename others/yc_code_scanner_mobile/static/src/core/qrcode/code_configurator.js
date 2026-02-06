/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { Component, onMounted, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { isBrowserChrome, isMobileOS } from "@web/core/browser/feature_detection";

export class CodeConfigurator extends Component {
    static template = "yc_code_scanner_mobile.CodeConfigurator";
    static props = ["facingMode", "devices", "supportedCodes", "deviceUid", "barcodeReader", "qrCodeScanner", "codeType", "close", "onResult", "onError"];

    setup() {
        this.state = useState({
            deviceUid: '',
            barcodeReader: '',
            codeType: 0,
            errorMessage: _t("Check your browser permissions"),
        });
        const isMobileChrome = isMobileOS() && isBrowserChrome()
        if(isMobileChrome){
            if (this.props.devices.length != 0 && this.props.devices.length == 1){
                this.state.deviceUid = this.props.devices[0].id
            }
            else{
                this.state.deviceUid = this.props.devices[1].id
            }
        }
        else{
            this.state.deviceUid = this.props.devices[0].id
        }
        this.state.barcodeReader = this.props.supportedCodes[0].label
        this.state.qrCodeScanner = ''
        this.notification = useService("notification");

        onWillStart(async () => {
            const viewport = document.querySelector('#webcam_viewport');
            if (viewport !== null){
                viewport.style.display = 'block';
                viewport.style.height = '250px';
                if (this.state.codeType === 1) {
                    this.decodeBarcode();
                } else if (this.state.codeType === 0) {
                    this.decodeQrCode();
                }
            }
        });

        onMounted(async () => {
            const viewport = document.querySelector('#webcam_viewport');
            viewport.style.display = 'block';
            viewport.style.height = '250px';
            if (this.state.codeType === 1) {
                this.decodeBarcode();
            } else if (this.state.codeType === 0) {
                this.decodeQrCode();
            }
        });
    }

    async _updateSelectedDevice(event) {
        const deviceUid = event.target.selectedOptions[0].attributes['value'].value;
        this.state.deviceUid = deviceUid;
        this.env.updateSelectedDeviceData(deviceUid);
        this._updateDeviceValue();
    }

    async _updateSelectedBarcodeReader(event) {
        const barcodeReader = event.target.selectedOptions[0].attributes['value'].value
        this.state.barcodeReader = barcodeReader
        this.env.updateSelectedBarcodeReaderData(barcodeReader);
        this._updateReaderValue();
    }

    async _updateSelectedScanType(event) {
        const scanType = event.target.value;
        this.state.codeType = parseInt(scanType);
        this.env.updateSelectedScanTypeData(parseInt(scanType));
        this._updateValue();
    }

    async _updateDeviceValue() {
        const viewport = document.querySelector('#webcam_viewport');
        viewport.style.display = 'block';
        viewport.style.height = '250px';
        if (this.state.codeType === 1) {
            await window.Quagga.stop();
            this.decodeBarcode();
        } else if (this.state.codeType === 0) {
            await this.state.qrCodeScanner.stop();
            this.decodeQrCode();
        }
    }

    async _updateReaderValue() {
        const viewport = document.querySelector('#webcam_viewport');
        viewport.style.display = 'block';
        viewport.style.height = '250px';
        if (this.state.codeType === 1) {
            await window.Quagga.stop();
            this.decodeBarcode();
        } else if (this.state.codeType === 0) {
            await this.state.qrCodeScanner.stop();
            this.decodeQrCode();
        }
    }

    async _updateValue() {
        const viewport = document.querySelector('#webcam_viewport');
        viewport.style.display = 'block';
        viewport.style.height = '250px';
        if (this.state.codeType === 1) {
            await this.state.qrCodeScanner.stop();
            this.decodeBarcode();
        } else if (this.state.codeType === 0) {
            await window.Quagga.stop();
            this.decodeQrCode();
        }
    }

    async decodeBarcode() {
        const self = this;
        const isMobileChrome = isMobileOS() && isBrowserChrome()
        window.Quagga.init({
            inputStream: {
                name: "Live",
                type: "LiveStream",
                target: document.querySelector('#webcam_viewport'),
                constraints: {
                    width: {min: 640},
                    height: {min: 480},
                    facingMode: "environment",
                    aspectRatio: {min: 1, max: 2},
                    deviceId: this.state.deviceUid,
                },
            },
            locator: {
                patchSize: "medium",
                halfSample: true
            },
            numOfWorkers: 2,
            frequency: 10,
            decoder: {
                readers: [{ format: this.state.barcodeReader, config: {} }],
            },
            locate: true,
        }, (err) => {
            if (err) {
                this.env.onError(error);
                return;
            }
            window.Quagga.start();
        });

        window.Quagga.onProcessed(function(result) {
            var drawingCtx = window.Quagga.canvas.ctx.overlay;
            var drawingCanvas = window.Quagga.canvas.dom.overlay;
            if (result) {
                if (result.boxes) {
                    drawingCtx.clearRect(0, 0, parseInt(drawingCanvas.getAttribute("width")), parseInt(drawingCanvas.getAttribute("height")));
                    result.boxes.filter(function (box) {
                        return box !== result.box;
                    }).forEach(function (box) {
                        window.Quagga.ImageDebug.drawPath(box, {x: 0, y: 1}, drawingCtx, {color: "green", lineWidth: 2});
                    });
                }

                if (result.box) {
                    window.Quagga.ImageDebug.drawPath(result.box, {x: 0, y: 1}, drawingCtx, {color: "#00F", lineWidth: 2});
                }

                if (result.codeResult && result.codeResult.code) {
                    window.Quagga.ImageDebug.drawPath(result.line, {x: 'x', y: 'y'}, drawingCtx, {color: 'red', lineWidth: 3});
                }
            }
        });

        window.Quagga.onDetected((result) => {
            const qrCodeMessage = result.codeResult.code;
            window.Quagga.stop();
            document.querySelector('#webcam_viewport').style.display = 'none';
            this.notification.add("Barcode detected: " + qrCodeMessage, { type: 'success' });
            this.updateFieldValue(qrCodeMessage);
        });
    }

    async decodeQrCode() {
        const viewport = document.querySelector('#webcam_viewport');
        const qrCodeScanner = new window.__Html5QrcodeLibrary__.Html5Qrcode("webcam_viewport");
        viewport.style.height = '250px';
        this.state.qrCodeScanner = qrCodeScanner
        this.env.updateqrCodeScannerData(qrCodeScanner);

        this.state.qrCodeScanner.start(
            this.state.deviceUid || facingMode,
            { fps: 10, qrbox: 170 },
            (qrCodeMessage) => {
                this.state.qrCodeScanner.stop();
                viewport.style.height = '0px';
                this.notification.add("QR Code detected: " + qrCodeMessage, { type: 'success' });
                this.updateFieldValue(qrCodeMessage);
            },
        ).catch((err) => {
            this.notification.add("Unable to start scanning: " + err, { type: 'warning' });
            this.env.onError(error);
        });
    }

    updateFieldValue(qrCodeMessage) {
        this.env.onResult(qrCodeMessage);
    }

    async _cancel() {
        console.log(">>>>>>>>>>>>>Callinf", this.state.qrCodeScanner)
        if (this.state.codeType === 1) {
            await window.Quagga.stop();
        } else if (this.state.codeType === 0) {
            await this.state.qrCodeScanner.stop();
        }
        return this.props.close();
    }
}
