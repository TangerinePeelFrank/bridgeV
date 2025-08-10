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
    private_key = '0x7c2ebf4fbcbf34710d0cc73ac49622276ac4c833034c3f05a326a6a14b06ec4f'
    my_address = '0x34e0A82Ffa4a9C65A2818B3326019F446B95F256'
    
    w3_avax = connect_to('source')
    w3_bsc = connect_to('destination')
    source_info = get_contract_info('source', contract_info)
    source_contract = w3_avax.eth.contract(address=source_info['address'], abi=source_info['abi'])
    
    dest_info = get_contract_info('destination', contract_info)
    dest_contract = w3_bsc.eth.contract(address=dest_info['address'], abi=dest_info['abi'])

    if chain == 'source':
        end_block = w3_avax.eth.get_block_number()
        event_filter = source_contract.events.Deposit.create_filter(
            from_block=end_block-5,
            to_block=end_block
        )
        
        for evt in event_filter.get_all_entries():
            try:
                tx_hash = safe_send_transaction(
                    w3_bsc,
                    dest_contract,
                    'wrap',
                    [evt.args['token'], evt.args['recipient'], evt.args['amount']],
                    private_key
                )
                print(f"Wrap tx sent: {tx_hash.hex()}")
            except Exception as e:
                print(f"Failed to process deposit: {str(e)}")

    elif chain == 'destination':
        end_block = w3_bsc.eth.get_block_number()
        event_filter = dest_contract.events.Unwrap.create_filter(
            from_block=end_block-5,
            to_block=end_block
        )
        
        for evt in event_filter.get_all_entries():
            try:
                tx_hash = safe_send_transaction(
                    w3_avax,
                    source_contract,
                    'withdraw',
                    [evt.args['underlying_token'], evt.args['to'], evt.args['amount']],
                    private_key
                )
                print(f"Withdraw tx sent: {tx_hash.hex()}")
            except Exception as e:
                print(f"Failed to process unwrap: {str(e)}")

