from dataclasses import dataclass
from typing import Literal, Optional, Any

Location = Literal['L1', 'L2']
Currency = Literal['BAX', 'RED', 'GBP']

@dataclass
class Account:
    location: Location
    address: str

@dataclass
class Amount:
    currency: Currency
    value: int

@dataclass
class Event:
    block_number: int
    idx: int
    pallet: str
    name: str
    data: Any
    link: str

@dataclass
class Events:  
    sender: list[Event]  
    receiver: Optional[list[Event]]

TransactionStatus = Literal['InProgress', 'Done', 'Error']

@dataclass
class Block:
    number: int
    link: str

    @classmethod
    def from_polkascan(cls, number: int, polkascan: str):
        from urllib.parse import urlparse, urljoin, urlunparse

        polkadot_url = urlparse(polkascan)
        polkadot_path = urljoin(f'{polkadot_url.path}/', f'block/{number}')
        link = urlunparse(polkadot_url._replace(path=polkadot_path))
        
        return cls(number, link)

@dataclass
class Transaction:
    tx_hash: str
    xcm_id: str
    sender: Account
    receiver: Account
    amount: Amount
    sent_in_block: Block
    received_in_block: Optional[Block]
    events: Events
    status: TransactionStatus
    error: Optional[str]

@dataclass
class ExtrinsicIdx:
    block_number: int
    idx: int

@dataclass
class EthTransaction:
    tx_hash: str
    extrinsic_idx: ExtrinsicIdx
    sender: Account
    receiver: Account
    amount: Amount
