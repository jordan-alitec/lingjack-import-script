import { patch } from '/web/static/src/core/utils/patch.js';

patch(PDFViewerApplication, {
  beforePrint() {
    this._printAnnotationStoragePromise = this.pdfScriptingManager.dispatchWillPrint().catch(() => { }).then(() => {
      var _this$pdfDocument4;

      return (_this$pdfDocument4 = this.pdfDocument) === null || _this$pdfDocument4 === void 0 ? void 0 : _this$pdfDocument4.annotationStorage.print;
    });

    if (this.printService) {
      return;
    }

    if (!this.supportsPrinting) {
      this.l10n.get("printing_not_supported").then(msg => {
        this._otherError(msg);
      });
      return;
    }

    if (!this.pdfViewer.pageViewsReady) {
      this.l10n.get("printing_not_ready").then(msg => {
        window.alert(msg);
      });
      return;
    }

    const pagesOverview = this.pdfViewer.getPagesOverview();
    const printContainer = this.appConfig.printContainer;

    const printResolution = PDFViewerApplicationOptions.get("printResolution");

    const optionalContentConfigPromise = this.pdfViewer.optionalContentConfigPromise;
    const printService = PDFViewerApplication.PDFPrintServiceFactory.instance.createPrintService(this.pdfDocument, pagesOverview, printContainer, printResolution, optionalContentConfigPromise, this._printAnnotationStoragePromise, this.l10n);


    PDFPrintService.prototype.useRenderedPage = function () {
      this.throwIfInactive();
      const img = document.createElement("img");
      const scratchCanvas = this.scratchCanvas;

      if ("toBlob" in scratchCanvas) {
        scratchCanvas.toBlob(function (blob) {
          img.src = URL.createObjectURL(blob);
        });
      } else {
        img.src = scratchCanvas.toDataURL();
      }

      const wrapper = document.createElement("div");
      wrapper.className = "printedPage";
      if (window.template) wrapper.append(img);

      wrapper.style.position = "relative";
      const currentPage = document.querySelectorAll(".page")[this.currentPage];
      //const scale = this.pagesOverview[this.currentPage].height / currentPage.clientHeight;
      const scale = 1132 / currentPage.clientHeight;

      currentPage.childNodes.forEach(function (node) {
        if (node.className !== "textLayer" && node.className !== "canvasWrapper" && node.className !== "loadingIcon notVisible") {
          var clonenode = node.cloneNode(true);
          clonenode.style.fontSize = parseFloat(clonenode.style.fontSize) * scale + "px";
          wrapper.append(clonenode);
        }
      });

      this.printContainer.append(wrapper);
      return new Promise(function (resolve, reject) {
        img.onload = resolve;
        img.onerror = reject;
      });
    };

    this.printService = printService;
    this.forceRendering();
    printService.layout();
    this.externalServices.reportTelemetry({
      type: "print"
    });

    if (this._hasAnnotationEditors) {
      this.externalServices.reportTelemetry({
        type: "editing",
        data: {
          type: "print"
        }
      });
    }
  }
});

PDFViewerApplication.eventBus._off("beforeprint", PDFViewerApplication._boundEvents.beforePrint);
PDFViewerApplication._boundEvents.beforePrint = PDFViewerApplication.beforePrint.bind(PDFViewerApplication);
PDFViewerApplication.eventBus._on("beforeprint", PDFViewerApplication._boundEvents.beforePrint);