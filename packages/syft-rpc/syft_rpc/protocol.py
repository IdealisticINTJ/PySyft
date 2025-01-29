import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import ClassVar, Optional, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic import ValidationError as PydanticValidationError
from syft_core.types import PathLike, to_path
from syft_core.url import SyftBoxURL
from typing_extensions import Self
from ulid import ULID

logger = logging.getLogger(__name__)

# Type aliases for better readability
JSON: TypeAlias = str | bytes | bytearray
Headers: TypeAlias = dict[str, str]


# Constants
DEFAULT_MESSAGE_EXPIRY: int = 60 * 60 * 24  # 1 days in seconds


def validate_syftbox_url(url: SyftBoxURL | str) -> SyftBoxURL:
    if isinstance(url, str):
        return SyftBoxURL(url)
    if isinstance(url, SyftBoxURL):
        return url
    raise ValueError(f"Invalid type for url: {type(url)}. Expected str or SyftBoxURL.")


class SyftMethod(StrEnum):
    """HTTP methods supported by the Syft protocol."""

    GET = "GET"
    HEAD = "HEAD"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class SyftStatus(IntEnum):
    """Standard HTTP-like status codes for Syft responses."""

    SYFT_200_OK = 200
    SYFT_400_BAD_REQUEST = 400
    SYFT_403_FORBIDDEN = 403
    SYFT_404_NOT_FOUND = 404
    SYFT_419_EXPIRED = 419
    SYFT_500_SERVER_ERROR = 500

    @property
    def is_success(self) -> bool:
        """Check if the status code indicates success."""
        return 200 <= self.value < 300

    @property
    def is_error(self) -> bool:
        """Check if the status code indicates an error."""
        return self.value >= 400


class Base(BaseModel):
    """Base model with enhanced serialization capabilities."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={
            ULID: str,
            datetime: lambda dt: dt.isoformat(),
        },
        ser_json_bytes="base64",
        val_json_bytes="base64",
    )

    def dumps(self) -> str:
        """Serialize the model instance to JSON formatted str.

        Returns:
            JSON string representation of the model instance.

        Raises:
            pydantic.ValidationError: If the model contains invalid data.
            TypeError: If the model contains types that cannot be JSON serialized.
        """
        return self.model_dump_json()

    def dump(self, path: PathLike) -> None:
        """Serialize the model instance as JSON to a file.

        Args:
            path: The file path where the JSON data will be written.

        Raises:
            pydantic.ValidationError: If the model contains invalid data.
            TypeError: If the model contains types that cannot be JSON serialized.
            PermissionError: If lacking permission to write to the path.
            OSError: If there are I/O related errors.
            FileNotFoundError: If the parent directory doesn't exist.
        """
        to_path(path).write_text(self.dumps())

    @classmethod
    def loads(cls, data: JSON) -> Self:
        """Load a model instance from a JSON string or bytes.

        Args:
            data: JSON data to parse. Can be string or binary data.

        Returns:
            A new instance of the model class.

        Raises:
            pydantic.ValidationError: If JSON doesn't match the model's schema.
            ValueError: If the input is not valid JSON.
            TypeError: If input type is not str, bytes, or bytearray.
            UnicodeDecodeError: If binary input cannot be decoded as UTF-8.
        """
        return cls.model_validate_json(data)

    @classmethod
    def load(cls, path: PathLike) -> Self:
        """Load a model instance from a JSON file.

        Args:
            path: Path to the JSON file to read.

        Returns:
            A new instance of the model class.

        Raises:
            pydantic.ValidationError: If JSON doesn't match the model's schema.
            ValueError: If file content is not valid JSON.
            FileNotFoundError: If the file doesn't exist.
            PermissionError: If lacking permission to read the file.
            OSError: If there are I/O related errors.
            UnicodeDecodeError: If content cannot be decoded as UTF-8.
        """
        return cls.loads(to_path(path).read_text())


class SyftMessage(Base):
    """Base message class for Syft protocol communication."""

    VERSION: ClassVar[int] = 1

    sender: str
    url: SyftBoxURL

    id: ULID = Field(default_factory=ULID)
    body: Optional[bytes] = None
    headers: Headers = Field(default_factory=dict)
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
        + timedelta(seconds=DEFAULT_MESSAGE_EXPIRY)
    )

    @property
    def age(self) -> float:
        """Return the age of the message in seconds."""
        return (datetime.now(timezone.utc) - self.created).total_seconds()

    @property
    def is_expired(self) -> bool:
        """Check if the message has expired."""
        return datetime.now(timezone.utc) > self.expires

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, value) -> SyftBoxURL:
        return validate_syftbox_url(value)

    def get_message_id(self) -> ULID:
        """Generate a deterministic ULID from the message contents."""
        return ULID.from_bytes(self.__msg_hash().digest()[:16])

    def get_message_hash(self) -> str:
        """Generate a hash of the message contents."""
        return self.__msg_hash().hexdigest()

    def __msg_hash(self):
        m = self.model_dump_json(include=["url", "method", "sender", "headers", "body"])
        return hashlib.sha256(m.encode())


class SyftError(Exception):
    """Base exception for Syft-related errors."""

    pass


class SyftTimeoutError(SyftError):
    """Raised when a request times out."""

    pass


class SyftRequest(SyftMessage):
    """Request message in the Syft protocol."""

    method: SyftMethod = SyftMethod.GET


class SyftResponse(SyftMessage):
    """Response message in the Syft protocol."""

    status_code: SyftStatus = SyftStatus.SYFT_200_OK

    @property
    def is_success(self) -> bool:
        """Check if the response indicates success."""
        return self.status_code.is_success

    def raise_for_status(self) -> SyftError:
        if self.status_code.is_error:
            raise SyftError(f"Request failed with status code {self.status_code}")


class SyftFuture(Base):
    """Represents an asynchronous Syft RPC operation.

    Attributes:
        id: Identifier of the corresponding request and response.
        local_path: Path where request and response files are stored.
        DEFAULT_POLL_INTERVAL: Default time between polling attempts in seconds.
    """

    DEFAULT_POLL_INTERVAL: ClassVar[float] = 0.5

    id: ULID
    url: SyftBoxURL
    local_path: PathLike
    expires: datetime

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, value) -> SyftBoxURL:
        return validate_syftbox_url(value)

    @property
    def request_path(self) -> Path:
        """Path to the request file."""
        return to_path(self.local_path) / f"{self.id}.request"

    @property
    def response_path(self) -> Path:
        """Path to the response file."""
        return to_path(self.local_path) / f"{self.id}.response"

    @property
    def rejected_path(self) -> Path:
        """Path to the rejected request marker file."""
        return self.request_path.with_suffix(f".syftrejected{self.request_path.suffix}")

    @property
    def is_rejected(self) -> bool:
        """Check if the request has been rejected."""
        return self.rejected_path.exists()

    @property
    def is_expired(self) -> bool:
        """Check if the future has expired."""
        return datetime.now(timezone.utc) > self.expires

    @staticmethod
    def load_state(request_path: PathLike) -> Self:
        try:
            request = SyftRequest.load(request_path)
        except FileNotFoundError:
            raise SyftError("Request file not found")

        message_hash = request.get_message_hash()
        state_path = request_path.parent / f".{message_hash}.state"

        try:
            return SyftFuture.load(state_path)
        except FileNotFoundError:
            raise SyftError(
                "Future object not found for the given request. Ensure the request has been sent."
            )

    def wait(
        self,
        timeout: Optional[float] = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> SyftResponse:
        """Wait for the future to complete and return the Response.

        Args:
            timeout: Maximum time to wait in seconds. None means wait until the request expires.
            poll_interval: Time in seconds between polling attempts.

        Returns:
            The response object.

        Raises:
            SyftTimeoutError: If timeout is reached before receiving a response.
            ValueError: If timeout or poll_interval is negative.
        """
        if timeout is not None and timeout <= 0:
            raise ValueError("Timeout must be greater than 0")
        if poll_interval <= 0:
            raise ValueError("Poll interval must be greater than 0")

        deadline = time.monotonic() + (timeout or float("inf"))

        while time.monotonic() < deadline:
            try:
                response = self.resolve()
                if response is not None:
                    return response
                time.sleep(poll_interval)
            except Exception as e:
                logger.error(f"Error while resolving future: {str(e)}")
                raise

        raise SyftTimeoutError(
            f"Timeout reached after waiting {timeout} seconds for response"
        )

    def resolve(self) -> Optional[SyftResponse]:
        """Attempt to resolve the future to a response.

        Args:
            silent: If True, suppress waiting messages.

        Returns:
            The response if available, None if still pending.
        """
        # Check for rejection first
        if self.is_rejected:
            self.request_path.unlink(missing_ok=True)
            self.rejected_path.unlink(missing_ok=True)
            return SyftResponse(
                status_code=SyftStatus.SYFT_403_FORBIDDEN,
                body=b"Request was rejected by the SyftBox cache server due to permissions issue",
                url=self.url,
                sender="SYSTEM",
            )

        # Check for existing response
        if self.response_path.exists():
            return self._handle_existing_response()

        # If both request and response are missing, the request has expired
        # and they got cleaned up by the server.
        if not self.request_path.exists():
            #! todo what's the possibility that a .req doesn't exist but a .resp does?
            return SyftResponse(
                status_code=SyftStatus.SYFT_404_NOT_FOUND,
                url=self.url,
                body=f"Request with {self.id} not found",
                sender="SYSTEM",
            )

        # Check for expired request
        request = SyftRequest.load(self.request_path)
        if request.is_expired:
            self.request_path.unlink(missing_ok=True)
            self.response_path.unlink(missing_ok=True)
            return SyftResponse(
                status_code=SyftStatus.SYFT_419_EXPIRED,
                body=f"Request with {self.id} expired on {self.expires}",
                url=self.url,
                sender="SYSTEM",
            )

        # No response yet
        return None

    def _handle_existing_response(self) -> SyftResponse:
        """Process an existing response file.

        Returns:
            The loaded response object.

        Note:
            If the response file exists but is invalid or expired,
            returns an appropriate error response instead of raising an exception.
        """
        try:
            response = SyftResponse.load(self.response_path)
            # preserve results, but change status code to 419
            if response.is_expired:
                response.status_code = SyftStatus.SYFT_419_EXPIRED
            return response
        except (PydanticValidationError, ValueError, UnicodeDecodeError) as e:
            logger.error(f"Error loading response: {str(e)}")
            return SyftResponse(
                status_code=SyftStatus.SYFT_500_SERVER_ERROR,
                body=str(e).encode(),
                url=self.url,
                sender="SYSTEM",
            )
        finally:
            self.request_path.unlink(missing_ok=True)
            self.response_path.unlink(missing_ok=True)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, SyftFuture):
            return False
        return self.id == other.id


class SyftBulkFuture(Base):
    futures: list[SyftFuture]
    DEFAULT_POLL_INTERVAL: ClassVar[float] = 0.1
    responses: list[SyftResponse] = []

    def gather_completed(
        self,
        timeout: Optional[float] = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> list[SyftResponse]:
        """Wait for all futures to complete and return a list of responses.

        Returns a list of responses in the order of the futures list. If a future
        times out, it will be omitted from the list. If the timeout is reached before
        all futures complete, the function will return the responses received so far.

        Args:
            timeout: Maximum time to wait in seconds.
            poll_interval: Time in seconds between polling attempts.
        Returns:
            A list of response objects.
        Raises:
            ValueError: If timeout or poll_interval is negative.
        """
        if timeout is not None and timeout <= 0:
            raise ValueError("Timeout must be greater than 0")
        if poll_interval <= 0:
            raise ValueError("Poll interval must be greater than 0")

        pending = set(self.futures)
        deadline = time.monotonic() + (timeout or float("inf"))

        while pending and time.monotonic() < deadline:
            for future in list(pending):  # Create list to allow set modification
                if response := future.resolve(silent=True):
                    self.responses.append(response)
                    pending.remove(future)
            time.sleep(poll_interval)

        return self.responses

    @property
    def id(self) -> ULID:
        """Generate a deterministic ULID from all future IDs.

        Returns:
            A single ULID derived from hashing all future IDs.
        """
        # Combine all ULIDs and hash them
        combined = ",".join(str(f.id) for f in self.futures)
        hash_bytes = hashlib.sha256(combined.encode()).digest()[:16]
        # Use first 16 bytes of hash to create a new ULID
        return ULID.from_bytes(hash_bytes)

    @property
    def failures(self) -> list[SyftResponse]:
        """Return a list of failed responses."""
        return [r for r in self.responses if not r.is_success]

    @property
    def successes(self) -> list[SyftResponse]:
        """Return a list of successful responses."""
        return [r for r in self.responses if r.is_success]
