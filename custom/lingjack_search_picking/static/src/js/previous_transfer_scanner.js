/** @odoo-module **/

import { registry } from '@web/core/registry';
import { rpc } from "@web/core/network/rpc";

// Global variables for scanner state
let wizardId = null;
let scanner = null;
let isScannerRunning = false;

/**
 * Load Html5Qrcode library dynamically
 */
const loadQRLibrary = async () => {
    if (window.Html5Qrcode) {
        return window.Html5Qrcode;
    }
    
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = 'https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js';
        script.onload = () => {
            if (window.Html5Qrcode) {
                resolve(window.Html5Qrcode);
            } else {
                reject(new Error('Html5Qrcode library failed to load'));
            }
        };
        script.onerror = () => reject(new Error('Failed to load Html5Qrcode library'));
        document.head.appendChild(script);
    });
};

/**
 * Create scanner modal HTML
 */
const createModalHTML = () => {
    return `
        <div id="previous-transfer-scanner-modal" style="
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 9999;
        ">
            <div style="
                background: white;
                border-radius: 8px;
                padding: 20px;
                max-width: 90%;
                max-height: 90%;
                overflow: auto;
                text-align: center;
            ">
                <h3 style="margin: 0 0 20px 0; color: #333;">Scan Previous Transfer Barcode</h3>
                
                <div id="scanner-status-pt" style="
                    margin-bottom: 15px;
                    padding: 10px;
                    border-radius: 4px;
                    background: #f8f9fa;
                    border: 1px solid #dee2e6;
                    color: #495057;
                    font-size: 14px;
                ">Initializing camera...</div>
                
                <div id="qr-reader-previous-transfer" style="
                    width: 100%;
                    max-width: 400px;
                    margin: 0 auto 20px auto;
                    border: 2px solid #007bff;
                    border-radius: 8px;
                    overflow: hidden;
                "></div>
                
                <div style="
                    display: flex;
                    gap: 10px;
                    justify-content: center;
                    margin-top: 20px;
                ">
                    <button id="close-scanner-btn-pt" style="
                        background: #dc3545;
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 14px;
                    ">Close</button>
                </div>
                
                <div style="
                    margin-top: 15px;
                    font-size: 12px;
                    color: #6c757d;
                ">
                    <strong>Instructions:</strong><br>
                    Point camera at previous transfer barcode
                </div>
            </div>
        </div>
    `;
};

/**
 * Update scanner status message
 */
const updateStatus = (message, color = '#495057') => {
    const statusEl = document.getElementById('scanner-status-pt');
    if (statusEl) {
        statusEl.textContent = message;
        statusEl.style.color = color;
    }
};

/**
 * Initialize scanner modal
 */
const initScanner = () => {
    // Remove existing modal if any
    const existingModal = document.getElementById('previous-transfer-scanner-modal');
    if (existingModal) {
        existingModal.remove();
    }

    // Create and append modal
    const modalHTML = createModalHTML();
    document.body.insertAdjacentHTML('beforeend', modalHTML);

    // Setup event listeners
    const closeBtn = document.getElementById('close-scanner-btn-pt');
    closeBtn.addEventListener('click', closeModal);

    // Start camera
    startScanner();
};

/**
 * Start camera scanner
 */
const startScanner = async () => {
    try {
        updateStatus('Starting camera...');

        const qrReaderElement = document.getElementById('qr-reader-previous-transfer');
        if (!qrReaderElement) {
            throw new Error('Scanner element not found');
        }

        // Clear previous scanner
        qrReaderElement.innerHTML = '';

        // Initialize Html5Qrcode
        scanner = new Html5Qrcode('qr-reader-previous-transfer');
        
        const config = {
            fps: 10,
            qrbox: { width: 250, height: 250 },
            aspectRatio: 1.0,
        };

        // Try to start with back camera (environment facing)
        try {
            await scanner.start(
                { facingMode: "environment" },
                config,
                (decodedText) => handleScanResult(decodedText),
                (errorMessage) => {
                    // Ignore continuous scan errors
                }
            );
            isScannerRunning = true;
            updateStatus('Camera ready - scan barcode', '#28a745');
        } catch (err) {
            // Fallback to default camera
            await scanner.start(
                {},
                config,
                (decodedText) => handleScanResult(decodedText),
                (errorMessage) => {
                    // Ignore continuous scan errors
                }
            );
            isScannerRunning = true;
            updateStatus('Camera ready - scan barcode', '#28a745');
        }

    } catch (error) {
        console.error('Failed to start scanner:', error);
        updateStatus('Failed to start camera: ' + error.message, '#dc3545');
    }
};

/**
 * Handle barcode scan result
 */
const handleScanResult = async (decodedText) => {
    try {
        updateStatus('Barcode detected: ' + decodedText, '#007bff');
        
        // Stop scanner
        await stopScanner();

        // Search for picking by previous_transfer field
        const pickings = await rpc('/web/dataset/call_kw', {
            model: 'stock.picking',
            method: 'search_read',
            args: [[['previous_transfer', 'ilike', decodedText]]],
            kwargs: {
                fields: ['id', 'name', 'previous_transfer'],
                limit: 1
            }
        });

        if (pickings && pickings.length > 0) {
            // Close modal
            closeModal();

            // Open transfer record directly
            window.location.href = `/web#id=${pickings[0].id}&model=stock.picking&view_type=form`;
        } else {
            updateStatus('No transfer found: ' + decodedText, '#dc3545');
            setTimeout(() => {
                updateStatus('Ready to scan', '#495057');
                startScanner();
            }, 2000);
        }

    } catch (error) {
        console.error('Error processing scan result:', error);
        updateStatus('Error: ' + error.message, '#dc3545');
        setTimeout(() => {
            updateStatus('Ready to scan', '#495057');
            startScanner();
        }, 2000);
    }
};

/**
 * Stop camera scanner
 */
const stopScanner = async () => {
    if (scanner && isScannerRunning) {
        try {
            await scanner.stop();
            scanner.clear();
            scanner = null;
            isScannerRunning = false;
        } catch (error) {
            console.error('Error stopping scanner:', error);
        }
    }
};

/**
 * Close scanner modal
 */
const closeModal = async () => {
    await stopScanner();
    const modal = document.getElementById('previous-transfer-scanner-modal');
    if (modal) {
        modal.remove();
    }
};

/**
 * Register the barcode scanner action
 */
registry.category("actions").add("previous_transfer_barcode_scanner", async (env, action) => {
    try {
        console.log('Previous transfer barcode scanner invoked', action);
        
        // Extract parameters
        wizardId = action && action.params ? action.params.wizard_id : null;
        
        if (!wizardId) {
            throw new Error('Wizard ID is required');
        }

        // Load QR library and initialize scanner
        await loadQRLibrary();
        initScanner();

    } catch (error) {
        console.error('Failed to execute previous transfer barcode scanner:', error);
        alert('Failed to start scanner: ' + error.message);
    }
});

