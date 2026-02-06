from contextlib import contextmanager
from odoo.fields import Command
from odoo.models import BaseModel
from odoo.addons.account.models.account_move import AccountMove


@contextmanager
def _sync_unbalanced_lines(self, container):
    def has_tax(move):
        return bool(move.line_ids.tax_ids)

    move_had_tax = {move: has_tax(move) for move in container['records']}
    yield

    for move in (x for x in container['records'] if x.state != 'posted'):
        if not has_tax(move) and not move_had_tax.get(move):
            continue

        if move_had_tax.get(move) and not has_tax(move):
            move.line_ids.filtered('tax_line_id').unlink()
            move.line_ids.tax_tag_ids = [Command.set([])]

        balance_name = move.journal_id.name

        existing_balancing_line = move.line_ids.filtered(
            lambda line: line.name == balance_name
        )

        if existing_balancing_line:
            existing_balancing_line.balance = 0.0
            existing_balancing_line.amount_currency = 0.0

        unbalanced_moves = self._get_unbalanced_moves({'records': move})

        if isinstance(unbalanced_moves, list) and len(unbalanced_moves) == 1:
            _, debit, credit = unbalanced_moves[0]

            vals = {'balance': credit - debit}

            if existing_balancing_line:
                existing_balancing_line.write(vals)
            else:
                vals.update({
                    'name': balance_name,
                    'move_id': move.id,
                    'account_id': move._get_automatic_balancing_account(),
                    'currency_id': move.currency_id.id,
                    'tax_ids': False,
                })
                self.env['account.move.line'].create(vals)

AccountMove._sync_unbalanced_lines = _sync_unbalanced_lines