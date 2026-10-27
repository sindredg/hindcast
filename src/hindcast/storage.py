"""Blob Storage reads and writes from Hindcast's code, signed in with Entra ID.

The account accepts no shared keys and no anonymous reads, so every call
carries a DefaultAzureCredential token and needs Storage Blob Data
Contributor. Captured sources live in the "sources" container under
<case_id>/<filename>; derived output goes to "extracted".
"""

import functools
import hashlib

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContainerClient

from hindcast.cases import SourceFile
from hindcast.config import StorageSettings, load_settings

SOURCES = "sources"


class SourceMismatch(ValueError):
    """A downloaded source does not match the SHA-256 pinned in the registry."""


@functools.cache
def _service() -> BlobServiceClient:
    return BlobServiceClient(
        account_url=load_settings(StorageSettings).storage_url,
        credential=DefaultAzureCredential(),
    )


@functools.cache
def container(name: str) -> ContainerClient:
    return _service().get_container_client(name)


def download_source(case_id: str, source: SourceFile, client=None) -> bytes:
    """The source's bytes from Blob Storage, refused unless they match the registry's hash."""
    data = (client or container(SOURCES)).download_blob(f"{case_id}/{source.filename}").readall()
    # A page captured again, or a changed blob, is not the source the case was built on.
    if hashlib.sha256(data).hexdigest() != source.sha256:
        raise SourceMismatch(f"{source.doc_id}: downloaded bytes do not match the registry")
    return data


def upload_bytes(
    container_name: str, name: str, data: bytes, *, overwrite: bool = False, client=None
) -> None:
    """Upload one blob; an existing blob is kept unless overwrite is set."""
    (client or container(container_name)).upload_blob(name, data, overwrite=overwrite)
