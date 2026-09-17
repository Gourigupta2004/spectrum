from datetime import timedelta

from django.contrib import admin as django_admin
from django.core.cache import cache
from django.core.files.storage import storages
from django.test import RequestFactory
from django.utils import timezone

from apps.catalog.models import EventPhoto
from apps.core import cache as public_cache
from apps.core.http import client_ip
from apps.core.models import Task
from apps.core.tasks import claim

from .base import SpectrumTestCase


class HardeningTests(SpectrumTestCase):
    def test_forged_forwarded_for_is_ignored(self):
        request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="10.9.9.9", REMOTE_ADDR="203.0.113.5")
        self.assertEqual(client_ip(request), "203.0.113.5")
        request = RequestFactory().get("/", HTTP_X_REAL_IP="198.51.100.7", REMOTE_ADDR="127.0.0.1")
        self.assertEqual(client_ip(request), "198.51.100.7")
        request = RequestFactory().get("/", HTTP_X_REAL_IP="abc", REMOTE_ADDR="bad")
        self.assertEqual(client_ip(request), "")

    def test_exhausted_task_is_never_claimed_again(self):
        Task.objects.create(name="core.housekeeping", attempts=3, max_attempts=3, status=Task.QUEUED,
                            run_after=timezone.now() - timedelta(seconds=1))
        self.assertIsNone(claim())

    def test_cache_version_never_repeats_after_eviction(self):
        before = public_cache.cached_bytes("probe", lambda: {"v": 1})
        public_cache.bump()
        cache.delete("v:public")  # simulate the cache culling the version key
        after = public_cache.cached_bytes("probe", lambda: {"v": 2})
        self.assertNotEqual(before, after)

    def test_admin_delete_removes_every_variant(self):
        self.make_catalog()
        photo = self.photo(self.event)
        names = [photo.original.name, photo.preview.name, photo.thumb.name]
        model_admin = django_admin.site._registry[EventPhoto]
        request = RequestFactory().get("/")
        request.user = self.make_staff()
        deferred = model_admin.get_queryset(request).get(pk=photo.pk)  # loaded with only()
        with self.captureOnCommitCallbacks(execute=True):
            deferred.delete()
        self.assertFalse(storages["private"].exists(names[0]))
        self.assertFalse(storages["default"].exists(names[1]))
        self.assertFalse(storages["default"].exists(names[2]))
