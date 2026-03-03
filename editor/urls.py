from django.urls import path

from . import views

urlpatterns = [
    # Pantalla principal
    path("", views.index, name="index"),
    # Sube y analiza un archivo
    path("upload/", views.text_upload, name="text_upload"),
    # Exportaciones
    path("text/export/docx/", views.export_docx, name="export_docx"),
    path("text/export/pdf/", views.export_pdf, name="export_pdf"),
]
