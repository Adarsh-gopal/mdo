# -*- coding: utf-8 -*-
{
    "name": "Automatic Customer Number And Product Number ",
    "version": "13.0.1.13",
    'license': 'LGPL-3',
    'author': 'Prixgen Tech Solutions Pvt. Ltd.',
    'company': 'Prixgen Tech Solutions Pvt. Ltd.',
    'website': 'https://www.prixgen.com',
    "summary": """
    Automatically create the customer number from a sequence when a customer is being created.
    """,
    "description": """
Automatic Customer Number
=========================
Automatically create the customer number from a sequence when a customer is being created.

The customer number can be configured in the sequence "Customer Number".
    """,
    "category": "Sales",
    "depends": [
        "base",
        "sale","contacts","product","account",
    ],
    "data": [
        "data/sequencer.xml",
        "views/partner.xml",
        "security/ir.model.access.csv"
    ],
    "installable": True,
    "auto_install": False,
}
