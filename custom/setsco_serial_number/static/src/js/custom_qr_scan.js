/** @odoo-module **/

import { registry } from '@web/core/registry';
import { rpc } from "@web/core/network/rpc";
import { useService } from '@web/core/utils/hooks';

// Global variables
let wizardId = null;
let targetField = null;
let rpcModel = 'setsco.serial.selection.wizard';
let scanner = null;
let isScannerRunning = false;
let currentEnv = null; // store env to access action service
let scannerMode = 'camera'; // 'camera' | 'barcode_reader'
let barcodeListener = null; // for barcode reader mode
let barcodeControlService = null; // for controlling global barcode service

// Range scanning state
let isRangeMode = false;
let rangePhase = 'start'; // 'start' | 'end'

// Barcode control functions
let barcodeEventInterceptor = null;
let keyboardInterceptor = null;

const disableGlobalBarcodeService = () => {
    try {
        console.log('🚫 Disabling global barcode service...');
        
        // Method 1: Set global flag for model override
        window.customScannerActive = true;
        console.log('✅ Global custom scanner flag set');
        
        // Method 2: Intercept barcode events at document level
        barcodeEventInterceptor = (event) => {
            // Check if this is a barcode_scanned event
            if (event.type === 'barcode_scanned' || 
                (event.detail && event.detail.barcode)) {
                console.log('🚫 Barcode event intercepted and blocked:', event.detail);
                event.stopImmediatePropagation();
                event.preventDefault();
                return false;
            }
        };
        
        // Method 3: Intercept keyboard events that might trigger barcode scanning
        keyboardInterceptor = (event) => {
            // Only intercept if not in input fields and looks like barcode scanner input
            if (event.target.tagName !== 'INPUT' && 
                event.target.tagName !== 'TEXTAREA' &&
                event.target.contentEditable !== 'true') {
                
                // Check if this looks like barcode scanner input (rapid keystrokes)
                const key = event.key;
                if (key && key.length === 1 && 
                    ((key >= '0' && key <= '9') || 
                     (key >= 'A' && key <= 'Z') || 
                     (key >= 'a' && key <= 'z'))) {
                    
                    console.log('🚫 Keyboard event intercepted (potential barcode):', key);
                    event.stopImmediatePropagation();
                    event.preventDefault();
                    return false;
                }
            }
        };
        
        // Add event listeners to intercept barcode events
        document.addEventListener('barcode_scanned', barcodeEventInterceptor, true);
        window.addEventListener('barcode_scanned', barcodeEventInterceptor, true);
        
        // Add keyboard interceptor
        document.addEventListener('keydown', keyboardInterceptor, true);
        
        console.log('✅ Global barcode service disabled via multiple methods');
        return true;
        
    } catch (error) {
        console.error('❌ Failed to disable global barcode service:', error);
        return false;
    }
};

const enableGlobalBarcodeService = () => {
    try {
        console.log('✅ Enabling global barcode service...');
        
        // Method 1: Clear global flag
        window.customScannerActive = false;
        console.log('✅ Global custom scanner flag cleared');
        
        // Method 2: Remove event interceptors
        if (barcodeEventInterceptor) {
            document.removeEventListener('barcode_scanned', barcodeEventInterceptor, true);
            window.removeEventListener('barcode_scanned', barcodeEventInterceptor, true);
            barcodeEventInterceptor = null;
        }
        
        if (keyboardInterceptor) {
            document.removeEventListener('keydown', keyboardInterceptor, true);
            keyboardInterceptor = null;
        }
        
        console.log('✅ Global barcode service enabled');
        
    } catch (error) {
        console.error('❌ Failed to enable global barcode service:', error);
    }
};

// Load QR library
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
                reject(new Error('Html5Qrcode not loaded'));
            }
        };
        script.onerror = () => reject(new Error('Failed to load Html5Qrcode'));
        document.head.appendChild(script);
    });
};

// Initialize barcode reader mode
const initBarcodeReader = () => {
    console.log('Initializing barcode reader mode');
    window.customScannerActive = true;
    // Hide camera elements
    const qrReaderElement = document.getElementById('qr-reader');
    if (qrReaderElement) {
        qrReaderElement.style.display = 'none';
    }
    
    // Update status
    updateStatus('Barcode reader mode active - scan with your barcode scanner', '#28a745');
    
    // Set up barcode event listener
    if (window.barcode && window.barcode.bus) {
        barcodeListener = (event) => {
            console.log('Barcode scanned:', event.detail.barcode);
            handleQRResult(event.detail.barcode);
        };
        
        window.barcode.bus.addEventListener('barcode_scanned', barcodeListener);
    } else {
        // Fallback: listen for keyboard input (common for USB barcode scanners)
        barcodeListener = (event) => {
            // Check if it's a barcode scanner input (usually rapid keystrokes)
            if (event.target.tagName !== 'INPUT' && event.target.tagName !== 'TEXTAREA') {
                const barcode = event.key;
                if (barcode && barcode.length === 1 && event.keyCode >= 48 && event.keyCode <= 90) {
                    // This is a simplified approach - real implementation would buffer keystrokes
                    // and detect barcode scanner patterns (rapid input ending with Enter)
                    console.log('Potential barcode input:', barcode);
                }
            }
        };
        
        document.addEventListener('keydown', barcodeListener);
    }
    
    isScannerRunning = true;
};

// Stop barcode reader
const stopBarcodeReader = () => {
    console.log('Stopping barcode reader');
    
    if (barcodeListener) {
        if (window.barcode && window.barcode.bus) {
            window.barcode.bus.removeEventListener('barcode_scanned', barcodeListener);
        } else {
            document.removeEventListener('keydown', barcodeListener);
        }
        barcodeListener = null;
    }
    
    isScannerRunning = false;
};

// Create modal HTML
const createModalHTML = () => {
    return `
        <div id="qr-scanner-modal" style="
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
            font-family: Arial, sans-serif;
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
                <h3 style="margin: 0 0 20px 0; color: #333;">Scan SETSCO Serial Number</h3>
                
                <!-- Scanner Mode Selection -->
                <div id="scanner-mode-selection" style="margin-bottom: 20px;">
                    <div style="display: flex; gap: 10px; justify-content: center; margin-bottom: 15px;">
                        <button id="camera-mode-btn" style="
                            background: #007bff;
                            color: white;
                            border: none;
                            padding: 10px 20px;
                            border-radius: 4px;
                            cursor: pointer;
                            font-size: 14px;
                        ">Camera Scanner</button>
                        <button id="barcode-mode-btn" style="
                            background: #6c757d;
                            color: white;
                            border: none;
                            padding: 10px 20px;
                            border-radius: 4px;
                            cursor: pointer;
                            font-size: 14px;
                        ">Barcode Reader</button>
                    </div>
                    <div id="mode-description" style="
                        font-size: 12px;
                        color: #666;
                        margin-bottom: 10px;
                    ">Camera mode: Use device camera to scan QR codes</div>
                </div>
                
                <div id="qr-reader-status" style="
                    margin-bottom: 15px;
                    padding: 10px;
                    border-radius: 4px;
                    background: #f8f9fa;
                    border: 1px solid #dee2e6;
                    color: #495057;
                    font-size: 14px;
                    z-index: 10;
                ">Initializing camera...</div>
                
                <div id="qr-reader" style="
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
                    flex-wrap: wrap;
                    margin-top: 20px;
                ">
                    
                    <button id="done-btn" style="
                        background: #28a745;
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 14px;
                        font-weight: bold;
                    ">Done Scanning</button>
                    
                    <button id="close-btn" style="
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
                    line-height: 1.4;
                ">
                    <strong>Instructions:</strong><br>
                    • Point camera at SETSCO barcode<br>
                    • Keep scanning to add multiple serials<br>
                    • Click "Done" when finished<br>
                    • Click "Close" to cancel
                </div>
            </div>
        </div>
    `;
};

// Create modal overlay with mobile-responsive design
const createModal = () => {
    // Remove existing modal if any
    const existingModal = document.getElementById('qr-scanner-modal');
    if (existingModal) {
        existingModal.remove();
    }

    // Create new modal
    const modalHTML = createModalHTML();
    document.body.insertAdjacentHTML('beforeend', modalHTML);

    // Get modal elements
    const modal = document.getElementById('qr-scanner-modal');
    const closeBtn = document.getElementById('close-btn');
    const doneBtn = document.getElementById('done-btn');
    // Add event listeners
    closeBtn.addEventListener('click', () => {
        closeModal();
    });

    doneBtn.addEventListener('click', () => {
        closeModal();
        showSuccessMessage('Scanning completed. You can now review and confirm your selections.');
    });

    // Close modal when clicking outside
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });

    // Prevent modal from closing when clicking inside
    const modalContent = modal.querySelector('div');
    modalContent.addEventListener('click', (e) => {
        e.stopPropagation();
    });

    return modal;
};

// Get status div with error handling
const getStatusDiv = () => {
    let statusDiv = document.getElementById('qr-reader-status');
    if (!statusDiv) {
        // Try to create it inside modal content
        const modal = document.getElementById('qr-scanner-modal');
        if (modal) {
            statusDiv = document.createElement('div');
            statusDiv.id = 'qr-reader-status';
            statusDiv.style.cssText = `
                margin-bottom: 15px;
                padding: 10px;
                border-radius: 4px;
                background: #f8f9fa;
                border: 1px solid #dee2e6;
                color: #495057;
                font-size: 14px;
                z-index: 10;
            `;
            // Insert before reader
            const reader = document.getElementById('qr-reader');
            if (reader && reader.parentNode) {
                reader.parentNode.insertBefore(statusDiv, reader);
            } else {
                modal.appendChild(statusDiv);
            }
        }
    }
    return statusDiv;
};

const updateStatus = (text, color) => {
    try {
        const statusDiv = getStatusDiv();
        if (!statusDiv) {
('Could not update status: status div not found');
            return;
        }
        statusDiv.textContent = text;
        if (color) statusDiv.style.color = color;
    } catch (e) {
('Failed to update status:', e);
    }
    };
    
    // Safe scanner stop function
    const safeStopScanner = async () => {
            try {
        if (scanner && isScannerRunning) {
                await scanner.stop();
('Scanner stopped successfully');
        }
    } catch (e) {
('Error while stopping Html5Qrcode:', e);
            } finally {
                isScannerRunning = false;
    }
};


// Initialize scanner
const initScanner = () => {
    try {
        console.log('Initializing scanner in mode:', scannerMode);
        
        // Disable global barcode service to prevent conflicts
        disableGlobalBarcodeService();
        
        // Create modal
        const modal = createModal();
        
        // Set up mode selection buttons
        setupModeSelection();
        
        // Start scanner based on mode
        setTimeout(() => {
            if (scannerMode === 'barcode_reader') {
                initBarcodeReader();
            } else {
                // Camera mode - don't auto-start, wait for user to click camera button
                updateStatus('Click "Camera Scanner" button to start camera scanning', '#007bff');
            }
        }, 100);
        
    } catch (error) {
        console.log('Failed to initialize scanner:', error);
        alert('Failed to initialize scanner: ' + error.message);
        // Re-enable global barcode service on error
        enableGlobalBarcodeService();
    }
};

// Set up mode selection buttons
const setupModeSelection = () => {
    const cameraBtn = document.getElementById('camera-mode-btn');
    const barcodeBtn = document.getElementById('barcode-mode-btn');
    const modeDescription = document.getElementById('mode-description');
    
    if (!cameraBtn || !barcodeBtn || !modeDescription) return;
    
    // Update button states based on current mode
    const updateModeButtons = () => {
        if (scannerMode === 'camera') {
            cameraBtn.style.background = '#007bff';
            barcodeBtn.style.background = '#6c757d';
            modeDescription.textContent = 'Camera mode: Use device camera to scan QR codes';
        } else {
            cameraBtn.style.background = '#6c757d';
            barcodeBtn.style.background = '#007bff';
            modeDescription.textContent = 'Barcode reader mode: Use USB/wireless barcode scanner';
        }
    };
    
    // Initial state
    updateModeButtons();
    
    // Camera mode button
    cameraBtn.addEventListener('click', () => {
        if (scannerMode === 'barcode_reader') {
            stopBarcodeReader();
        }
        scannerMode = 'camera';
        updateModeButtons();
        
        // Show camera element
        const qrReaderElement = document.getElementById('qr-reader');
        if (qrReaderElement) {
            qrReaderElement.style.display = 'block';
        }
        
        // Start camera scanner
        startScanner();
    });
    
    // Barcode reader mode button
    barcodeBtn.addEventListener('click', () => {
        if (scanner) {
            scanner.stop().catch(console.error);
            scanner = null;
        }
        scannerMode = 'barcode_reader';
        updateModeButtons();
        
        // Hide camera element
        const qrReaderElement = document.getElementById('qr-reader');
        if (qrReaderElement) {
            qrReaderElement.style.display = 'none';
        }
        
        // Start barcode reader
        initBarcodeReader();
    });
};

    // Request camera permission early (helps populate device labels)
    const requestCameraPermission = async () => {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
        let stream;
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } } });
        } catch (e) {
            // ignored; permissions may be denied or prompt canceled
        } finally {
            if (stream) {
                stream.getTracks().forEach((t) => t.stop());
            }
        }
    };

    // Find preferred cameraId (prefer back camera)
    const getPreferredCameraId = async () => {
        if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return null;
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videos = devices.filter((d) => d.kind === 'videoinput');
        if (!videos.length) return null;
        // Try to find a back camera by label
        const back = videos.find((d) => /back|rear|environment/i.test(d.label));
        return (back || videos[0]).deviceId || null;
    };

    // Start scanner
    const startScanner = async () => {
        try {
            updateStatus('Starting camera...');

            const qrReaderElement = document.getElementById('qr-reader');
            if (!qrReaderElement) {
                throw new Error('QR reader element not found');
            }

            // Clear previous scanner
            qrReaderElement.innerHTML = '';

            // Ensure permission prompt shown first so labels populate
            await requestCameraPermission();

            // Initialize Html5Qrcode
            scanner = new Html5Qrcode('qr-reader');
            
            const baseConfig = {
                fps: 12,
                qrbox: { width: 260, height: 260 },
                aspectRatio: 1.0,
                disableFlip: false,
            };

            let started = false;

            // 1) Try specific deviceId (prefer back camera)
            try {
                const cameraId = await getPreferredCameraId();
                if (cameraId) {
                    await scanner.start(
                        cameraId, // IMPORTANT: pass cameraId string (not constraints object)
                        baseConfig,
                        (decodedText) => handleQRResult(decodedText),

                    );
                    started = true;
                }
            } catch (e) {
('Failed with deviceId:', e);
            }

            // 2) Try facingMode environment
            if (!started) {
                try {
                    await scanner.start(
                        { facingMode: 'environment' },
                        baseConfig,
                        (decodedText) => handleQRResult(decodedText),

                    );
                    started = true;
                } catch (e) {
('Failed with facingMode environment:', e);
                }
            }

            // 3) Try default (let browser choose)
            if (!started) {
                try {
                    await scanner.start(
                        {},
                        baseConfig,
                        (decodedText) => handleQRResult(decodedText),

                    );
                    started = true;
                } catch (e) {
('Failed with default camera selection:', e);
                }
            }

            if (started) {
            isScannerRunning = true;
                updateStatus('Camera ready - scan QR code');
                return;
            }
            
            throw new Error('Could not start camera with any method');
        } catch (error) {
('Failed to start scanner:', error);
            updateStatus('Failed to start scanner: ' + error.message, 'red');
        }
    };


    // Handle QR result
    const handleQRResult = async (decodedText) => {
        try {
            // Stop scanner first
            await safeStopScanner();
            
('QR Code scanned:', decodedText);
('Raw QR content:', JSON.stringify(decodedText));
            
            // Extract SETSCO number from QR code content
            let setscoNumber = decodedText;
            
        // For direct SETSCO format (e.g., "av00001"), use the entire text
        // For complex format (e.g., "SETSCO(av00001)"), extract the value
        let setscoMatch = null;
        
        // Pattern 1: SETSCO(value) - for complex format
        setscoMatch = decodedText.match(/SID\(([^)]+)\)/);
        if (setscoMatch) {
            setscoNumber = setscoMatch[1];
('Extracted SETSCO number from complex format:', setscoNumber);
        } else {
            // Pattern 2: SETSCO\(value\) (escaped parentheses)
            setscoMatch = decodedText.match(/SID\\(([^)]+)\\)/);
            if (setscoMatch) {
                setscoNumber = setscoMatch[1];
('Extracted SETSCO number from escaped format:', setscoNumber);
            } else {
                // Pattern 3: SETSCO:value or SETSCO=value
                setscoMatch = decodedText.match(/SID[:=]([^\s,)]+)/);
                if (setscoMatch) {
                    setscoNumber = setscoMatch[1];
('Extracted SETSCO number from colon format:', setscoNumber);
                } else {
                    // Pattern 4: Direct format - check if it looks like a SETSCO serial
                    const directMatch = decodedText.match(/^([A-Za-z]{2,3}\d{5,})$/);
                    if (directMatch) {
                        setscoNumber = directMatch[1];
('Using direct SETSCO format:', setscoNumber);
                    } else {
                        // If no pattern matches, use the entire text as fallback
                        setscoNumber = decodedText.trim();
('Using entire text as SETSCO number:', setscoNumber);
                    }
                }
            }
        }
        
('Final extracted SETSCO number:', setscoNumber);
('Target field:', targetField);
            
        // Validate the extracted serial number
        if (!setscoNumber || setscoNumber.trim() === '') {
            throw new Error('No valid SETSCO serial number found in QR code');
        }
        
        // Clean the serial number
        setscoNumber = setscoNumber.trim();
        
        // RANGE MODE: one button flow (first scan = start, second = end)
        if (isRangeMode || targetField === 'range_start_scan_input' || targetField === 'range_end_scan_input' || targetField === 'start_serial_scan' || targetField === 'end_serial_scan') {
            // Enter range mode on first invocation
            isRangeMode = true;
            if (rangePhase === 'start') {
                // Set start
                await setRangeStartSerial(setscoNumber);
                rangePhase = 'end';
                showSuccessMessage(`Start set: ${setscoNumber}. Now scan End serial.`);
                setTimeout(() => openScanner(), 300);
                return;
            } else {
                // Set end and add range
                await setRangeEndSerial(setscoNumber);
                await addRangeToList();
                await reloadWizardModal();
                showSuccessMessage(`Range added. You can scan next Start.`);
                rangePhase = 'start';
                setTimeout(() => openScanner(), 300);
                return;
            }
        }
        
        // INDIVIDUAL MODE (default)
        if (targetField === 'individual_scan_input') {
            await addIndividualSerial(setscoNumber);
            showSuccessMessage(`Added: ${setscoNumber}`);
            setTimeout(() => openScanner(), 300);
            return;
        }
        
        // Legacy support (if any left)
            if (targetField === 'start_serial_scan') {
            await setRangeStartSerial(setscoNumber);
            showSuccessMessage(`Start set: ${setscoNumber}`);
            setTimeout(() => openScanner(), 300);
            return;
            } else if (targetField === 'end_serial_scan') {
            await setRangeEndSerial(setscoNumber);
            showSuccessMessage(`End set: ${setscoNumber}`);
            setTimeout(() => openScanner(), 300);
            return;
        }
        
        // If none of the above, show error or default behavior
(`Unknown target field: ${targetField}`);
        alert(`Error: Unknown field type. Please try again.`);
        setTimeout(() => openScanner(), 1000);
        
    } catch (error) {
        showErrorMessage(`${error.message}`);
        setTimeout(() => openScanner(), 1000);
    }
};

// Show success message without closing scanner
const showSuccessMessage = (message) => {
    const statusDiv = getStatusDiv();
    if (statusDiv) {
        statusDiv.textContent = message;
        statusDiv.style.color = 'green';
        statusDiv.style.backgroundColor = '#d4edda';
        statusDiv.style.border = '1px solid #c3e6cb';
        statusDiv.style.padding = '10px';
        statusDiv.style.borderRadius = '4px';
        statusDiv.style.marginBottom = '10px';
        statusDiv.style.display = 'block';
    }
    
    // Also show a brief notification
    const notification = document.createElement('div');
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #28a745;
        color: white;
        padding: 10px 15px;
        border-radius: 4px;
        z-index: 10000;
        font-size: 14px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    `;
    document.body.appendChild(notification);
    
    // Remove notification after 3 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    }, 3000);
};

// Show error message without closing scanner
const showErrorMessage = (message) => {
    const statusDiv = getStatusDiv();
    if (statusDiv) {
        statusDiv.textContent = message;
        statusDiv.style.color = '#721c24';
        statusDiv.style.backgroundColor = '#f8d7da';
        statusDiv.style.border = '1px solid #f5c6cb';
        statusDiv.style.padding = '10px';
        statusDiv.style.borderRadius = '4px';
        statusDiv.style.marginBottom = '10px';
        statusDiv.style.display = 'block';
    }
    
    // Also show a brief notification
    const notification = document.createElement('div');
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #dc3545;
        color: white;
        padding: 10px 15px;
        border-radius: 4px;
        z-index: 10000;
        font-size: 14px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    `;
    document.body.appendChild(notification);
    
    // Remove notification after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    }, 5000);
};

// Ensure modal exists and has qr-reader
const ensureScannerModal = () => {
    let modal = document.getElementById('qr-scanner-modal');
    if (!modal) {
        modal = createModal();
    }
    // Ensure qr-reader exists
    let reader = document.getElementById('qr-reader');
    if (!reader) {
        // Rebuild modal to guarantee structure
        modal.remove();
        modal = createModal();
        reader = document.getElementById('qr-reader');
    }
    return { modal, reader };
};

// Open scanner for continuous scanning without tearing modal down
const openScanner = () => {
    // Ensure modal and reader are present
    ensureScannerModal();
    // Start scanner after a brief delay to allow layout
    setTimeout(() => {
        startScanner();
    }, 150);
};

    // Reload only the wizard modal (no full page reload)
    const reloadWizardModal = async () => {
        try {
            if (currentEnv && currentEnv.services && currentEnv.services.action && typeof currentEnv.services.action.doAction === 'function') {
                await currentEnv.services.action.doAction({
                    type: 'ir.actions.act_window',
                    res_model: 'setsco.serial.selection.wizard',
                    res_id: wizardId,
                    views: [[false, 'form']],
                    target: 'new',
                });
            } else {
                // Fallback: try to refresh form content
                updateFormDisplay();
            }
        } catch (e) {
('Failed to reload wizard modal:', e);
        }
    };

// Add individual serial to list
const addIndividualSerial = async (serialNumber) => {
    try {
('Adding individual serial:', serialNumber);
        
        const result = await rpc('/web/dataset/call_button', {
            model: rpcModel,
            method: 'add_individual_serial_from_scan',
            args: [wizardId, serialNumber],
            kwargs: {}
        });

        
        if (result && result.type === 'ir.actions.client' && result.tag === 'display_notification') {
            const { title, message, type } = result.params;
(`Success: ${title} - ${message}`);
            
            // Reload only the wizard modal
            await reloadWizardModal();
            
        } else if (result && result.error) {
            throw new Error(result.error.data.message || 'Failed to add serial');
        } else {
            if (!result){
              throw new Error('Serial already scanned in the list');
            };
('Unexpected result format:', result);
        }
        
    } catch (error) {
('Failed to add individual serial:', error);
        throw error;
    }
};

// Set range start serial
const setRangeStartSerial = async (serialNumber) => {
    try {
('Setting range start serial:', serialNumber);
        
        const result = await rpc('/web/dataset/call_button', {
            model: rpcModel,
            method: 'set_range_start_serial_from_scan',
            args: [wizardId, serialNumber],
            kwargs: {}
        });
        
        if (result && result.type === 'ir.actions.client' && result.tag === 'display_notification') {
            const { title, message, type } = result.params;
(`Success: ${title} - ${message}`);
            
            await reloadWizardModal();
            
        } else if (result && result.error) {
            throw new Error(result.error.data.message || 'Failed to set range start serial');
        } else {
('Unexpected result format:', result);
        }
        
    } catch (error) {
('Failed to set range start serial:', error);
        throw error;
    }
};

// Set range end serial
const setRangeEndSerial = async (serialNumber) => {
    try {
('Setting range end serial:', serialNumber);
        
        const result = await rpc('/web/dataset/call_button', {
            model: rpcModel,
            method: 'set_range_end_serial_from_scan',
            args: [wizardId, serialNumber],
            kwargs: {}
        });
        
        if (result && result.type === 'ir.actions.client' && result.tag === 'display_notification') {
            const { title, message, type } = result.params;
(`Success: ${title} - ${message}`);
            
            await reloadWizardModal();
            
        } else if (result && result.error) {
            throw new Error(result.error.data.message || 'Failed to set range end serial');
                } else {
('Unexpected result format:', result);
        }
        
    } catch (error) {
('Failed to set range end serial:', error);
        throw error;
    }
};

// Add range to list (wizard server method)
const addRangeToList = async () => {
    try {
        const result = await rpc('/web/dataset/call_button', {
            model: rpcModel,
            method: 'action_add_range_to_list',
            args: [wizardId],
            kwargs: {}
        });
        return result;
    } catch (error) {
('Failed to add range to list:', error);
        throw error;
    }
};

// Update form display in real-time
const updateFormDisplay = () => {
    try {
        // Preferred: use Odoo action service to reload the current view
        if (currentEnv && currentEnv.services && currentEnv.services.action && typeof currentEnv.services.action.reload === 'function') {
            currentEnv.services.action.reload();
            return;
        }
        
        // Fallbacks below if action.reload not available
        const formView = document.querySelector('.o_form_view');
        if (formView) {
            const formController = formView.__owl__;
            if (formController && formController.env && formController.env.services) {
                const actionService = formController.env.services.action;
                if (actionService && actionService.reload) {
                    actionService.reload();
                    return;
                }
            }
        }
        
        const serialListContainer = document.querySelector('.o_list_view');
        if (serialListContainer) {
            const listController = serialListContainer.__owl__;
            if (listController && listController.render) {
                listController.render();
            }
        }
        
    } catch (error) {
('Form update failed, continuing with scanning:', error);
        }
    };
    
    // Manual input handler
    const handleManualInput = () => {
        const input = prompt('Please enter the serial number manually:');
        if (input && input.trim()) {
            handleQRResult(input.trim());
        }
    };
    
    // Close modal function
    const closeModal = async () => {
        try {
            // Stop camera scanner if running
            await safeStopScanner();
            
            // Stop barcode reader if running
            if (scannerMode === 'barcode_reader') {
                stopBarcodeReader();
            }
            
            // Re-enable global barcode service
            enableGlobalBarcodeService();
            
        } catch (error) {
            console.log('Error during modal close:', error);
            // Ensure global barcode service is re-enabled even on error
            enableGlobalBarcodeService();
        }
        
        const modalOverlay = document.getElementById('qr-scanner-modal');
        if (modalOverlay && modalOverlay.parentNode) {
            modalOverlay.parentNode.removeChild(modalOverlay);
        }
    };
    
// Main action
const CustomQRScan = {
    dependencies: ['web.core'],
    start: async function (params) {
        try {
('CustomQRScan started with params:', params);
            
            // Extract parameters
            targetField = params.target_field || 'individual_scan_input';
            wizardId = params.wizard_id;
            
            // Initialize range mode flag based on target
            isRangeMode = (targetField && targetField.indexOf('range') !== -1) || targetField === 'start_serial_scan' || targetField === 'end_serial_scan';
            rangePhase = 'start';
            
            if (!wizardId) {
                throw new Error('Wizard ID is required');
            }
            
            // Load QR library
            await loadQRLibrary();
            
            // Initialize scanner
            initScanner();
            
        } catch (error) {
('Failed to start CustomQRScan:', error);
            alert('Failed to start scanner: ' + error.message);
        }
    }
};

// Register the action
registry.category("actions").add("custom_qr_scan", async (env, action) => {
    try {
        console.log('custom_qr_scan invoked with action:', action);
        
        // Save env for later UI refreshes
        currentEnv = env;
        
        // Initialize barcode control service (optional)
        try {
            barcodeControlService = env.services.barcode_control;
            console.log('✅ Barcode control service initialized');
        } catch (error) {
            console.log('⚠️ Barcode control service not available (this is OK)');
        }
        
        // Extract parameters from action
        targetField = (action && action.params && action.params.target_field) ? action.params.target_field : 'individual_scan_input';
        wizardId = action && action.params ? action.params.wizard_id : null;
        rpcModel = (action && action.params && action.params.model) ? action.params.model : 'setsco.serial.selection.wizard';
        scannerMode = (action && action.params && action.params.scanner_mode) ? action.params.scanner_mode : 'camera';
        
        // Initialize range scanning state based on targetField
        isRangeMode = !!(targetField && (targetField === 'range' || targetField.indexOf('range') !== -1 || targetField === 'start_serial_scan' || targetField === 'end_serial_scan'));
        rangePhase = 'start';
        
        if (!wizardId) {
            throw new Error('Wizard ID is required');
        }
        
        console.log('Target field:', targetField);
        console.log('Wizard ID:', wizardId);
        
        // Load QR library and initialize scanner
        await loadQRLibrary();
        
        // Add a small delay to ensure barcode service is fully initialized
        setTimeout(() => {
            console.log('🚀 Starting scanner initialization...');
            initScanner();
        }, 100);
    } catch (error) {
        console.log('Failed to execute custom_qr_scan action:', error);
        alert('Failed to start scanner: ' + error.message);
        // Ensure global barcode service is re-enabled on error
        enableGlobalBarcodeService();
    }
});
