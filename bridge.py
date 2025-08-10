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
    if chain not in ['source','destination']:
        print(f"Invalid chain: {chain}")
        return 0
    contracts = get_contract_info(chain, contract_info)
    w3 = connect_to(chain)
    contract = w3.eth.contract(address=contracts['address'], abi=contracts['abi'])


    private_key = "0x7c2ebf4fbcbf34710d0cc73ac49622276ac4c833034c3f05a326a6a14b06ec4f"
    account = w3.eth.account.from_key(private_key)
    w3.eth.default_account = account.address

    latest_block = w3.eth.block_number

    if chain == 'source':
        dest_info = get_contract_info('destination', contract_info)
        dest_w3 = connect_to('destination')
        dest_contract = dest_w3.eth.contract(address=dest_info['address'], abi=dest_info['abi'])
        nonce = dest_w3.eth.get_transaction_count(account.address)

        for block_num in range(latest_block - 5, latest_block + 1):
            block = w3.eth.get_block(block_num, full_transactions=True)
            for tx in block.transactions:
                receipt = w3.eth.get_transaction_receipt(tx.hash)
                logs = contract.events.Deposit().process_receipt(receipt)
                for log in logs:
                    txn = dest_contract.functions.wrap(
                        log.args.token,
                        log.args.recipient,
                        log.args.amount
                    ).build_transaction({
                        'from': account.address,
                        'nonce': nonce,
                        'gasPrice': dest_w3.eth.gas_price,
                        'gas': 5_000_000
                    })
                    signed_txn = dest_w3.eth.account.sign_transaction(txn, private_key)
                    tx_hash = dest_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"Wrap tx sent: {tx_hash.hex()} at block {block_num}")
                    nonce += 1

    elif chain == 'destination':
        source_info = get_contract_info('source', contract_info)
        source_w3 = connect_to('source')
        source_contract = source_w3.eth.contract(address=source_info['address'], abi=source_info['abi'])
        nonce = source_w3.eth.get_transaction_count(account.address)

        for block_num in range(latest_block - 5, latest_block + 1):
            block = w3.eth.get_block(block_num, full_transactions=True)
            for tx in block.transactions:
                receipt = w3.eth.get_transaction_receipt(tx.hash)
                logs = contract.events.Unwrap().process_receipt(receipt)
                for log in logs:
                    txn = source_contract.functions.withdraw(
                        log.args.underlying_token,
                        log.args.to,
                        log.args.amount
                    ).build_transaction({
                        'from': account.address,
                        'nonce': nonce,
                        'gasPrice': source_w3.eth.gas_price,
                        'gas': 5_000_000
                    })
                    signed_txn = source_w3.eth.account.sign_transaction(txn, private_key)
                    tx_hash = source_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"Withdraw tx sent: {tx_hash.hex()} at block {block_num}")
                    nonce += 1


