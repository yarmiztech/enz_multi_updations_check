# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

from datetime import date
from datetime import datetime
from datetime import datetime, timedelta
from odoo.exceptions import UserError, ValidationError
import calendar
import re
import json
from dateutil.relativedelta import relativedelta
import pgeocode
import qrcode
from PIL import Image
from random import choice
from string import digits
import json
import re
import uuid
from functools import partial



class SalesExecutiveCollections(models.Model):
    _inherit = "executive.collection"


    def action_confirm(self):
        for line in self.partner_invoices:
            stmt = self.env['account.bank.statement']
            if line.amount_total == 0.0:
                raise UserError(_("Please mention paid amount for this partner %s ") % (line.partner_id.name))
            cv = 0
            if line.check_type == 'cheque':
                journal = self.env['account.journal'].search(
                    [('name', '=', 'Bank'), ('company_id', '=', self.env.user.company_id.id)])
            else:
                journal = line.journal_id.id
            if not stmt:
                # _get_payment_info_JSON
                # bal = sum(self.env['account.move.line'].search([('journal_id', '=', line.journal_id.id)]).mapped(
                #     'debit'))

                if self.env['account.bank.statement'].search([('company_id', '=', line.journal_id.company_id.id),
                                                              ('journal_id', '=', line.journal_id.id)]):
                    bal = self.env['account.bank.statement'].search(
                        [('company_id', '=', line.journal_id.company_id.id),
                         ('journal_id', '=', line.journal_id.id)])[0].balance_end_real
                else:
                    bal = 0

                stmt = self.env['account.bank.statement'].create({'name': line.partner_id.name,
                                                                  'balance_start': bal,
                                                                  # 'journal_id': line.journal_id.id,
                                                                  'journal_id': line.journal_id.id,
                                                                  'balance_end_real': bal+line.amount_total

                                                                  })

            payment_list = []
            pay_id_list = []
            account = self.env['account.move'].search(
                [('partner_id', '=', line.partner_id.id),('amount_residual','!=',0),('company_id','=',line.journal_id.company_id.id),('move_type','=','out_invoice'),('state', '=', 'posted')])
            amount = line.amount_total
            actual = 0
            if account:
               for check_inv in reversed(account):
                 if amount:
                    # if check_inv.amount_residual:

                    # if check_inv.amount_total >= amount:
                    if check_inv.amount_residual >= amount:
                        actual = amount
                        product_line = (0, 0, {
                            'date': line.date,
                            'name': check_inv.display_name,
                            'partner_id': line.partner_id.id,
                            'payment_ref': check_inv.display_name,
                            'amount': amount
                        })
                        amount = amount - amount
                        payment_list.append(product_line)
                    else:
                        # if check_inv.amount_total != 0:
                        if check_inv.amount_residual != 0:
                            amount = amount - check_inv.amount_residual
                            actual = check_inv.amount_residual
                            product_line = (0, 0, {
                                'date': line.date,
                                'name': check_inv.display_name,
                                'partner_id': line.partner_id.id,
                                'payment_ref': check_inv.display_name,
                                'amount': check_inv.amount_residual
                            })
                            payment_list.append(product_line)

                    j = self.env['account.payment.method'].search([('name', '=', 'Manual')])[0]
                    # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

                    # pay_id = self.env['account.payment'].create({'partner_id': line.partner_id.id,
                    #                                              # 'amount': check_inv.amount_total,
                    #                                              'amount': actual,
                    #                                              'partner_type': self.partner_type,
                    #                                              'company_id': self.env.user.company_id.id,
                    #                                              'payment_type': self.payment_type,
                    #                                              'payment_method_id': self.payment_method_id.id,
                    #                                              # 'journal_id': line.journal_id.id,
                    #                                              'journal_id': line.journal_id.id,
                    #                                              'ref': 'Cash Collection',
                    #                                              # 'invoice_ids': [(6, 0, check_inv.ids)]
                    #                                              })
                    # pay_id.action_validate_invoice_payment()
                    # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%5
                    pmt_wizard = self.env['account.payment.register'].with_context(active_model='account.move',
                                                                                   active_ids=check_inv.ids).create({
                        'payment_date': check_inv.date,
                        'journal_id': self.env['account.journal'].search(
                            [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id,
                        'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                        'amount': actual,

                    })
                    pmt_wizard._create_payments()
                    # pay_id.action_post()
                    # pay_id.action_cash_book()
                    self.action_cash_book(line)
                    # # for k in pay_id.move_line_ids:
                    # for k in pay_id.line_ids:
                    #     pay_id_list.append(k.id)
                    # line.payments += pay_id
                    invoices = self.env['account.move'].search(
                        [('partner_id', '=', line.partner_id.id),
                         ('company_id', '=', self.env.user.company_id.id), ('state', '!=', 'paid')])
                    if invoices.mapped('amount_residual'):
                        bal = sum(invoices.mapped('amount_residual'))
                    else:
                        bal = sum(invoices.mapped('amount_total'))
                    bal += self.env['partner.ledger.customer'].search(
                        [('partner_id', '=', line.partner_id.id), ('description', '=', 'Opening Balance')]).balance
                    bal_ref = self.env['partner.ledger.customer'].search(
                        [('company_id', '=', self.env.user.company_id.id), ('partner_id', '=', line.partner_id.id)])

                    if bal_ref:
                        bal = self.env['partner.ledger.customer'].search(
                        [('company_id', '=', self.env.user.company_id.id), ('partner_id', '=', line.partner_id.id)])[
                        -1].balance

               self.env['partner.ledger.customer'].sudo().create({
                        'date': datetime.today().date(),
                        # 'invoice_id': inv.id,
                        'description': 'Cash',
                        'partner_id': line.partner_id.id,
                        'company_id': 1,
                        'account_journal': line.journal_id.id,
                        'account_move': line.payments.move_id.id,
                        'credit': line.amount_total,
                        'balance': bal - line.amount_total,
                    })
            else:
                if not account:
                    actual = amount

                j = self.env['account.payment.method'].search([('name', '=', 'Manual')])[0]

                # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
                pay_id = self.env['account.payment'].create({'partner_id': line.partner_id.id,
                                                             'amount': actual,
                                                             'partner_type': self.partner_type,
                                                             'company_id': self.env.user.company_id.id,
                                                             'payment_type': self.payment_type,
                                                             'payment_method_id': self.payment_method_id.id,
                                                             'journal_id': line.journal_id.id,
                                                             'ref': 'Cash Collection',
                                                             })
                # pay_id.post()
                # pay_id.action_post()
                pay_id.action_post()
                # pay_id.action_cash_book()
                # %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
                # pmt_wizard = self.env['account.payment.register'].with_context(active_model='account.move',
                #                                                                active_ids=check_inv.ids).create({
                #     'payment_date': check_inv.date,
                #     'journal_id': self.env['account.journal'].search(
                #         [('name', '=', 'Cash'), ('company_id', '=', self.env.user.company_id.id)]).id,
                #     'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                #     'amount': actual,
                #
                # })
                # pmt_wizard._create_payments()

                # pay_id.action_cash_book()
                self.action_cash_book(line)
                product_line = (0, 0, {
                    'date': self.payment_date,
                    'name': self.display_name,
                    'partner_id': line.partner_id.id,
                    'payment_ref': self.name,
                    'amount': actual
                })
                payment_list.append(product_line)

                # for k in pay_id.move_line_ids:
                # for k in pay_id.line_ids:
                #     pay_id_list.append(k.id)
                # line.payments += pay_id
                invoices = self.env['account.move'].search(
                    [('partner_id', '=', line.partner_id.id),
                     ('company_id', '=', self.env.user.company_id.id), ('state', '!=', 'paid')])
                if invoices:
                    if invoices.mapped('amount_residual'):
                        bal = sum(invoices.mapped('amount_residual'))
                    else:
                        bal = sum(invoices.mapped('amount_total'))
                bal += self.env['partner.ledger.customer'].search(
                    [('partner_id', '=', line.partner_id.id), ('description', '=', 'Opening Balance')]).balance
                bal_ref = self.env['partner.ledger.customer'].search(
                    [('company_id', '=', self.env.user.company_id.id), ('partner_id', '=', line.partner_id.id)])

                if bal_ref:
                    bal = self.env['partner.ledger.customer'].search(
                        [('company_id', '=', self.env.user.company_id.id), ('partner_id', '=', line.partner_id.id)])[
                        -1].balance

                self.env['partner.ledger.customer'].sudo().create({
                    'date': datetime.today().date(),
                    # 'invoice_id': inv.id,
                    'description': 'Cash',
                    'partner_id': line.partner_id.id,
                    'company_id': 1,
                    'account_journal': line.journal_id.id,
                    'account_move': line.payments.move_id.id,
                    'credit': line.amount_total,
                    'balance': bal - line.amount_total,
                })

        if stmt:
            stmt.line_ids = payment_list
            # receivable_line = check_inv.line_ids.filtered(
            #             lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
            # stmt.button_post()
            # stmt.button_validate_or_action()
            line_id = None
            # for l in stmt.line_id:
            #     if l.account_id.id == stmt.account_rcv_id:
            #         line_id = l
            #         break
            # for statement_line in stmt.line_ids:
            #     statement_line.reconcile([{'id': receivable_line.id}])


            # stmt.line_ids.move_id.sudo().action_post()
            # stmt.move_line_ids = pay_id_list
            # if pay_id_list:
            #     self.env['account.move.line'].browse(pay_id_list[0])
            # invoice = self.env['account.move.line'].browse(pay_id_list[0]).mapped('move_id')
            # # for l in invoice.line_ids:
            # for l in pay_id_list:
            #     if l.account_id.account_internal_type == 'receivable':
            #         line_id = l
            #         break
            # for statement_line in stmt.line_ids:
            #     statement_line.reconcile([{'id': line_id.id}])

            # stmt.button_post()
            #     # counterpart_lines = move.mapped('line_ids').filtered(lambda line: line.account_internal_type in ('receivable', 'payable'))
            #
            # stmt.action_bank_reconcile_bank_statements()
            # stmt.write({'state': 'confirm'})
            self.write({'state': 'validate'})

        self.action_accountant_record()



class SaleEstimateLines(models.Model):
    _inherit = "sale.estimate.lines"


    def _compute_done_qty(self):
        for each in self:
            each.done_qty = sum(each.sub_customers.mapped('quantity'))
            each.bal_qty = each.product_uom_qty - each.done_qty



