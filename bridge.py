from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware #Necessary for POA chains
from datetime import datetime
import json

def connect_to(chain):
    if chain == 'source':  # The source contract chain is avax
        api_url = f"https://api.avax-test.network/ext/bc/C/rpc" #AVAX C-chain testnet

    if chain == 'destination':  # The destination contract chain is bsc
        api_url = f"https://data-seed-prebsc-1-s1.binance.org:8545/" #BSC testnet

    if chain in ['source','destination']:
        w3 = Web3(Web3.HTTPProvider(api_url))
        # inject the poa compatibility middleware to the innermost layer
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def get_contract_info(chain, contract_info):
    """
        Load the contract_info file into a dictionary
        This function is used by the autograder and will likely be useful to you
    """
    try:
        with open(contract_info, 'r')  as f:
            contracts = json.load(f)
    except Exception as e:
        print( f"Failed to read contract info\nPlease contact your instructor\n{e}" )
        return 0
    return contracts[chain]



def scan_blocks(chain, contract_info="contract_info.json"):
    """
        chain - (string) should be either "source" or "destination"
        Scan the last 5 blocks of the source and destination chains
        Look for 'Deposit' events on the source chain and 'Unwrap' events on the destination chain
        When Deposit events are found on the source chain, call the 'wrap' function the destination chain
        When Unwrap events are found on the destination chain, call the 'withdraw' function on the source chain
    """

    # This is different from Bridge IV where chain was "avax" or "bsc"

    
    
    current_w3 = connect_to(chain)
    other_chain = 'destination' if chain == 'source' else 'source'
    other_w3 = connect_to(other_chain)

    current_contract_data = get_contract_info(chain, contract_info)
    other_contract_data = get_contract_info(other_chain, contract_info)

    current_contract = current_w3.eth.contract(address=current_contract_data['address'], abi=current_contract_data['abi'])
    other_contract = other_w3.eth.contract(address=other_contract_data['address'], abi=other_contract_data['abi'])

    priv_key = "0x7c2ebf4fbcbf34710d0cc73ac49622276ac4c833034c3f05a326a6a14b06ec4f"
    other_account = other_w3.eth.account.from_key(priv_key)
    other_addr = other_account.address
    nonce_counter = other_w3.eth.get_transaction_count(other_addr)

    event_map = {
        'source': ('Deposit', 'wrap', 43113),       
        'destination': ('Unwrap', 'withdraw', 97) 
    }
    event_name, function_name, chain_id = event_map[chain]

    latest_block = current_w3.eth.block_number
    from_block = max(0, latest_block - 5) 


    event_filter = getattr(current_contract.events, event_name).create_filter(from_block=from_block, to_block=latest_block)

    try:
        entries = event_filter.get_all_entries()
    except Exception as ex:
        print(f"Failed to fetch events: {ex}")
        return

    for ev in entries:
        try:
            ev_args = ev.args

            token = ev_args.token if chain == 'source' else ev_args.underlying_token
            receiver = ev_args.recipient if chain == 'source' else ev_args.to
            value = ev_args.amount

            txn = getattr(other_contract.functions, function_name)(token, receiver, value).build_transaction({
                'from': other_addr,
                'nonce': nonce_counter,
                'gas': 300000,
                'gasPrice': other_w3.eth.gas_price,
                'chainId': chain_id
            })

            signed_txn = other_w3.eth.account.sign_transaction(txn, priv_key)
            tx_hash = other_w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            print(f"Transaction sent: {tx_hash.hex()} for event {event_name}")


            other_w3.eth.wait_for_transaction_receipt(tx_hash)
            nonce_counter += 1
        except Exception as inner_ex:
            print(f"Error handling event {ev}: {inner_ex}")

