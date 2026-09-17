from django.core.files.storage import storages


def public_storage():
    return storages["default"]


def private_storage():
    return storages["private"]
