"""Blob Storage reads and writes from Hindcast's code, signed in with Entra ID.

The account accepts no shared keys and no anonymous reads, so every call
carries a DefaultAzureCredential token and needs Storage Blob Data
Contributor. Captured sources live in the "sources" container under
<case_id>/<filename>; derived output goes to "extracted".
"""

import functools
import hashlib
from typing import Protocol

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContainerClient

from hindcast.config import StorageSettings, load_settings

SOURCES = "sources"


class Pinned(Protocol):
    """A registry entry with a pinned file: a case source or a library document."""

    # Read-only, so frozen dataclasses satisfy the protocol.
    @property
    def doc_id(self) -> str: ...
    @property
    def filename(self) -> str: ...
    @property
    def sha256(self) -> str: ...


class BlobDownload(Protocol):
    def readall(self) -> bytes: ...


class BlobContainer(Protocol):
    """The two container operations the code uses; ContainerClient satisfies it."""

    def download_blob(self, name: str) -> BlobDownload: ...
    def upload_blob(self, name: str, data: bytes, overwrite: bool = ...) -> None: ...


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


def download_source(prefix: str, source: Pinned, client: BlobContainer | None = None) -> bytes:
    """The bytes at sources/<prefix>/<filename>, refused unless they match the registry's hash.

    prefix is the case ID for a case source, "library" for a library page.
    """
    data = (client or container(SOURCES)).download_blob(f"{prefix}/{source.filename}").readall()
    # A page captured again, or a changed blob, is not the source the case was built on.
    if hashlib.sha256(data).hexdigest() != source.sha256:
        raise SourceMismatch(f"{source.doc_id}: downloaded bytes do not match the registry")
    return data


def upload_bytes(
    container_name: str,
    name: str,
    data: bytes,
    *,
    overwrite: bool = False,
    client: BlobContainer | None = None,
) -> None:
    """Upload one blob; an existing blob is kept unless overwrite is set."""
    (client or container(container_name)).upload_blob(name, data, overwrite=overwrite)


def upload_source(prefix: str, filename: str, data: bytes) -> None:
    """Upload a captured page to sources/<prefix>/<filename>, never over an existing one.

    A source that changes after its hash is pinned is a different source, so
    replacing one means deleting the blob by hand and pinning the new hash.
    """
    upload_bytes(SOURCES, f"{prefix}/{filename}", data)
