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

    if chain not in ("source", "destination"):
        print(f"Error: Unsupported chain '{chain}'. Must be 'source' or 'destination'.")
        return

    

    current_w3 = connect_to(chain)
    target_chain = "destination" if chain == "source" else "source"
    target_w3 = connect_to(target_chain)


    contracts_data = {
        chain: {
            "web3": current_w3,
            "contract_info": get_contract_info(chain, contract_info)
        },
        target_chain: {
            "web3": target_w3,
            "contract_info": get_contract_info(target_chain, contract_info)
        }
    }


    current_contract = contracts_data[chain]["web3"].eth.contract(
        address=contracts_data[chain]["contract_info"]["address"],
        abi=contracts_data[chain]["contract_info"]["abi"]
    )
    target_contract = contracts_data[target_chain]["web3"].eth.contract(
        address=contracts_data[target_chain]["contract_info"]["address"],
        abi=contracts_data[target_chain]["contract_info"]["abi"]
    )

    private_key = "0x7c2ebf4fbcbf34710d0cc73ac49622276ac4c833034c3f05a326a6a14b06ec4f"
    target_account = target_w3.eth.account.from_key(private_key)
    target_address = target_account.address
    nonce = target_w3.eth.get_transaction_count(target_address)

    chain_params = {
        "source": {
            "event": "Deposit",
            "call_function": "wrap",
            "chain_id": 97
        },
        "destination": {
            "event": "Unwrap",
            "call_function": "withdraw",
            "chain_id": 43113
        }
    }

    params = chain_params[chain]
    latest_block = current_w3.eth.block_number
    start_block = max(latest_block - 19, 0)

    event_filter = getattr(current_contract.events, params["event"]).create_filter(
        from_block=start_block,
        to_block=latest_block
    )
    event_logs = event_filter.get_all_entries()


    for ev in event_logs:
        ev_args = ev["args"]

        token = ev_args["token"] if chain == "source" else ev_args["underlying_token"]
        recipient = ev_args["recipient"] if chain == "source" else ev_args["to"]
        amount = ev_args["amount"]

        txn = getattr(target_contract.functions, params["call_function"])(
            token, recipient, amount
        ).build_transaction({
            "from": target_address,
            "nonce": nonce,
            "gas": 300000,
            "gasPrice": target_w3.eth.gas_price,
            "chainId": params["chain_id"]
        })


        signed_txn = target_w3.eth.account.sign_transaction(txn, private_key)
        tx_hash = target_w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        target_w3.eth.wait_for_transaction_receipt(tx_hash)

        nonce += 1
