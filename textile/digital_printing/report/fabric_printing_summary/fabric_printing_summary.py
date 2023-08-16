# Copyright (c) 2023, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate


def execute(filters=None):
	return FabricPrintingSummary(filters).run()


class FabricPrintingSummary:
	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})
		self.filters.from_date = getdate(filters.from_date)
		self.filters.to_date = getdate(filters.to_date)

		if self.filters.from_date > self.filters.to_date:
			frappe.throw(_("Date Range is incorrect"))

	def run(self):
		self.get_data()
		self.prepare_data()
		self.get_columns()

		return self.columns, self.data

	def get_data(self):
		self.order_data = frappe.db.sql("""
			SELECT item.fabric_material,
				COUNT(distinct pro.name) AS no_of_orders,
				SUM(poi.stock_print_length) AS ordered_qty
			FROM `tabPrint Order Item` poi
			INNER JOIN `tabPrint Order` pro ON pro.name = poi.parent
			INNER JOIN `tabItem` item ON item.name = pro.fabric_item
			WHERE pro.docstatus = 1
				AND pro.transaction_date BETWEEN %(from_date)s AND %(to_date)s
			GROUP BY item.fabric_material
		""", self.filters, as_dict=1)

		self.fabric_received_data = frappe.db.sql("""
			SELECT item.fabric_material, SUM(sed.transfer_qty) AS received_qty
			FROM `tabStock Entry Detail` sed
			INNER JOIN `tabStock Entry` se ON se.name = sed.parent
			LEFT JOIN `tabItem` item ON item.name = sed.item_code
			WHERE se.docstatus = 1
				AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
				AND se.customer_provided = 1
				AND item.textile_item_type IN ('Greige Fabric', 'Ready Fabric')
			GROUP BY item.fabric_material
		""", self.filters, as_dict=1)

		self.production_data = frappe.db.sql("""
			SELECT item.fabric_material, SUM(se.fg_completed_qty) AS produced_qty
			FROM `tabStock Entry` se
			INNER JOIN `tabWork Order` wo ON wo.name = se.work_order
			LEFT JOIN `tabItem` item ON item.name = wo.fabric_item
			WHERE se.docstatus = 1
				AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
				AND se.purpose = 'Manufacture'
				AND ifnull(wo.print_order, '') != ''
			GROUP BY item.fabric_material
		""", self.filters, as_dict=1)

		self.packing_data = frappe.db.sql("""
			SELECT item.fabric_material, SUM(psi.stock_qty) AS packed_qty
			FROM `tabPacking Slip Item` psi
			INNER JOIN `tabPacking Slip` ps ON ps.name = psi.parent
			INNER JOIN `tabItem` item ON item.name = psi.item_code
			WHERE ps.docstatus = 1
				AND ps.posting_date BETWEEN %(from_date)s AND %(to_date)s
				AND ifnull(psi.print_order, '') != ''
				AND ifnull(psi.source_packing_slip, '') = ''
			GROUP BY item.fabric_material
		""", self.filters, as_dict=1)

		self.delivery_data = frappe.db.sql("""
			SELECT item.fabric_material, SUM(dni.stock_qty) AS delivered_qty
			FROM `tabDelivery Note Item` dni
			INNER JOIN `tabDelivery Note` dn ON dn.name = dni.parent
			INNER JOIN `tabItem` item ON item.name = dni.item_code
			WHERE dn.docstatus = 1
				AND dn.posting_date BETWEEN %(from_date)s AND %(to_date)s
				AND dn.is_return = 0
				AND ifnull(dni.print_order, '') != ''
				AND dni.is_return_fabric = 0
			GROUP BY item.fabric_material
		""", self.filters, as_dict=1)

	def prepare_data(self):
		data_bank = [
			self.order_data,
			self.fabric_received_data,
			self.production_data,
			self.packing_data,
			self.delivery_data
		]

		result = {}
		for data_list in data_bank:
			for d in data_list:
				result.setdefault(d.fabric_material, {
					"no_of_orders": 0,
					"ordered_qty": 0,
					"received_qty": 0,
					"produced_qty": 0,
					"packed_qty": 0,
					"delivered_qty": 0
				}).update(d)

		self.data = sorted(list(result.values()), key=lambda d: d['fabric_material'])

	def get_columns(self):
		self.columns = [
			{
				"label": _("Fabric Material"),
				"fieldname": "fabric_material",
				"fieldtype": "Link",
				"options": "Fabric Material",
				"width": 120
			},
			{
				"label": _("Orders Received"),
				"fieldname": "no_of_orders",
				"fieldtype": "Int",
				"width": 110
			},
			{
				"label": _("Ordered Qty"),
				"fieldname": "ordered_qty",
				"fieldtype": "Float",
				"width": 120
			},
			{
				"label": _("Fabric Received Qty"),
				"fieldname": "received_qty",
				"fieldtype": "Float",
				"width": 125
			},
			{
				"label": _("Produced Qty"),
				"fieldname": "produced_qty",
				"fieldtype": "Float",
				"width": 120
			},
			{
				"label": _("Packed Qty"),
				"fieldname": "packed_qty",
				"fieldtype": "Float",
				"width": 120
			},
			{
				"label": _("Delivered Qty"),
				"fieldname": "delivered_qty",
				"fieldtype": "Float",
				"width": 120
			},
		]