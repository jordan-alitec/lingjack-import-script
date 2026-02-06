import logging

from odoo import models, fields, api, _, tools
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class IrUiView(models.Model):
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-branches
    # pylint: disable=translation-positional-used

    _inherit = 'ir.ui.view'

    type = fields.Selection(
        selection_add=[('pdfForm', 'PDF Form')],
        ondelete={'pdfForm': 'cascade'}
    )

    def _get_view_info(self):
        # return {'pdfForm': {'icon': 'fa fa-code-fork'},'eReport': {'icon': 'fa fa-newspaper-o'}} | super()._get_view_info()
        return {'pdfForm': {'icon': 'fa fa-code-fork'}} | super()._get_view_info()

    #def _postprocess_tag_node(self, node, name_manager, node_info):
    #    if node.get('bg_color_field'):
    #        name_manager.has_field(node.get('bg_color_field'), {})
    #    if node.get('fg_color_field'):
    #        name_manager.has_field(node.get('fg_color_field'), {})
    #    for child in node:
    #        if child.tag == 'field':
    #            name_manager.has_field(child.get('name'), {})
    #            node.remove(child)

    #def _postprocess_tag_arrow(self, node, name_manager, node_info):
    #    if node.get('source'):
    #        name_manager.has_field(node.get('source'), {})
    #    if node.get('destination'):
    #        name_manager.has_field(node.get('destination'), {})
    #    for child in node:
    #        if child.tag == 'field':
    #            name_manager.has_field(child.get('name'), {})
    #            node.remove(child)

    #def _postprocess_tag_diagram_plus(self, node, name_manager, node_info):
    #    # Here we store children in node_info, because we need to avoid futher
    #    # post-processing of arrow/node nodes in context of diagram model.
    #    node_info['children'] = []
    #    for child in node:
    #        if child.tag == 'arrow':
    #            self.with_context(
    #                base_model_name=name_manager.model._name,
    #            )._postprocess_view(
    #                child, child.get('object'), editable=node_info['editable'],
    #            )
    #        elif child.tag == 'node':
    #            sub_name_manager = self.with_context(
    #                base_model_name=name_manager.model._name,
    #            )._postprocess_view(
    #                child, child.get('object'), editable=node_info['editable'],
    #            )
    #            has_create_access = sub_name_manager.model.check_access_rights(
    #                'create', raise_exception=False)
    #            if not node.get('create') and not has_create_access:
    #                node.set('create', 'false')

    #def _validate_tag_diagram_plus(self, node, name_manager, node_info):
    #    for child in node:
    #        if child.tag not in ("arrow", "node"):
    #            msg = _(
    #                "Only 'node' and 'arrow' tags allowed in "
    #                "'diagram_plus_view', but %(tag_name)s found.",
    #            ) % {'tag_name': child.tag}
    #            self._raise_view_error(msg)

    # @api.model
    # def update_from_pdfviewer(self, id, fields, delIds, newName):
    #     pass


    # @api.model
    # def rotate_pdf(self,id):
    #     pass
        

    def pdfform_edit(self):
        self.ensure_one()
        return {
                'name': self.name +  _('edit'),
                'type': 'ir.actions.act_window',
                'view_mode': 'pdfForm',
                'view_id': self.id,
                'target': 'current',
                'res_model': self.model,
                'res_id': False,
                "breadcrumbs": True,
        }
    
    def _postprocess_access_rights(self, tree):
        for node in tree.xpath('//*[@groups_edit]'):
            if not self.user_has_groups(node.get('groups_edit')):
                node.set('readonly', 'True')
            node.attrib.pop('groups_edit')
        return super(IrUiView, self)._postprocess_access_rights(tree)
