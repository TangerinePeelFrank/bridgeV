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
    my_address      = '0x34e0A82Ffa4a9C65A2818B3326019F446B95F256'
    w3_avax         = connect_to('source')
    source_info     = get_contract_info('source', contract_info)
    source_contract = w3_avax.eth.contract(address=source_info['address'], abi=source_info['abi'])
    #
    w3_bsc            = connect_to('destination')
    destination_info  = get_contract_info('destination', contract_info)
    destination_contract = w3_bsc.eth.contract(address=destination_info['address'], abi=destination_info['abi']) 

    if chain == 'source':
        
        arg_filter = {}
        end_block = w3_avax.eth.get_block_number()
        event_filter = source_contract.events.Deposit.create_filter(from_block=end_block-5,to_block=end_block,argument_filters=arg_filter)
        events = event_filter.get_all_entries()
        for evt in events:
            wrap_deployment = destination_contract.functions.wrap(evt.args['token'],evt.args['recipient'],evt.args['amount']).build_transaction({'from': my_address, 
                                                                                                                                   'gasPrice': w3_bsc.eth.gas_price, 
                                                                                                                                   'nonce': w3_bsc.eth.get_transaction_count(my_address), 
                                                                                                                                   'gas': 5 * (10 ** 6)})
            wrap_signed     = w3_bsc.eth.account.sign_transaction(wrap_deployment, private_key=private_key)
            wrap_hash       = w3_bsc.eth.send_raw_transaction(wrap_signed.rawTransaction)
            wrap_receipt    = w3_bsc.eth.wait_for_transaction_receipt(wrap_hash)
    else:
        arg_filter = {}
        end_block = w3_bsc.eth.get_block_number()
        event_filter = destination_contract.events.Unwrap.create_filter(from_block=end_block-5,to_block=end_block,argument_filters=arg_filter)
        events = event_filter.get_all_entries()
        for evt in events:
            withdraw_deployment = source_contract.functions.withdraw(evt.args['underlying_token'],evt.args['to'],evt.args['amount']).build_transaction({'from': my_address, 
                                                                                                                                  'gasPrice': w3_avax.eth.gas_price, 
                                                                                                                                  'nonce': w3_avax.eth.get_transaction_count(my_address), 
                                                                                                                                  'gas': 5 * (10 ** 6)})
            withdraw_signed     = w3_avax.eth.account.sign_transaction(withdraw_deployment, private_key=private_key)
            withdraw_hash       = w3_avax.eth.send_raw_transaction(withdraw_signed.rawTransaction)
            withdraw_receipt    = w3_avax.eth.wait_for_transaction_receipt(withdraw_hash)

