#coding: utf-8

import logging

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

HELP_NOTE = """It is possible to define HTML tags (e.g. <b></b> or <a href=''></a> to beautify alert appearance.
You can also apply dynamic placeholders to retrieve values from a linked object by applying the same syntax
that is used for Odoo email templates. For example, {{ object.name }} to show a quotation number"""


class smart_warning(models.Model):
    """
    The model to keep alerts data
    """
    _name = "smart.warning"
    _description = "Smart Warning"

    @api.depends("model")
    def _compute_ir_model_id(self):
        """
        Compute method for ir_model_id

        Extra info:
         * we use compute/inverse/onchange instrad of simple 'related' to the backward compatibility
        """
        for warn in self:
            warn.ir_model_id = self.env["ir.model"].search([("model", "=", warn.model)])

    @api.depends("ir_model_id")
    def _compute_model(self):
        """
        Compute (onchnage) method for model and domain
        """
        for warn in self:
            warn.model = warn.ir_model_id and warn.ir_model_id.model or False
            warn.domain = "[]"

    @api.depends("user_group_ids", "user_group_ids.users")
    def _compute_access_user_ids(self):
        """
        Compute method for access_user_ids
        """
        for warn in self:
            users = warn.user_group_ids.mapped("users")
            warn.access_user_ids = [(6, 0, users.ids)]

    def _inverse_ir_model_id(self):
        """
        Inverse method for ir_model_id
        """
        for warn in self:
            warn.model = warn.ir_model_id and warn.ir_model_id.model or False

    name = fields.Char("Alert Title", required=True, translate=True, help=HELP_NOTE)
    description = fields.Text("Alert Text", required=True, translate=True, help=HELP_NOTE,)
    css_class = fields.Selection(
        [("danger", "Danger"), ("warning", "Warning"), ("info", "Info"), ("success", "Success"),],
        string="Type",
        required=True,
        default="danger",
    )
    ir_model_id = fields.Many2one(
        "ir.model",
        string="Document Type",
        compute=_compute_ir_model_id,
        inverse=_inverse_ir_model_id,
    )
    model = fields.Char(string="Model", compute=_compute_model, readonly=False, store=True)
    domain = fields.Text(
        string="Filters",
        compute=_compute_model,
        readonly=False,
        store=True,
        default="[]",
        help="""Warning will be shown only in case a record satisfies those filters.
Leave it empty to show this alert for all records of this document type.""",
    )
    user_group_ids = fields.Many2many(
        "res.groups",
        "res_groups_smart_warning_rel_table",
        "res_groups_id",
        "smart_warning_id",
        string="Show only for user groups",
        help="""If selected, this alert will be shown only for users which belong to these groups.
If empty, it will be shown for everyone""",
    )
    access_user_ids = fields.Many2many(
        "res.users",
        "res_users_smart_warning_rel_table",
        "res_users_id",
        "smart_warning_id",
        string="Access Users",
        compute=_compute_access_user_ids,
        compute_sudo=True,
        store=True,
    )
    active = fields.Boolean(string="Active", default=True)
    sequence = fields.Integer(string="Sequence", default=0,)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)

    _order = "sequence, id"

    @api.model
    def action_return_warnings(self, res_model, res_id):
        """
        The method to find all warning related to this record and prepare them in js formats

        Args:
         * res_model - char - model name
         * res_id - int - id of a document

        Methods:
         * _render_template_inline_template of mail.render.mixin

        Returns:
         * list of warning dicts:
          ** name
          ** description
          ** css_class
        """
        def render_dynamic(place_text):
            """
            The method to render text for dynamic clauses

            Args:
             * place_text - str

            Returns:
             * str
            """
            result = place_text
            if place_text.find("{{") != -1:
                try:
                    result = self.env["mail.render.mixin"]._render_template_inline_template(
                        place_text,  res_model, [res_id],
                    ).get(res_id)
                except Exception as er:
                    _logger.warning("Alert {} cannot be parsed: {}".format(place_text, er))
                    result = place_text
            return result

        def prepare_js_dict(warn):
            """
            The method to prepare dict needed to show alert

            Args:
             * warn - smart.warning instance

            Returns:
             * dict of name (string), description (string, HTML-like), css_class - string (see css_class above)
            """
            alert_name = render_dynamic(warn.name)
            alert_text = render_dynamic(warn.description)
            return {"id": warn.id, "name": alert_name, "description": alert_text, "css_class": warn.css_class}

        if not res_model or not res_id:
            return []

        self = self.with_context(lang=self.env.user.lang)
        warnings = self.search([
            ("model", "=", res_model), "|", ("access_user_ids", "=", False), ("access_user_ids", "in", self.env.uid),
        ])
        res = []
        for warn in warnings:
            if warn.domain and warn.domain != "[]":
                try:
                    domain = [("id", "=", res_id)] + safe_eval(warn.domain)
                    model_cl = self.env[res_model]
                    if self.env[res_model].with_context(active_test=False).search_count(domain, limit=1):
                        res.append(prepare_js_dict(warn))
                except Exception as er:
                    _logger.warning("Domain {} for alert {} is not correctly set: {}".format(warn.domain, warn.id, er))
            else:
                res.append(prepare_js_dict(warn))
        return res
