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
    
    contracts = get_contract_info(chain, "contract_info.json")

    contract = w3.eth.contract(address=contracts['address'], abi=contracts['abi'])

    latest_block = w3.eth.block_number
    for block_num in range(latest_block - 5, latest_block + 1):
        block = w3.eth.get_block(block_num, full_transactions=True)
        for tx in block.transactions:
            receipt = w3.eth.get_transaction_receipt(tx.hash)

            logs = contract.events.Deposit().processReceipt(receipt)
            for log in logs:
                if chain == 'source':
                    destination_contracts = get_contract_info('destination', "contract_info.json")
                    destination_w3 = connect_to('destination')
                    destination_contract = destination_w3.eth.contract(
                        address=destination_contracts['address'],
                        abi=destination_contracts['abi']
                    )
                    destination_contract.functions.wrap(
                        log['args']['token'],
                        log['args']['recipient'],
                        log['args']['amount']
                    ).transact({'from': w3.eth.default_account})
                    print(f"Deposit event found in block {block_num}, called wrap() on destination")

            logs = contract.events.Unwrap().processReceipt(receipt)
            for log in logs:
                if chain == 'destination':
                    source_contracts = get_contract_info('source', "contract_info.json")
                    source_w3 = connect_to('source')
                    source_contract = source_w3.eth.contract(
                        address=source_contracts['address'],
                        abi=source_contracts['abi']
                    )
                    source_contract.functions.withdraw(
                        log['args']['token'],
                        log['args']['recipient'],
                        log['args']['amount']
                    ).transact({'from': w3.eth.default_account})
                    print(f"Unwrap event found in block {block_num}, called withdraw() on source")

if __name__ == "__main__":
    scan_blocks('source')
    scan_blocks('destination')

