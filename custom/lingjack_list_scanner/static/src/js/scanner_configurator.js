/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { Component, onMounted, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { isBrowserChrome, isMobileOS } from "@web/core/browser/feature_detection";

export class ScannerConfigurator extends Component {
    static template = "lingjack_list_scanner.ScannerConfigurator";
    static props = ["facingMode", "devices", "supportedCodes", "deviceUid", "barcodeReader", "qrCodeScanner", "codeType", "close", "onResult", "onError"];

    setup() {
        this.state = useState({
            deviceUid: '',
            barcodeReader: '',
            codeType: 0,
            errorMessage: _t("Check your browser permissions"),
        });
        const isMobileChrome = isMobileOS() && isBrowserChrome();
        if (isMobileChrome) {
            if (this.props.devices && this.props.devices.length > 0) {
                if (this.props.devices.length === 1) {
                    this.state.deviceUid = this.props.devices[0].id;
                } else {
                    this.state.deviceUid = this.props.devices[1].id;
                }
            }
        } else {
            if (this.props.devices && this.props.devices.length > 0) {
                this.state.deviceUid = this.props.devices[0].id;
            }
        }
        if (this.props.supportedCodes && this.props.supportedCodes.length > 0) {
            this.state.barcodeReader = this.props.supportedCodes[0].label;
        }
        this.state.qrCodeScanner = '';
        this.notification = useService("notification");

        onWillStart(async () => {
            const viewport = document.querySelector('#webcam_viewport');
            if (viewport !== null) {
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
            if (viewport) {
                viewport.style.display = 'block';
                viewport.style.height = '250px';
                if (this.state.codeType === 1) {
                    this.decodeBarcode();
                } else if (this.state.codeType === 0) {
                    this.decodeQrCode();
                }
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
        const barcodeReader = event.target.selectedOptions[0].attributes['value'].value;
        this.state.barcodeReader = barcodeReader;
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
        if (viewport) {
            viewport.style.display = 'block';
            viewport.style.height = '250px';
            if (this.state.codeType === 1) {
                if (window.Quagga) {
                    await window.Quagga.stop();
                }
                this.decodeBarcode();
            } else if (this.state.codeType === 0) {
                if (this.state.qrCodeScanner) {
                    await this.state.qrCodeScanner.stop();
                }
                this.decodeQrCode();
            }
        }
    }

    async _updateReaderValue() {
        const viewport = document.querySelector('#webcam_viewport');
        if (viewport) {
            viewport.style.display = 'block';
            viewport.style.height = '250px';
            if (this.state.codeType === 1) {
                if (window.Quagga) {
                    await window.Quagga.stop();
                }
                this.decodeBarcode();
            } else if (this.state.codeType === 0) {
                if (this.state.qrCodeScanner) {
                    await this.state.qrCodeScanner.stop();
                }
                this.decodeQrCode();
            }
        }
    }

    async _updateValue() {
        const viewport = document.querySelector('#webcam_viewport');
        if (viewport) {
            viewport.style.display = 'block';
            viewport.style.height = '250px';
            if (this.state.codeType === 1) {
                if (this.state.qrCodeScanner) {
                    await this.state.qrCodeScanner.stop();
                }
                this.decodeBarcode();
            } else if (this.state.codeType === 0) {
                if (window.Quagga) {
                    await window.Quagga.stop();
                }
                this.decodeQrCode();
            }
        }
    }

    async decodeBarcode() {
        if (!window.Quagga) {
            this.notification.add(_t("Barcode scanner library not loaded"), { type: 'warning' });
            return;
        }

        const viewport = document.querySelector('#webcam_viewport');
        if (!viewport) {
            return;
        }

        window.Quagga.init({
            inputStream: {
                name: "Live",
                type: "LiveStream",
                target: viewport,
                constraints: {
                    width: { min: 640 },
                    height: { min: 480 },
                    facingMode: "environment",
                    aspectRatio: { min: 1, max: 2 },
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
                this.env.onError(err);
                return;
            }
            window.Quagga.start();
        });

        window.Quagga.onDetected((result) => {
            const qrCodeMessage = result.codeResult.code;
            window.Quagga.stop();
            if (viewport) {
                viewport.style.display = 'none';
            }
            this.notification.add(_t("Barcode detected: ") + qrCodeMessage, { type: 'success' });
            this.updateFieldValue(qrCodeMessage);
        });
    }

    async decodeQrCode() {
        if (!window.__Html5QrcodeLibrary__ || !window.__Html5QrcodeLibrary__.Html5Qrcode) {
            this.notification.add(_t("QR code scanner library not loaded"), { type: 'warning' });
            return;
        }

        const viewport = document.querySelector('#webcam_viewport');
        if (!viewport) {
            return;
        }

        const qrCodeScanner = new window.__Html5QrcodeLibrary__.Html5Qrcode("webcam_viewport");
        viewport.style.height = '250px';
        this.state.qrCodeScanner = qrCodeScanner;
        this.env.updateqrCodeScannerData(qrCodeScanner);

        const facingMode = this.props.facingMode || "environment";
        this.state.qrCodeScanner.start(
            this.state.deviceUid || facingMode,
            { fps: 10, qrbox: 170 },
            (qrCodeMessage) => {
                this.state.qrCodeScanner.stop();
                viewport.style.height = '0px';
                this.notification.add(_t("QR Code detected: ") + qrCodeMessage, { type: 'success' });
                this.updateFieldValue(qrCodeMessage);
            },
        ).catch((err) => {
            this.notification.add(_t("Unable to start scanning: ") + err, { type: 'warning' });
            this.env.onError(err);
        });
    }

    updateFieldValue(qrCodeMessage) {
        this.env.onResult(qrCodeMessage);
    }
}


