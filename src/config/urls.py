from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .views import home


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home, name="home"),
    path("", include("landing.urls", namespace="landing")),
    path("", include("subscriptions.urls", namespace="subscriptions")),
    path("", include("checkouts.urls", namespace="checkouts")),
    path("accounts/", include("accounts.urls", namespace="accounts")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
