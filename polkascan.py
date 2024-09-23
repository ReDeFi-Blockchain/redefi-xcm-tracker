from models import *
from envs import *
from consts import *

import json
import re
from urllib.parse import urlparse
from typing import Dict, Optional, Any
import pymysql
from pymysql import Connection
from substrateinterface.base import ss58_encode, ss58_decode
from urllib.parse import urljoin, urlunparse
from substrateinterface import SubstrateInterface
from scalecodec.base import RuntimeConfigurationObject, ScaleBytes

connections: Dict[Location, Connection] = {}
for (location, url) in [('L1', L1_DB_CONNECTION), ('L2', L2_DB_CONNECTION)]:
    url = urlparse(url)
    connections[location] = pymysql.connect(
        host=url.hostname,
        port=url.port,
        user=url.username,
        password=url.password,
        database=url.path[1:],
        cursorclass=pymysql.cursors.DictCursor)

substrates: Dict[Location, SubstrateInterface] = {}
if VERY_OLD_RELAY:
    for (location, url) in [('L1', L1_SUBSTRATE_RPC_URL), ('L2', L2_SUBSTRATE_RPC_URL)]:
        substrates[location] = SubstrateInterface(url)

def get_transaction(tx_hash: str) -> Transaction:
    if not re.match(r'^0[xX][0-9a-fA-F]{64}$', tx_hash):
        raise Exception('Invalid hash format')

    tx = fetch_tx('L1', tx_hash)
    if tx is None:
        tx = fetch_tx('L2', tx_hash)

    if tx is None:
        raise Exception('Could not find transaction')
    
    sender_events = fetch_extrinsic_events(tx.sender.location, tx.extrinsic_idx)

    xcm_error = get_xcm_error(sender_events)
    if xcm_error:
        return Transaction(
            tx_hash=tx.tx_hash,
            link_to_scanner=build_tx_link(tx.sender.location, tx.tx_hash),
            xcm_id=None,
            sender=tx.sender,
            receiver=tx.receiver,
            amount=tx.amount,
            sent_in_block=Block.from_polkascan(
                tx.extrinsic_idx.block_number,
                POLKADOT_INSTANCE[tx.sender.location]),
            received_in_block=None,
            events=Events(sender=sender_events, receiver=None),
            status='Error',
            error=xcm_error
        )
    
    xcm_id: Optional[str] = None
    if tx.sender.location == 'L1' and VERY_OLD_RELAY:
        xcm_id = find_xcm_id_in_dmp_queue(tx)
    else:
        xcm_id = find_xcm_id_in_events(sender_events)

    if xcm_id is None:
        raise Exception('Tx is cross chain transfer, but could not find xcm id')

    processed_event = fetch_processed_event(tx.receiver.location, xcm_id)

    return Transaction(
        tx_hash=tx.tx_hash,
        link_to_scanner=build_tx_link(tx.sender.location, tx.tx_hash),
        xcm_id=xcm_id,
        sender=tx.sender,
        receiver=tx.receiver,
        amount=tx.amount,
        sent_in_block=Block.from_polkascan(
                tx.extrinsic_idx.block_number,
                POLKADOT_INSTANCE[tx.sender.location]),
        received_in_block=Block.from_polkascan(
            processed_event.block_number, 
            POLKADOT_INSTANCE[tx.receiver.location]) if processed_event else None,
        events=Events(
            sender=sender_events,
            receiver=[processed_event] if processed_event else None,
        ),
        status='Done' if processed_event else 'InProgress',
        error=None
    )

# Search tx transaction by hash
def fetch_tx(location: Location, tx_hash: str) -> Optional[EthTransaction]:
    with connections[location].cursor() as cursor:
        cursor.execute("""
            SELECT
                codec_block_extrinsic.block_number,
                codec_block_extrinsic.extrinsic_idx,
                codec_block_extrinsic.data as extrinsic_data,
                event.data as event_data
            FROM
                codec_block_extrinsic,
                (
                    SELECT
                        codec_block_event.block_number,
                        codec_block_event.extrinsic_idx,
                        codec_block_event.data
                    FROM
                        codec_block_event
                    WHERE
                        event_module = 'Ethereum' AND
                        event_name = 'Executed' AND 
                        json_extract(data, '$.attributes.transaction_hash') = %s
                    LIMIT
                        1
                ) AS event
            WHERE 
                codec_block_extrinsic.block_number = event.block_number AND
                codec_block_extrinsic.extrinsic_idx = event.extrinsic_idx
            LIMIT
                1
            ;
        """, (tx_hash,))
        
        tx = cursor.fetchone()
        if tx is None:
            return None
        
        return parse_tx(location, tx_hash, tx)

# Parse ethereum tx from extrinsic + event data 
def parse_tx(location: Location, tx_hash: str, tx: Dict[str, Any]) -> Optional[EthTransaction]:
    block_number = int(tx['block_number'])
    extrinsic_idx = int(tx['extrinsic_idx'])
    
    event_data = json.loads(tx['event_data'])
    extrinsic_data = json.loads(tx['extrinsic_data'])

    sender = event_data['attributes']['from']
    sender = f'{int(sender, 16):#066x}'

    currency_address = event_data['attributes']['to']
    currency = CURRENCY_ADDRESSES.get(currency_address)
    if currency is None:
        # print(f'Tx {tx_hash} contains invalid currency {currency_address}')
        raise Exception('Tx is not cross chain transfer')
    
    # TODO(vklachkov): Theoretically we can have multiple parachains
    chain_id: int
    receiver: int
    amount: int

    try:
        input = extrinsic_data['call']['call_args'][0]['value']['EIP1559']['input']
        
        decoded = decode_tx_input(input)
        if decoded is None:
            return None

        chain_id = decoded['chain_id']
        receiver = decoded['receiver']
        amount = decoded['amount'] / pow(10, CURRENCY_DECIMALS[currency])
    except Exception as e:
        # print(f'Failed to decode tx {tx_hash}: {e}')
        raise Exception('Tx is not cross chain transfer')

    return EthTransaction(
        tx_hash=tx_hash,
        extrinsic_idx=ExtrinsicIdx(block_number, extrinsic_idx),
        sender=Account(location=location,
                       address=ss58_encode(sender)),
        receiver=Account(location=dest_location(location), 
                         address=ss58_encode(receiver)),
        amount=Amount(currency, amount))

# Decode crossChainTransfer(uint64,address,uint256)
def decode_tx_input(input: str) -> Optional[Dict[str, Any]]:
    input = input[2:]

    if len(input) != 200:
        return None
    
    selector = input[:8]
    if selector != 'ee18d38e':
        return None
    
    chain_id = int(input[8:72], 16)
    receiver = f'0x{input[72:136]}'
    amount = int(input[136:200], 16)

    return { 'chain_id': chain_id, 'receiver': receiver, 'amount': amount }

def dest_location(source: Location) -> Location:
    return 'L1' if source == 'L2' else 'L2'

# Fetch all events per extrinsic from specified polkascan
def fetch_extrinsic_events(location: Location, extrinsic_idx: ExtrinsicIdx) -> list[Event]:
    with connections[location].cursor() as cursor:
        cursor.execute("""
            SELECT
                event_idx,
                event_module,
                event_name,
                data
            FROM
                codec_block_event
            WHERE 
                block_number = %s AND
                extrinsic_idx = %s
            ;
        """, (extrinsic_idx.block_number, extrinsic_idx.idx,))

        events = []

        for row in cursor.fetchall():
            block_number = extrinsic_idx.block_number
            idx = row['event_idx']
            pallet = row['event_module']
            name = row['event_name']
            data = json.loads(row['data'])
            link = build_event_link(location, block_number, idx)

            events.append(Event(
                block_number,
                idx,
                pallet,
                name,
                data,
                link
            ))
        
        return events

# Build an url to the event on Polkascan
def build_event_link(location: Location, block_number: int, idx: int) -> str:
    polkadot_url = urlparse(POLKADOT_INSTANCE[location])
    polkadot_path = urljoin(f'{polkadot_url.path}/', f'event/{block_number}-{idx}')
    return urlunparse(polkadot_url._replace(path=polkadot_path))

# Build an url to the tx on Blockscout
def build_tx_link(location: Location, tx_hash: str) -> str:
    blockscout_url = urlparse(BLOCKSCOUT_INSTANCE[location])
    blockscout_path = urljoin(f'{blockscout_url.path}/', f'tx/{tx_hash}')
    return urlunparse(blockscout_url._replace(path=blockscout_path))

# "Looks for the Xcm Attempted event and checks it for errors
def get_xcm_error(events: list[Event]) -> Optional[str]:
    attempted: Optional[Event] = None
    for event in events:
        if event.pallet == 'XcmPallet' and event.name == 'Attempted':
            attempted = event
            break
    
    if attempted is None:
        raise Exception('Tx is cross chain transfer, but could not find Xcm Attempted event')
    
    outcome = attempted.data['attributes']['outcome']

    if 'Complete' in outcome:
        return None
    elif 'Incomplete' in outcome:
        return f'{outcome["Incomplete"]["error"]}'
    elif 'Error' in outcome:
        return f'{outcome["Error"]["error"]}'
    else:
        raise Exception('Tx is cross chain transfer, but Xcm Attempted event is invalid')

# Looks for the Xcm Sent event and extracts the identifier from it
def find_xcm_id_in_events(events: list[Event]) -> Optional[str]:
    sent: Optional[Event] = None
    for event in events:
        if event.pallet == 'XcmPallet' and event.name == 'Sent':
            sent = event
            break

    if sent is None:
        return None

    message_id = sent.data['attributes']['message_id']
    
    return message_id

# Looks at the XCM messages on the chain and searches for the XCM ID for the transaction
def find_xcm_id_in_dmp_queue(tx: EthTransaction) -> Optional[str]:
    assert VERY_OLD_RELAY

    relay = substrates['L1']
    parachain = substrates['L2']

    parachain_id = parachain.query('ParachainInfo', 'ParachainId').decode()
    
    block_number = tx.extrinsic_idx.block_number
    block_hash = relay.get_block_hash(block_number)
    
    xcm_messages = relay.query('Dmp', 'DownwardMessageQueues', [parachain_id], block_hash=block_hash)
    
    for message in xcm_messages.decode():
        if message['sent_at'] != block_number:
            continue
        
        xcm_message = decode_xcm_message(relay, block_hash, message['msg'])
        
        if 'V3' not in xcm_message:
            raise Exception('Unsupported XCM version')

        # Unfortunately, there is no 100% way to know that this XCM message was sent from some extrinsic.
        # Therefore, if the amount, currency, and receiver in the XCM message match those specified
        # in the Eth transaction, we consider that the XCM message relates to our transaction
        if is_xcm_message_eq_to_tx(xcm_message, tx):
            return get_xcm_id(xcm_message)
    
    return None

def decode_xcm_message(substrate: SubstrateInterface, block_hash: str, msg: str) -> Any:
    runtime_config = RuntimeConfigurationObject()

    chain_metadata = substrate.get_metadata(block_hash=block_hash)
    runtime_config.add_portable_registry(chain_metadata)

    xcm = runtime_config.create_scale_object(
        'xcm::VersionedXcm', data=ScaleBytes(bytearray.fromhex(msg[2:]))
    ).decode()

    return xcm

def is_xcm_message_eq_to_tx(xcm_message: Any, tx: EthTransaction) -> bool:
    assert 'V3' in xcm_message

    same_value = False
    same_currency = False
    same_receiver = False

    for instruction in xcm_message['V3']:
        if 'ReceiveTeleportedAsset' in instruction:
            instruction = instruction['ReceiveTeleportedAsset'][0]
            
            fun = instruction['fun']['Fungible'] / pow(10, CURRENCY_DECIMALS[tx.amount.currency])
            same_value = tx.amount.value == fun
            
            currency = instruction['id']['Concrete']['interior']['X1']['AccountKey20']['key']
            same_currency = tx.amount.currency == CURRENCY_ADDRESSES[currency]
        
        elif 'DepositAsset' in instruction:
            instruction = instruction['DepositAsset']

            receiver = instruction['beneficiary']['interior']['X1']['AccountKey20']['key']
            receiver = f'{int(receiver, 16):#066x}'
            same_receiver = tx.receiver.address == ss58_encode(receiver)

    return same_value and same_currency and same_receiver

def get_xcm_id(xcm_message: Any) -> Optional[str]:
    assert 'V3' in xcm_message

    for instruction in xcm_message['V3']:
        if 'SetTopic' in instruction:
            return instruction['SetTopic']
        
    return None

# Search xcm processed event by xcm id
def fetch_processed_event(location: Location, xcm_id: str) -> Optional[Event]:
    with connections[location].cursor() as cursor:
        PALLET: str = 'MessageQueue'
        EVENT_NAME: str = 'Processed'

        cursor.execute("""
            SELECT
                block_number,
                event_idx,
                data
            FROM
                codec_block_event
            WHERE
                event_module = %s AND
                event_name = %s AND 
                json_extract(data, '$.attributes.id') = %s
            LIMIT
                1
            ;
        """, (PALLET, EVENT_NAME, xcm_id))
        
        event = cursor.fetchone()
        if event is None:
            return None
    
        block_number = int(event['block_number'])
        idx = int(event['event_idx'])
        data = json.loads(event['data'])
        link = build_event_link(location, block_number, idx)
    
        return Event(block_number=block_number,
                     idx=idx,
                     pallet=PALLET,
                     name=EVENT_NAME,
                     data=data,
                     link=link)
