from django.urls import path

from apps.crm import views

app_name = "crm"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("contacts/", views.contact_list, name="contacts"),
    path("contacts/new/", views.contact_edit, name="contact_new"),
    path("contacts/<int:pk>/", views.contact_detail, name="contact_detail"),
    path("contacts/<int:pk>/edit/", views.contact_edit, name="contact_edit"),
    path("contacts/<int:contact_pk>/enquiry/", views.enquiry_save, name="enquiry_save"),
    path("contacts/<int:contact_pk>/followup/", views.followup_save, name="followup_save"),
    path("contacts/<int:contact_pk>/payment/", views.payment_save, name="payment_save"),
    path("contacts/<int:contact_pk>/document/", views.document_save, name="document_save"),
    path("contacts/export/", views.export_contacts, name="export"),
    path("import/", views.import_contacts, name="import"),
    path("import/count/", views.import_count, name="import_count"),
    path("import/<int:pk>/map/", views.import_map, name="import_map"),
    path("import/<int:pk>/preview/", views.import_preview, name="import_preview"),
    path("import/<int:pk>/result/", views.import_result, name="import_result"),
    path("import/<int:pk>/errors.csv", views.import_errors, name="import_errors"),
    path("enquiries/", views.enquiry_list, name="enquiries"),
    path("enquiries/<int:pk>/status/", views.enquiry_status, name="enquiry_status"),
    path("follow-ups/", views.followup_list, name="followups"),
    path("whatsapp/", views.whatsapp_templates, name="whatsapp"),
    path("payments/", views.payments, name="payments"),
    path("reports/", views.reports, name="reports"),
]
