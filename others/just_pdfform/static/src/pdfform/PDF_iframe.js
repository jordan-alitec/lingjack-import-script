/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { renderToString } from "@web/core/utils/render";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { normalizePosition, pinchService, isVisible } from "./utils";
import { Field } from "@web/views/fields/field";
import { parseXML, createTextNode } from "@web/core/utils/xml";
import { Component, onWillDestroy, xml } from "@odoo/owl";

export class PDFIframe {
  /**
   * Renders custom elements inside the PDF.js iframe
   * @param {HTMLIFrameElement} iframe
   * @param {Document} root
   * @param {Object} env
   * @param {Object} owlServices
   * @param {Object} props
   */
  constructor(root, env, owlServices, props) {
    this.root = root;
    this.env = env;
    Object.assign(this, owlServices);
    this.props = props;
    this.cleanupFns = [];
    this.preList = [];
    this.readonly = props.readonly;
    this.waitForPagesToLoad();
  }

  waitForPagesToLoad() {
    // const errorElement = this.root.querySelector("#errorMessage");
    // if (errorElement && isVisible(errorElement)) {
    if (! this.props.hasTemplate ) {
      return this.dialog.add(AlertDialog, {
        body: _t("Need a valid PDF to add fields!"),
      });
    }
    this.pageCount = this.root.querySelectorAll(".page").length;
    if (this.pageCount > 0) {
      this.start();
    } else {
      setTimeout(() => this.waitForPagesToLoad(), 50);
    }
  }

  start() {
    this.pdfFields = this.getpdfFields();
    this.loadCustomCSS().then(() => {
      this.pageCount = this.root.querySelectorAll(".page").length;
      this.clearNativePDFViewerButtons();
      this.startPinchService();
      this.preRender();
      this.renderSidebar();
      this.renderpdfFields();
    });
  }

  unmount() {
    this.cleanupFns.forEach((fn) => typeof fn === "function" && fn());
  }

  async loadCustomCSS() {
    // var script = this.root.createElement("script");
    // script.src = "/just_pdfform/static/lib/PDFPrintService.js";
    // script.type = "module";
    // this.root.body.appendChild(script);

    this.root
      .querySelector("head")
      .insertAdjacentHTML(
        "beforeend",
        '<link rel="stylesheet" href="/just_pdfform/static/src/css/pdfForm.css">'
      );
    this.root.querySelector("body").style.overflow = "hidden";

    this.root.defaultView.template = this.props.template;
  }

  clearNativePDFViewerButtons() {
    const selectors = [
      "#pageRotateCw",
      "#pageRotateCcw",
      "#openFile",
      // "#presentationMode",
      "#viewBookmark",
      // "#print",
      "#download",
      "#secondaryOpenFile",
      "#secondaryPresentationMode",
      "#secondaryViewBookmark",
      "#secondaryPrint",
      "#secondaryDownload",
    ];
    if (this.props.defView) {
      selectors.push("#presentationMode", "#print");
    }
    const elements = this.root.querySelectorAll(selectors.join(", "));
    elements.forEach((element) => {
      element.style.display = "none";
    });
    this.root.querySelector("#lastPage").nextElementSibling.style.display =
      "none";
    // prevent password from being autocompleted in search input
    this.root.querySelector("#findInput").value = "";
    this.root.querySelector("#findInput").setAttribute("autocomplete", "off");
    const passwordInputs = this.root.querySelectorAll("[type=password]");
    Array.from(passwordInputs).forEach((input) =>
      input.setAttribute("autocomplete", "new-password")
    );
  }

  /**
   * Used when signing a sign request
   */
  renderSidebar() { }

  async renderpdfFields() {
    for (const page in this.pdfFields) {
      const pageContainer = this.getPageContainer(page);
      for (const id in this.pdfFields[page]) {
        const pdfField = this.pdfFields[page][id];
        pdfField.el = await this.renderpdfField(pdfField, pageContainer, id);
        this.enableCustom({ el: pdfField.el, data: pdfField.data });
      }
    }
    this.updateFontSize();
    this.postRender();
  }

  async renderpdfField(pdfField, pageContainer, id) {
    var field = this.getContext(pdfField.data);
    if (this.props.defView) {
      pageContainer.insertAdjacentHTML(
        "beforeend",
        renderToString("pdfForm.newField", {
          required: true,
          editMode: true,
          readonly: true,
          updated: true,
          option_ids: [],
          name: field.name,
          type: field.type,
          placeholder: field.props.placeholder,
          classes: `o_color_responsible_yellow`,
          style: field.props.style,
        })
      );
    } else {
      const app = renderToString.app;
      app.env = field.env;
      const ctx = app.makeNode(Field, field.props);
      await app.mountNode(ctx, pageContainer);
    }
    var fieldElement = pageContainer.lastChild;
    if (field.props.invisible && !this.props.defView) {
      fieldElement.style.display = "none";
    }
    if (this.allowEdit) {
      fieldElement.dataset.id = id;
      //fieldElement.querySelector('.fa-times').addEventListener('click', this.deletepdfField(pdfField).bind(this));
      fieldElement.classList.add("o_sign_sign_item");
    }

    return fieldElement;
  }

  /**
   * register sign item events. in template edition, should be overwritten to add drag/drop events
   */
  enableCustom(pdfField) { }

  startPinchService() {
    const pinchTarget = this.root.querySelector("#viewerContainer #viewer");
    const pinchServiceCleanup = pinchService(pinchTarget, {
      decreaseDistanceHandler: () =>
        this.root.querySelector("button#zoomIn").click(),
      increaseDistanceHandler: () =>
        this.root.querySelector("button#zoomOut").click(),
    });
    this.cleanupFns.push(pinchServiceCleanup);
  }

  /**
   * Extends the rendering context of the sign item based on its data
   * @param {pdfField.data} pdfField
   * @returns {Object}
   */
  getContext(pdfField) { }

  /**
   * PDF.js removes custom elements every once in a while.
   * So we need to constantly re-render them :(
   * We keep the elements stored in memory, so we don't need to call the qweb engine everytime a element is detached
   */
  refreshpdfFields() {
    for (const page in this.pdfFields) {
      const pageContainer = this.getPageContainer(page);
      for (const id in this.pdfFields[page]) {
        const pdfField = this.pdfFields[page][id].el;
        if (
          !pdfField.parentElement ||
          !pdfField.parentElement.classList.contains("page")
        ) {
          pageContainer.append(pdfField);
        }
      }
    }
    this.updateFontSize();
  }

  /**
   * Hook executed before rendering the sign items and the sidebar
   */
  preRender() {
    const viewerContainer = this.root.querySelector("#viewerContainer");
    viewerContainer.style.visibility = "visible";
    this.setInitialZoom();
  }

  get normalSize() {
    return this.root.querySelector(".page").clientHeight * 0.015;
  }

  /**
   * Updates the font size of all sign items in case there was a zoom/resize of element
   */
  updateFontSize() {
    for (const page in this.pdfFields) {
      for (const id in this.pdfFields[page]) {
        const pdfField = this.pdfFields[page][id];
        this.updatepdfFieldFontSize(pdfField);
      }
    }
  }

  /**
   * Updates the font size of a determined sign item
   * @param {pdfField}
   */
  updatepdfFieldFontSize({ el, data }) {
    const largerTypes = ["signature", "digitalsign", "textarea", "selection"];
    const size = largerTypes.includes(data.props.fieldInfo.widget)
      ? this.normalSize
      : parseFloat(el.clientHeight);
    el.style.fontSize = `${size * 0.8}px`;
  }

  async rotatePDF(e) {
    const button = e.target;
    button.setAttribute("disabled", "");
    const result = await this.props.rotatePDF();
    if (result) {
      this.root.querySelector("#pageRotateCw").click();
      button.removeAttribute("disabled");
      this.refreshpdfFields();
    }
  }

  setInitialZoom() {
    let button = this.root.querySelector("button#zoomIn");
    if (!this.env.isSmall) {
      button = this.root.querySelector("button#zoomOut");
      button.click();
    }
    button.click();
  }

  postRender() {
    const refreshpdfFieldsIntervalId = setInterval(
      () => this.refreshpdfFields(),
      2000
    );
    this.cleanupFns.push(() => clearInterval(refreshpdfFieldsIntervalId));
  }

  /**
   * Creates rendering context for the sign item based on the sign item type
   * @param {number} typeId
   * @returns {Object} context
   */
  createpdfFieldDataFromType(name) {
    //const record = this.model.root;
    // const node = parseXML(xml`"<field name='{{name}}'/>"`);
    var node = document.createElement("field");
    node.setAttribute("name", name);
    const fieldInfo = Field.parseFieldNode(
      node,
      this.props.models,
      this.props.resModel,
      "form",
      ""
    );
    fieldInfo.position = {
      page: 1,
      posX: 0.5,
      posY: 0.5,
      width: 0.2,
      height: 0.015,
      alignment: "center",
    };
    const fieldprops = {
      id: name + "_0",
      name: fieldInfo.name,
      record: this.env.model.root,
      field: fieldInfo.field,
      fieldInfo: fieldInfo,
    };

    fieldprops.readonly = false;
    var newField = new Field(fieldprops, this.env, this);
    return { data: newField, el: null };
  }

  /**
   * @typedef {Object} pdfField
   * @property {Object} data // sign item data returned from the search_read
   * @property {HTMLElement} el // html element of the sign item
   */

  /**
   * Converts a list of items to an object indexed by page and id
   * @returns { Object.<page:number, Object.<id:number, pdfField >>}
   */
  getpdfFields() {
    const pdfFields = {};
    this.props.pdfFields.forEach((pdfField, id) => {
      var page = pdfField.props.fieldInfo.position.page;
      if (!pdfFields[page]) pdfFields[page] = {};
      pdfFields[page][id] = {
        data: pdfField,
        el: null,
      };
    });
    return pdfFields;
  }

  /**
   * Gets page container from the page number
   * @param {Number} page
   * @returns {HTMLElement} pageContainer
   */
  getPageContainer(page) {
    const pageContainer = this.root.querySelector(
      `.page[data-page-number="${page}"]`
    );
    return pageContainer;
  }
}
