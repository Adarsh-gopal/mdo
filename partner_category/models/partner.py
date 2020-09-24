# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import itertools

class ResPartner(models.Model):
    _inherit = 'res.partner'
    _name = _inherit

    z_partner_category = fields.Many2one('partner.category',string="Partner Category",domain="[('active_id', '=', True)]")
    z_partner = fields.Boolean('Partner')
    customer = fields.Boolean('Customer')
    vendor = fields.Boolean('Vendor')
    transport_vendor= fields.Boolean('Transport Vendor')
    distributor = fields.Boolean('Distributor')
    invoice_vendor = fields.Boolean('Invoice Vendor',store=True,compute='compute_vendor')
    invoice_customer = fields.Boolean('Invoice Customer',store=True,compute='compute_customer')
    invoice_filter = fields.Char('Invoice Filter',store=True,compute='compute_filter')
    preffered_transporter = fields.Many2one('res.partner',string="Preffered Transporter",domain="[('transport_vendor', '=', 'True')]")


    @api.model
    def create(self, vals):
        if 'z_partner' in vals and vals['z_partner']:
            sequence_type =  vals.get('z_partner_category')
            sequence_type = self.env['partner.category'].browse(sequence_type)
            if sequence_type:
                vals['ref'] = sequence_type.partner_category.next_by_id()

        return super(ResPartner, self).create(vals)

    @api.onchange('z_partner_category')
    def Onchange_partner(self):
        for l in self:
            if l.z_partner_category.partner_category:
                l.z_partner = True
            else:
                l.z_partner = False

    @api.depends('customer','distributor')
    def compute_customer(self):
        for l in self:
            if l.customer == True or l.distributor == True:
                l.invoice_customer = True
            elif l.customer == True and l.distributor == True:
                l.invoice_customer = True
            elif l.customer == False and l.distributor == False:
                l.invoice_customer = False

    @api.depends('vendor','transport_vendor')
    def compute_vendor(self):
        for l in self:
            if l.vendor == True or l.transport_vendor == True:
                l.invoice_vendor = True
            elif l.vendor == True and l.transport_vendor == True:
                l.invoice_vendor = True
            elif l.vendor == False and l.transport_vendor == False:
                l.invoice_vendor = False

    @api.depends('invoice_customer','invoice_vendor')
    def compute_filter(self):
        for l in self:
            if l.invoice_customer == True:
                l.invoice_filter = 'sale'
            if l.invoice_vendor == True:
                l.invoice_filter = 'purchase'


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    _name = _inherit

    z_partner = fields.Boolean('Partner')
    default_code= fields.Char(string='Internal Reference',compute = "_trackcode",store=True)
    default_code1= fields.Char(string='Internal Reference')


    @api.onchange('categ_id')
    def Onchange_partner(self):
        for l in self:
            if l.categ_id.sequence_id:
                l.z_partner = True
            else:
                l.z_partner = False

    @api.depends('default_code1')
    def _trackcode(self):
        for l in self:
            l.default_code = l.default_code1   

    @api.model
    def create(self, vals):
        if 'z_partner' in vals and vals['z_partner']:
            sequence_type =  vals.get('categ_id')
            sequence_type = self.env['product.category'].browse(sequence_type)
            if sequence_type:
                new_code = sequence_type.sequence_id.next_by_id()
                vals.update({'default_code1': new_code,'default_code': new_code})

        return super(ProductTemplate, self).create(vals)

    def _create_variant_ids(self):
        self.flush()
        Product = self.env["product.product"]

        variants_to_create = []
        variants_to_activate = Product
        variants_to_unlink = Product

        for tmpl_id in self:
            lines_without_no_variants = tmpl_id.valid_product_template_attribute_line_ids._without_no_variant_attributes()

            all_variants = tmpl_id.with_context(active_test=False).product_variant_ids.sorted('active')

            current_variants_to_create = []
            current_variants_to_activate = Product

            # adding an attribute with only one value should not recreate product
            # write this attribute on every product to make sure we don't lose them
            single_value_lines = lines_without_no_variants.filtered(lambda ptal: len(ptal.product_template_value_ids._only_active()) == 1)
            if single_value_lines:
                for variant in all_variants:
                    combination = variant.product_template_attribute_value_ids | single_value_lines.product_template_value_ids._only_active()
                    # Do not add single value if the resulting combination would
                    # be invalid anyway.
                    if (
                        len(combination) == len(lines_without_no_variants) and
                        combination.attribute_line_id == lines_without_no_variants
                    ):
                        variant.product_template_attribute_value_ids = combination

            # Determine which product variants need to be created based on the attribute
            # configuration. If any attribute is set to generate variants dynamically, skip the
            # process.
            # Technical note: if there is no attribute, a variant is still created because
            # 'not any([])' and 'set([]) not in set([])' are True.
            if not tmpl_id.has_dynamic_attributes():
                # Iterator containing all possible `product.template.attribute.value` combination
                # The iterator is used to avoid MemoryError in case of a huge number of combination.
                all_combinations = itertools.product(*[
                    ptal.product_template_value_ids._only_active() for ptal in lines_without_no_variants
                ])
                # Set containing existing `product.template.attribute.value` combination
                existing_variants = {
                    variant.product_template_attribute_value_ids: variant for variant in all_variants
                }
                # For each possible variant, create if it doesn't exist yet.
                for combination_tuple in all_combinations:
                    combination = self.env['product.template.attribute.value'].concat(*combination_tuple)
                    if combination in existing_variants:
                        current_variants_to_activate += existing_variants[combination]
                    else:
                        current_variants_to_create.append({
                            'product_tmpl_id': tmpl_id.id,
                            'product_template_attribute_value_ids': [(6, 0, combination.ids)],
                            'active': tmpl_id.active,
                            'default_code':tmpl_id.default_code,
                        })
                        if len(current_variants_to_create) > 1000:
                            raise UserError(_(
                                'The number of variants to generate is too high. '
                                'You should either not generate variants for each combination or generate them on demand from the sales order. '
                                'To do so, open the form view of attributes and change the mode of *Create Variants*.'))
                variants_to_create += current_variants_to_create
                variants_to_activate += current_variants_to_activate

            variants_to_unlink += all_variants - current_variants_to_activate

        if variants_to_activate:
            variants_to_activate.write({'active': True})
        if variants_to_create:
            Product.create(variants_to_create)
        if variants_to_unlink:
            variants_to_unlink._unlink_or_archive()

        # prefetched o2m have to be reloaded (because of active_test)
        # (eg. product.template: product_variant_ids)
        # We can't rely on existing invalidate_cache because of the savepoint
        # in _unlink_or_archive.
        self.flush()
        self.invalidate_cache()
        return True


class ProductCategory(models.Model):
    _inherit = 'product.category'

    sequence_id = fields.Many2one('ir.sequence',string='Sequence')


class PartnerCategory(models.Model):
    _name = 'partner.category'
    _parent_name = "zparent"
    _parent_store = True
    _rec_name = 'full_name'
    _order = 'full_name'

    name = fields.Char(string='Name',index=True)
    full_name = fields.Char(string='Category Name',store=True,compute='_compute_complete_name')
    zparent = fields.Many2one('partner.category',string='Parent')
    active_id = fields.Boolean(string='Release')
    partner_category = fields.Many2one('ir.sequence',string="Sequence")
    parent_path = fields.Char(index=True)

    @api.depends('name', 'zparent.name')
    def _compute_complete_name(self):
        for location in self:
            if location.zparent:
                location.full_name = '%s / %s' % (location.zparent.full_name, location.name)
            else:
                location.full_name = location.name

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    partner_reference = fields.Char('Partner Category')
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True,
        states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
        required=True, change_default=True, index=True, tracking=1,
        domain="['|', ('customer','=',True),('distributor','=',True)]",)

    @api.onchange('partner_id')
    def Onchange_partner(self):
        for l in self:
            l.partner_reference = l.partner_id.z_partner_category.full_name

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    READONLY_STATES = {
        'purchase': [('readonly', True)],
        'done': [('readonly', True)],
        'cancel': [('readonly', True)],
    }

    partner_reference = fields.Char('Partner Category')
    partner_id = fields.Many2one('res.partner', string='Vendor', required=False, states=READONLY_STATES, change_default=True, tracking=True, domain="['|', ('vendor', '=', True),('transport_vendor', '=', True)]", help="You can find a vendor by its Name, TIN, Email or Internal Reference.")

    @api.onchange('partner_id')
    def Onchange_partnerr(self):
        for l in self:
            l.partner_reference = l.partner_id.z_partner_category.name

# class Lead(models.Model):
#     _inherit = "crm.lead"

#     partner_id = fields.Many2one('res.partner', string='Customer', tracking=10, index=True,
#         domain="['|',('customer','=',True),('distributor','=',True)]", help="Linked partner (optional). Usually created when converting the lead. You can find a partner by its Name, TIN, Email or Internal Reference.")

class AccountInvoice(models.Model):
    _inherit = "account.move"

    partner_reference = fields.Char('Partner Category',store=True,track_visibility='always',compute='change_partners')
    partner_id = fields.Many2one('res.partner', readonly=True, tracking=True,
        states={'draft': [('readonly', False)]},
        domain="[('invoice_filter', '=', invoice_filter_type_domain)]",
        string='Partner', change_default=True)


    @api.depends('partner_id')
    def change_partners(self):
        for l in self:
            l.partner_reference = l.partner_id.z_partner_category.name


# class account_payment(models.Model):
#     _inherit = "account.payment"

#     partner_id = fields.Many2one('res.partner', string='Partner', tracking=True, readonly=True, states={'draft': [('readonly', False)]}, domain="['|', ('partner_type','=', 'customer'), ('partner_type', '=','supplier')]")