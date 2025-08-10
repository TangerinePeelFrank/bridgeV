from web3 import Web3
from web3.providers.rpc import HTTPProvider
from web3.middleware import ExtraDataToPOAMiddleware #Necessary for POA chains
from datetime import datetime
import json
import pandas as pd

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
    if chain not in ['source','destination']:
        print( f"Invalid chain: {chain}" )
        return 0
    
    #YOUR CODE HERE
    # Connect to both chains
    listener_web3 = connect_to(chain)
    opposite_chain = "destination" if chain == "source" else "source"
    opposite_web3 = connect_to(opposite_chain)

    contract_configs = {
        chain: {
            "web3": listener_web3,
            "info": get_contract_info(chain, contract_info)
        },
        opposite_chain: {
            "web3": opposite_web3,
            "info": get_contract_info(opposite_chain, contract_info)
        }
    }
    listener_contract = contract_configs[chain]["web3"].eth.contract(
        abi=contract_configs[chain]["info"]["abi"],
        address=contract_configs[chain]["info"]["address"]
    )
    opposite_contract = contract_configs[opposite_chain]["web3"].eth.contract(
        abi=contract_configs[opposite_chain]["info"]["abi"],
        address=contract_configs[opposite_chain]["info"]["address"]
    )
    private_key = "0x7c2ebf4fbcbf34710d0cc73ac49622276ac4c833034c3f05a326a6a14b06ec4f"
    opposite_account = opposite_web3.eth.account.from_key(private_key)
    opposite_account_address = opposite_account.address
    opposite_nonce = opposite_web3.eth.get_transaction_count(opposite_account_address)

    current_block = listener_web3.eth.block_number
    chain_config = {
        "source": {
            "event_name": "Deposit",
            "opposite_function": "wrap",
            "chain_id": 97
        },
        "destination": {
            "event_name": "Unwrap",
            "opposite_function": "withdraw",
            "chain_id": 43113
        }
    }
    config = chain_config[chain]
    event_filter = getattr(listener_contract.events, config["event_name"]).create_filter(
        from_block=current_block - 19, to_block=current_block
    )
    events = event_filter.get_all_entries()

    for event in events:
        args = event["args"]
        token_address = args["token"] if chain == "source" else args["underlying_token"]
        recipient_address = args["recipient"] if chain == "source" else args["to"]
        amount = args["amount"]

        transaction = getattr(opposite_contract.functions, config["opposite_function"])(
            token_address, recipient_address, amount
        ).build_transaction({
            "from": opposite_account_address,
            "nonce": opposite_nonce,
            "gas": 300000,
            "gasPrice": opposite_web3.eth.gas_price,
            "chainId": config["chain_id"]
        })

        opposite_nonce += 1
        signed_transaction = opposite_web3.eth.account.sign_transaction(transaction, private_key)
        transaction_hash = opposite_web3.eth.send_raw_transaction(signed_transaction.raw_transaction)
        opposite_web3.eth.wait_for_transaction_receipt(transaction_hash)