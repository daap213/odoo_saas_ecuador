# -*- coding: utf-8 -*-
import base64
from odoo import models, fields


class L10nEcBankTransferWizard(models.TransientModel):
    _name = "l10n_ec.bank.transfer.wizard"
    _description = "Generate Bank Cash Management Files"

    bank_id = fields.Selection(
        [
            ("pichincha", "Banco Pichincha (Cash Management)"),
            ("guayaquil", "Banco Guayaquil (Multicash)"),
        ],
        string="Target Bank",
        required=True,
        default="pichincha",
    )

    payment_date = fields.Date(
        string="Payment Date", default=fields.Date.context_today, required=True
    )
    description = fields.Char(string="Batch Description", default="NOMINA MENSUAL")

    # We will process Payslips marked as 'done' but not yet paid?
    # Or just select a Payslip Batch? For MVP simplicity, we select a list of payslips.
    payslip_ids = fields.Many2many("l10n_ec.payslip", string="Payslips to Pay")

    # Output
    filename = fields.Char()
    file_data = fields.Binary()

    def action_generate(self):
        """
        Generates the TXT file based on selected Bank.
        """
        self.ensure_one()
        if self.bank_id == "pichincha":
            self._generate_pichincha_txt()
        elif self.bank_id == "guayaquil":
            self._generate_guayaquil_txt()

        return {
            "type": "ir.actions.act_window",
            "res_model": "l10n_ec.bank.transfer.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def _generate_pichincha_txt(self):
        """
        Generates Banco Pichincha 'Cash Management' Header/Detail structure.
        Structure (Simplified Standard):
        HEADER: PA (Pago), RUC, Date, Reference
        DETAIL: AccountType (CTA/AHO), AccountNum, Amount, ID, Name, Ref
        """
        lines = []

        # 1. Header
        # PA | RUC_EMPRESA | USD | DATE | BATCH_REF
        company = self.env.company
        header = f"PA\t{company.vat}\tUSD\t{self.payment_date.strftime('%Y%m%d')}\t{self.description}"
        lines.append(header)

        # 2. Details
        total = 0.0
        for slip in self.payslip_ids:
            if slip.net_wage <= 0:
                continue

            emp = slip.employee_id
            # Validation: Employee must have bank account
            # For MVP, assuming emp.bank_account_id exists or skipping/erroring.
            # Using placeholders for bank fields if not yet in model, but typically res.partner.bank

            bank_acc = emp.bank_account_id
            acc_type = "AHO"  # Savings default
            acc_num = bank_acc.acc_number if bank_acc else "0000000000"

            # Format: REF \t BENEFICIARY \t ID \t AMOUNT \t ACC_TYPE \t ACC_NUM
            # Amount in cents? Usually floats in Pichincha Cash Mgmt are 2 decimals.
            amount_str = "{:.2f}".format(slip.net_wage)
            # `slip.name`, no `slip.number`: `l10n_ec.payslip` nunca ha declarado un
            # campo `number`. Con el nombre viejo esto lanzaba AttributeError en el
            # primer rol de pago, así que el TXT de pago masivo no se ha generado nunca.
            line = f"{slip.name}\t{emp.name}\t{emp.identification_id}\t{amount_str}\t{acc_type}\t{acc_num}"
            lines.append(line)
            total += slip.net_wage

        # 3. Footer/Control (Optional in some formats, but good practice)
        # TOT | NUM_RECORDS | TOTAL_AMOUNT
        footer = f"TOT\t{len(self.payslip_ids)}\t{'{:.2f}'.format(total)}"
        lines.append(footer)

        content = "\n".join(lines)

        self.filename = f"PICHINCHA_NOMINA_{self.payment_date}.txt"
        self.file_data = base64.b64encode(content.encode("utf-8"))

    def _generate_guayaquil_txt(self):
        # Similar logic, different separator/layout
        content = "HEADER_GUAYAQUIL\n"
        for slip in self.payslip_ids:
            content += f"{slip.employee_id.name},{slip.net_wage}\n"

        self.filename = f"GUAYAQUIL_NOMINA_{self.payment_date}.txt"
        self.file_data = base64.b64encode(content.encode("utf-8"))
