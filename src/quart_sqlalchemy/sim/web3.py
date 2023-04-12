import typing as t
from decimal import Decimal

import typing_extensions as tx
import web3.providers
from ens import ENS
from eth_typing import AnyAddress
from eth_typing import ChecksumAddress
from eth_typing import HexStr
from eth_typing import Primitives
from eth_typing.abi import TypeStr
from quart import request
from quart.ctx import has_request_context
from web3.eth import Eth
from web3.geth import Geth
from web3.main import BaseWeb3
from web3.module import Module
from web3.net import Net
from web3.providers import BaseProvider
from web3.types import Wei


"""
generate new key address pairing

```zsh
python -c "from web3 import Web3; w3 = Web3(); acc = w3.eth.account.create(); print(f'private key={w3.to_hex(acc.key)}, account={acc.address}')"
```
"""


class Web3Node(tx.Protocol):
    eth: Eth
    net: Net
    geth: Geth
    provider: BaseProvider
    ens: ENS

    def is_connected(self) -> bool:
        ...

    @staticmethod
    def to_bytes(
        primitive: t.Optional[Primitives] = None,
        hexstr: t.Optional[HexStr] = None,
        text: t.Optional[str] = None,
    ) -> bytes:
        ...

    @staticmethod
    def to_int(
        primitive: t.Optional[Primitives] = None,
        hexstr: t.Optional[HexStr] = None,
        text: t.Optional[str] = None,
    ) -> int:
        ...

    @staticmethod
    def to_hex(
        primitive: t.Optional[Primitives] = None,
        hexstr: t.Optional[HexStr] = None,
        text: t.Optional[str] = None,
    ) -> HexStr:
        ...

    @staticmethod
    def to_text(
        primitive: t.Optional[Primitives] = None,
        hexstr: t.Optional[HexStr] = None,
        text: t.Optional[str] = None,
    ) -> str:
        ...

    @staticmethod
    def to_json(obj: t.Dict[t.Any, t.Any]) -> str:
        ...

    @staticmethod
    def to_wei(number: t.Union[int, float, str, Decimal], unit: str) -> Wei:
        ...

    @staticmethod
    def from_wei(number: int, unit: str) -> t.Union[int, Decimal]:
        ...

    @staticmethod
    def is_address(value: t.Any) -> bool:
        ...

    @staticmethod
    def is_checksum_address(value: t.Any) -> bool:
        ...

    @staticmethod
    def to_checksum_address(value: t.Union[AnyAddress, str, bytes]) -> ChecksumAddress:
        ...

    @property
    def api(self) -> str:
        ...

    @staticmethod
    def keccak(
        primitive: t.Optional[Primitives] = None,
        text: t.Optional[str] = None,
        hexstr: t.Optional[HexStr] = None,
    ) -> bytes:
        ...

    @classmethod
    def normalize_values(
        cls, _w3: BaseWeb3, abi_types: t.List[TypeStr], values: t.List[t.Any]
    ) -> t.List[t.Any]:
        ...

    @classmethod
    def solidity_keccak(cls, abi_types: t.List[TypeStr], values: t.List[t.Any]) -> bytes:
        ...

    def attach_modules(
        self, modules: t.Optional[t.Dict[str, t.Union[t.Type[Module], t.Sequence[t.Any]]]]
    ) -> None:
        ...

    def is_encodable(self, _type: TypeStr, value: t.Any) -> bool:
        ...


def web3_node_factory(config):
    if config["WEB3_PROVIDER_CLASS"] is web3.providers.HTTPProvider:
        provider = config["WEB3_PROVIDER_CLASS"](config["WEB3_HTTPS_PROVIDER_URI"])
        return web3.Web3(provider)


class Web3:
    node: Web3Node

    def __init__(self, node: Web3Node, default_network: str, default_chain: str):
        self.node = node
        self.default_network = default_network
        self.default_chain = default_chain

    @property
    def chain(self) -> str:
        if has_request_context():
            return request.headers.get("x-web3-chain", self.default_chain).upper()
        return self.default_chain

    @property
    def network(self) -> str:
        if has_request_context():
            return request.headers.get("x-web3-network", self.default_network).upper()
        return self.default_network
