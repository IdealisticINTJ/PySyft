import base64
from pathlib import Path

import httpx
from typing_extensions import Self, Type

from syftbox.client.base import SyftClientInterface
from syftbox.client.exceptions import SyftServerError
from syftbox.lib.workspace import SyftWorkspace
from syftbox.server.sync.models import ApplyDiffResponse, DiffResponse, FileMetadata


class SyncClient:
    """
    Client for handling file sync operations with the server.
    """

    def __init__(
        self,
        email: str,
        client: httpx.Client,
        workspace: SyftWorkspace,
    ) -> None:
        self.email = email
        self.workspace = workspace
        self.client = client

    @classmethod
    def for_client(cls: Type[Self], client: SyftClientInterface) -> Self:
        """Create a SyncClient from a SyftClientInterface instance"""
        return cls(
            email=client.email,
            client=client.server_client,
            workspace=client.workspace,
        )

    def raise_for_sync_error(self, response: httpx.Response) -> None:
        """Implements response error handling for all sync operations."""
        # TODO handle different status codes
        endpoint_path = response.url.path
        if response.status_code != 200:
            raise SyftServerError(f"[{endpoint_path}] call failed: {response.text}")

    def get_datasite_states(self) -> dict[str, list[FileMetadata]]:
        response = self.client.post("/sync/datasite_states")
        self.raise_for_sync_error(response)
        data = response.json()

        result = {}
        for email, metadata_list in data.items():
            result[email] = [FileMetadata(**item) for item in metadata_list]

        return result

    def get_remote_state(self, relative_path: Path) -> list[FileMetadata]:
        response = self.client.post(
            "/sync/dir_state",
            params={"dir": relative_path.as_posix()},
        )
        self.raise_for_sync_error(response)
        data = response.json()
        return [FileMetadata(**item) for item in data]

    def get_metadata(self, path: Path) -> FileMetadata:
        response = self.client.post(
            "/sync/get_metadata",
            json={"path_like": path.as_posix()},
        )
        self.raise_for_sync_error(response)
        return FileMetadata(**response.json())

    def get_diff(self, relative_path: Path, signature: str) -> DiffResponse:
        """Get rsync-style diff between local and remote file.

        Args:
            relative_path: Path to file relative to workspace root
            signature: b85 encoded signature of the local file

        Returns:
            DiffResponse containing the diff and expected hash
        """
        response = self.client.post(
            "/sync/get_diff",
            json={
                "path": relative_path.as_posix(),
                "signature": signature,
            },
        )

        self.raise_for_sync_error(response)
        return DiffResponse(**response.json())

    def apply_diff(self, relative_path: Path, diff: bytes, expected_hash: str) -> ApplyDiffResponse:
        """Apply an rsync-style diff to update a remote file.

        Args:
            relative_path: Path to file relative to workspace root
            diff: py_fast_rsync binary diff to apply
            expected_hash: Expected hash of the file after applying diff, used for verification.

        Returns:
            ApplyDiffResponse containing the result of applying the diff
        """
        response = self.client.post(
            "/sync/apply_diff",
            json={
                "path": relative_path.as_posix(),
                "diff": base64.b85encode(diff).decode("utf-8"),
                "expected_hash": expected_hash,
            },
        )

        self.raise_for_sync_error(response)
        return ApplyDiffResponse(**response.json())

    def delete(self, relative_path: Path) -> None:
        response = self.client.post(
            "/sync/delete",
            json={"path": relative_path.as_posix()},
        )
        self.raise_for_sync_error(response)

    def create(self, relative_path: Path, data: bytes) -> None:
        response = self.client.post(
            "/sync/create",
            files={"file": (relative_path.as_posix(), data, "text/plain")},
        )
        self.raise_for_sync_error(response)

    def download(self, relative_path: Path) -> bytes:
        response = self.client.post(
            "/sync/download",
            json={"path": relative_path.as_posix()},
        )
        self.raise_for_sync_error(response)
        return response.content

    def download_bulk(self, relative_paths: list[Path]) -> bytes:
        relative_paths = [path.as_posix() for path in relative_paths]
        response = self.client.post(
            "/sync/download_bulk",
            json={"paths": relative_paths},
        )
        self.raise_for_sync_error(response)
        return response.content
