# stdlib
from typing import Dict

# relative
from ....common.serde.serializable import serializable
from .syft_object import SyftObject


@serializable(recursive_serde=True)
class NoSQLTask(SyftObject):
    # version
    __canonical_name__ = "Task"
    __version__ = 1

    # fields
    uid: str
    user: str
    inputs: Dict[str, str]
    owner: Dict[str, str]
    code: str
    policy_code: str
    policy_name: str
    state: Dict[str, str]
    status: str
    created_at: str
    updated_at: str
    reviewed_by: str
    execution: Dict[str, str]
    outputs: Dict[str, str]
    reason: str = ""

    # serde / storage rules
    __attr_state__ = [
        "uid",
        "code",
        "policy_code",
        "policy_name",
        "state",
        "user",
        "status",
        "inputs",
        "outputs",
        "created_at",
        "updated_at",
        "reviewed_by",
        "execution",
        "reason",
        "owner",
    ]

    __attr_searchable__ = ["uid", "status", "user"]
    __attr_unique__ = ["uid"]
