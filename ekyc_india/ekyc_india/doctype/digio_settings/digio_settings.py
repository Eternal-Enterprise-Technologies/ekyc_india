# Copyright (c) 2025, hello@frappe.io and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import base64
from frappe.integrations.utils import make_request
from frappe.utils.password import get_decrypted_password


class DigioSettings(Document):
	pass

def make_esignature_request(doc):
	request = frappe._dict()
	request.update({
		"signers": get_signers(doc),
		"expire_in_days": 10,
		"notify_signers": True,
		"send_sign_link": True,
		"generate_access_token": True,
		"file_name": doc.name,
		"file_data": get_file_data_in_base64(doc.doctype, doc.name),
	})

	make_post_api_call(request)

def make_post_api_call(body):
	api_client_id, api_client_secret, url = get_api_credentials_and_url()
	headers = {
		"Content-Type": "application/json",
		"Accept": "application/json",
		"Authorization": "Basic" + base64.b64encode((api_client_id + ":" + api_client_secret).encode('utf-8')).decode()
	}

	response = make_request(
		method="POST",
		url=url,
		headers=headers,
		json=body
	)

	make_e_sign_request_log(response)

def make_e_sign_request_log(response):
	doc = frappe.new_doc("e-Signature Request Log")
	doc.digio_id = response.get("id")
	doc.is_agreement = response.get("is_agreement")
	doc.agreement_status = response.get("agreement_status")
	doc.agreement_type = response.get("agreement_type")
	doc.reponse_json = response
	doc.save(ignore_permissions=True)


def get_api_credentials_and_url():
	digio_settings = frappe.get_doc("Digio Settings", "Digio Settings")

	if digio_settings.enable_production:
		api_client_id = get_decrypted_password("Digio Settings", "Digio Settings", fieldname="api_client_id", raise_exception=False)
		api_client_secret = get_decrypted_password("Digio Settings", "Digio Settings", fieldname="api_client_secret", raise_exception=False)
		url = frappe.get_single_value("Digio Settings", "production_url")
	else:
		if not digio_settings.enable_sandbox:
			frappe.throw("Please enable Sandbox or Production mode in Digio Settings")

		api_client_id = get_decrypted_password("Digio Settings", "Digio Settings", fieldname="sandbox_api_client_id", raise_exception=False)
		api_client_secret = get_decrypted_password("Digio Settings", "Digio Settings", fieldname="sandbox_api_secret", raise_exception=False)
		url = frappe.get_single_value("Digio Settings", "sandbox_url")

	return api_client_id, api_client_secret, url

def get_file_data_in_base64(doctype, docname):
	file_data = base64.b64encode(
		frappe.get_print(doctype, docname, as_pdf=True, pdf_generator="wkhtmltopdf")
	).decode()

	return file_data


def get_signers(doc):
	signers = []
	receiver_fields = frappe.db.get_all(
		"e-Signature Document",
		filters={
			"document_type": doc.doctype
		},
		fields=["request_recipient_by_document_field"]
	)

	for receiver in receiver_fields:
		data_field, child_field = _parse_receiver_by_document_field(
			receiver.request_recipient_by_document_field
		)

		if child_field:
			for d in doc.get(child_field):
				email_id = d.get(data_field)
				signers.append(email_id)
		# field from current doc
		else:
			email_ids_value = doc.get(data_field)
			email_ids = email_ids_value.replace(",", "\n")
			signers = signers + email_ids.split("\n")
	
	return signers

def _parse_receiver_by_document_field(s):
	fragments = s.split(",")
	# fields from child table or linked doctype
	if len(fragments) > 1:
		data_field, child_field = fragments
	else:
		data_field, child_field = fragments[0], None
	return data_field, child_field
