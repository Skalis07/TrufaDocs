from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    # Todo el sitio vive en la app "editor"
    path("", include("editor.urls")),
]

if settings.DEBUG:
    # Solo en local: servir archivos subidos desde MEDIA_ROOT
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
