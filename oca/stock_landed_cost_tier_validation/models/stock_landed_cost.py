# Copyright 2025 Alitec Pte. Ltd.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import ValidationError


class StockLandedCost(models.Model):
    _name = "stock.landed.cost"
    _inherit = ["stock.landed.cost", "tier.validation"]
    _state_from = ["draft"]
    _state_to = ["posted"]
    _cancel_state = "cancel"

    _tier_validation_manual_config = False

    def button_validate(self):
        """Override button_validate to include tier validation"""
        for rec in self:
            if rec.need_validation:
                # try to validate operation
                reviews = rec.request_validation()
                rec._validate_tier(reviews)
                if not self._calc_reviews_validated(reviews):
                    raise ValidationError(
                        _(
                            "This action needs to be validated for at least "
                            "one record. \nPlease request a validation."
                        )
                    )
            if rec.review_ids and not rec.validated:
                raise ValidationError(
                    _(
                        "A validation process is still open for at least "
                        "one record."
                    )
                )
        return super().button_validate()
