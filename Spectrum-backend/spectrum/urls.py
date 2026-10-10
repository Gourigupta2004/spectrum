from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from apps.catalog import views as catalog
from apps.content import views as content
from apps.orders import views as orders
from apps.portal import views as portal

api = [
    path("site/", content.site),
    path("pages/home/", content.home),
    path("pages/about/", content.about),
    path("pages/contact/", content.contact_page),
    path("pages/portal/", content.portal_page),
    path("contact/", content.contact_submit),
    path("events/", catalog.events),
    path("events/<slug:slug>/", catalog.event_detail),
    path("portal/access/", portal.access),
    path("portal/login/", portal.login),
    path("portal/refresh/", portal.refresh),
    path("portal/me/", portal.me),
    path("portal/summary/", portal.summary),
    path("portal/captions/", portal.captions),
    path("portal/captions/<int:item_id>/resolve/", portal.caption_resolve),
    path("portal/captions/<int:item_id>/image/", portal.caption_image),
    path("portal/classes/", portal.classes),
    path("portal/classes/<slug:slug>/", portal.class_detail),
    path("portal/classes/<slug:slug>/names/", portal.class_names),
    path("portal/classes/<slug:slug>/absentees/", portal.class_absentees),
    path("portal/classes/<slug:slug>/comment/", portal.class_comment),
    path("orders/", orders.create_order),
    path("orders/<uuid:order_id>/", orders.order_status),
    path("orders/<uuid:order_id>/verify/", orders.verify_order),
    path("webhooks/razorpay/", orders.razorpay_webhook),
    path("webhooks/twilio/", orders.twilio_webhook),
    path("downloads/<str:token>/photos/<int:item_id>/", orders.download_photo),
    path("downloads/<str:token>/zip/", orders.download_zip),
]

urlpatterns = [
    path("api/", include(api)),
    path("admin/uploads/", include("apps.core.uploads")),
    path("admin/", admin.site.urls),
]

if settings.SERVE_LOCAL_MEDIA:
    # Public variants only. Originals live in media/private and are never routed.
    urlpatterns.append(
        re_path(r"^media/public/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT / "public"})
    )
