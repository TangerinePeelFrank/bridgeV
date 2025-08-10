from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
import time

def get_role_hash(role_name: str) -> bytes:
    return Web3.keccak(text=role_name)

def has_role(contract, role_name: str, address: str) -> bool:
    role_hash = get_role_hash(role_name)
    return contract.functions.hasRole(role_hash, address).call()

def send_transaction_with_nonce_management(w3, contract, func, private_key, *args, gas=300000):
    account = w3.eth.account.from_key(private_key)
    address = account.address

    nonce = w3.eth.get_transaction_count(address, 'pending')

    tx = func(*args).build_transaction({
        'from': address,
        'nonce': nonce,
        'gas': gas,
        'gasPrice': w3.eth.gas_price,
        'chainId': w3.eth.chain_id
    })

    signed_tx = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt

def connect_to(chain):
    if chain == 'source':
        url = "https://api.avax-test.network/ext/bc/C/rpc"
    elif chain == 'destination':
        url = "https://data-seed-prebsc-1-s1.binance.org:8545/"
    else:
        raise ValueError(f"Unknown chain {chain}")
    w3 = Web3(Web3.HTTPProvider(url))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    return w3

def get_contract_info(chain, filepath="contract_info.json"):
    with open(filepath, "r") as f:
        data = json.load(f)
    return data[chain]

def scan_blocks(chain, contract_info="contract_info.json"):
    if chain not in ["source", "destination"]:
        print(f"Invalid chain: {chain}")
        return
    
    w3 = connect_to(chain)
    opp_chain = "destination" if chain == "source" else "source"
    w3_opp = connect_to(opp_chain)

    contract_info_curr = get_contract_info(chain, contract_info)
    contract_info_opp = get_contract_info(opp_chain, contract_info)

    contract = w3.eth.contract(address=contract_info_curr["address"], abi=contract_info_curr["abi"])
    contract_opp = w3_opp.eth.contract(address=contract_info_opp["address"], abi=contract_info_opp["abi"])

    private_key = "0x7c2ebf4fbcbf34710d0cc73ac49622276ac4c833034c3f05a326a6a14b06ec4f"
    account = w3_opp.eth.account.from_key(private_key)

    if chain == "destination":
        if not has_role(contract_opp, "BRIDGE_WARDEN_ROLE", account.address):
            print(f"Account {account.address} does NOT have WARDEN_ROLE on {opp_chain} contract.")
            return
        else:
            print(f"Account {account.address} has WARDEN_ROLE on {opp_chain} contract.")

    current_block = w3.eth.block_number
    config = {
        "source": {
            "event": "Deposit",
            "func": "wrap"
        },
        "destination": {
            "event": "Unwrap",
            "func": "withdraw"
        }
    }[chain]

    event_filter = getattr(contract.events, config["event"]).create_filter(
        from_block=current_block - 5,
        to_block=current_block
    )
    events = event_filter.get_all_entries()

    for event in events:
        args = event["args"]
        if chain == "source":
            token = args["token"]
            recipient = args["recipient"]
            amount = args["amount"]
        else:
            token = args["underlying_token"]
            recipient = args["to"]
            amount = args["amount"]

        print(f"Processing event: token={token}, recipient={recipient}, amount={amount}")

        try:
            receipt = send_transaction_with_nonce_management(
                w3_opp,
                contract_opp,
                getattr(contract_opp.functions, config["func"]),
                private_key,
                token,
                recipient,
                amount
            )
            print(f"Transaction successful: {receipt.transactionHash.hex()}")
        except Exception as e:
            print(f"Error sending transaction: {e}")