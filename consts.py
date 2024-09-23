from models import *
from envs import *
from typing import Dict, Any
from urllib.parse import urlparse

CURRENCY_ADDRESSES: Dict[str, Currency] = {
    '0xffffffff0000000000000000000000000000babb': 'BAX',
    '0xffffffffbabb0000000000000000000000000000': 'RED',
    '0xffffffffbabb0000000000000000000000000010': 'GBP',
}

CURRENCY_DECIMALS: Dict[Currency, int] = {
    'BAX': 18,
    'RED': 18,
    'GBP': 6
}

POLKADOT_INSTANCE: Dict[Location, str] = {
    'L1': L1_POLKASCAN,
    'L2': L2_POLKASCAN,
}

BLOCKSCOUT_INSTANCE: Dict[Location, str] = {
    'L1': L1_BLOCKSCOUT,
    'L2': L2_BLOCKSCOUT,
}