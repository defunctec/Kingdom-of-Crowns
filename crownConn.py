import requests
import time
import json
import logging
import asyncio
import mysql.connector
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, RPC_USER, RPC_PASSWORD, CHANGE_ADDRESS, CONFS_NEEDED

# Configure logging
logging.basicConfig(filename='error_log_crownconn.txt',
                    level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')

# Create a MySQL connection
db = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME
)

# Define the RPC endpoint URL, assumed local
rpc_url = 'http://localhost:9341'

# Define the RPC authentication credentials
rpc_user = RPC_USER
rpc_password = RPC_PASSWORD

async def is_crown_wallet_online():
    try:
        # Define the RPC request payload
        payload = {
            'method': 'getblockchaininfo',
            'params': [],
            'jsonrpc': '1.0',
            'id': 1
        }

        # Convert the payload to JSON
        json_payload = json.dumps(payload)

        # Set the headers for the request
        headers = {
            'Content-Type': 'application/json'
        }

        # Set the RPC authentication credentials
        auth = (rpc_user, rpc_password)

        # Send the RPC request with authentication
        response = requests.post(rpc_url, data=json_payload, headers=headers, auth=auth)

        # Check the response status
        if response.status_code == 200:
            return True
        else:
            return False

    except Exception as e:
        logging.error(f"An error occurred while checking Crown wallet connectivity: {str(e)}")
        return False

async def get_block_count():
    # Define the RPC request payload
    payload = {
        'method': 'getblockcount',
        'params': [],
        'jsonrpc': '1.0',
        'id': 1
    }

    # Convert the payload to JSON
    json_payload = json.dumps(payload)

    # Set the headers for the request
    headers = {
        'Content-Type': 'application/json'
    }

    # Set the RPC authentication credentials
    auth = (rpc_user, rpc_password)

    # Send the RPC request with authentication
    response = requests.post(rpc_url, data=json_payload, headers=headers, auth=auth)

    # Check the response status
    if response.status_code == 200:
        # Parse the JSON response
        json_response = response.json()

        # Check if the RPC request was successful
        if 'result' in json_response:
            block_count = json_response['result']
            return block_count
        elif 'error' in json_response:
            error_message = json_response['error']['message']
            raise Exception(f"RPC request failed: {error_message}")
    else:
        raise Exception("Error connecting to the Crown wallet RPC server")

async def generate_payment_address():
    try:
        payload = {
            'method': 'getnewaddress',
            'params': [],
            'jsonrpc': '1.0',
            'id': 1
        }

        # Convert the payload to JSON
        json_payload = json.dumps(payload)

        # Set the headers for the request
        headers = {
            'Content-Type': 'application/json'
        }

        # Set the RPC authentication credentials
        auth = (rpc_user, rpc_password)

        response = requests.post(rpc_url, data=json_payload, headers=headers, auth=auth)

        if response.status_code == 200:
            json_response = response.json()
            if 'result' in json_response:
                return json_response['result']

    except Exception as e:
        logging.error(f"An error occurred while generating a payment address: {str(e)}")

    return None

def list_transactions(address, transaction_count):
    # Define the RPC endpoint URL
    rpc_url = 'http://localhost:9341'

    # Define the RPC request payload to list transactions
    payload = {
        'method': 'listtransactions',
        'params': [address, transaction_count],
        'jsonrpc': '1.0',
        'id': 1
    }

    # Set the RPC authentication credentials
    auth = (rpc_user, rpc_password)

    # Send the RPC request with authentication
    response = requests.post(rpc_url, json=payload, auth=auth)

    # Check the response status
    if response.status_code == 200:
        # Parse the JSON response
        json_response = response.json()

        # Check if the RPC request was successful
        if 'result' in json_response:
            transactions = json_response['result']
            return transactions

        elif 'error' in json_response:
            error_message = json_response['error']['message']
            logging.info(f"RPC request failed: {error_message}")

    else:
        logging.info("Error connecting to the Crown wallet RPC server")

    return None

def is_valid_crw_address(address):
    logging.info(f"********************is_valid_crw_address(), crownConn.py*********************")
    if address.startswith("CRW") and len(address) in [34, 36]:
        logging.info(f"********************End is_valid_crw_address(), crownConn.py*********************")
        return True
    else:
        logging.info(f"********************End is_valid_crw_address(), crownConn.py*********************")
        return False
    

async def get_transaction_info(txid):
    try:
        logging.info(f"********************get_transaction_info(), crownConn.py*********************")
        # Define the RPC endpoint URL
        rpc_url = 'http://localhost:9341'

        # Define the RPC request payload
        payload = {
            'method': 'gettransaction',
            'params': [txid],
            'jsonrpc': '1.0',
            'id': 1
        }

        # Set the RPC authentication credentials
        auth = (rpc_user, rpc_password)

        # Send the RPC request with authentication
        response = requests.post(rpc_url, json=payload, auth=auth)

        # Check the response status
        if response.status_code == 200:
            # Parse the JSON response
            json_response = response.json()

            # Check if the RPC request was successful
            if 'result' in json_response:
                transaction_info = json_response['result']
                logging.info(f"Retrieved transaction info for transaction: {txid}")
                return transaction_info
            elif 'error' in json_response:
                error_message = json_response['error']['message']
                logging.error(f"RPC request failed: {error_message}")
        else:
            logging.error("Error connecting to the Crown wallet RPC server")

    except Exception as e:
        logging.error(f"An error occurred while fetching transaction info: {str(e)}")

    logging.info(f"********************End get_transaction_info(), crownConn.py*********************")
    return None

async def return_funds(transaction_id, return_address, return_amount, vout):
    try:
        logging.info(f"********************return_funds(), crownConn.py*********************")
        max_timeout = 900  # Maximum timeout of 15 minutes (900 seconds)
        timeout = 0  # Initial timeout counter
        confirmed = False
        change_address = CHANGE_ADDRESS

        while timeout < max_timeout:
            transaction_info = await get_transaction_info(transaction_id)
            confirmations = transaction_info.get('confirmations', 0)

            if confirmations >= CONFS_NEEDED:
                confirmed = True
                break

            time.sleep(15)  # Wait for 15 seconds before checking again
            timeout += 15

        if confirmed:
            # Set the flag to indicate that a return transaction is being processed
            is_processing_return = True
            #logging.info(f"Dump return_address:  {return_address}")
            #logging.info(f"Dump return_amount:  {return_amount}")

            if return_address:
                # Default fee percentage for amounts greater than 1.00
                fee_percentage = 2  

                # Calculate the fee based on the return_amount
                if return_amount < 0.01:
                    fee_percentage = 20
                elif return_amount < 0.10:
                    fee_percentage = 10
                elif return_amount <= 1.00:
                    fee_percentage = 5
                else:
                    fee_percentage = 1

                # Calculate the fee_amount
                fee_amount = return_amount * (fee_percentage / 100)
                #logging.info(f"Dump fee_amount:  {fee_amount}")
                
                # Calculate the miner_fee
                miner_fee = 0.00025
                #logging.info(f"Dump miner_fee:  {miner_fee}")
                
                # Check if the fee_amount is greater than the miner_fee
                if fee_amount < miner_fee:
                    raise Exception("Fee is less than the miner fee. Please increase the fee or decrease the miner fee.")

                # Calculate the final_return_amount after deducting the fee
                final_return_amount = return_amount - fee_amount
                #logging.info(f"Dump final_return_amount:  {final_return_amount}")

                # Calculate the final_change_amount which is the fee minus the miner fee
                final_change_amount = fee_amount - miner_fee
                #logging.info(f"Dump final_change_amount:  {final_change_amount}")
                
                # Transaction is confirmed and sender's address obtained, proceed with creating the return transaction
                raw_transaction = await create_return_transaction(transaction_id, return_address, vout, final_return_amount, change_address, final_change_amount)
                signed_raw_transaction = await sign_raw_transaction(raw_transaction)

                # Broadcast the return transaction
                broadcast_result = await broadcast_transaction(signed_raw_transaction)
                if broadcast_result:
                    #logging.info(f"Return transaction created and broadcasted for transaction: {transaction_id} with fee %: {fee_percentage}")
                    is_processing_return = False
                    return True, is_processing_return
                else:
                    #logging.error(f"Failed to broadcast return transaction for transaction: {transaction_id}")
                    is_processing_return = False
                    return False, is_processing_return
            else:
                #logging.error(f"Failed to obtain the sender's address for transaction: {transaction_id}")
                is_processing_return = False
                return False, is_processing_return

        else:
            # Transaction is not confirmed within the timeout period
            #logging.info(f"Transaction {transaction_id} is not confirmed within the timeout period.")
            is_processing_return = False
            return False, is_processing_return

    except Exception as e:
        #logging.error(f"An error occurred while returning funds for transaction {transaction_id}: {str(e)}")
        is_processing_return = False
        return False, is_processing_return
    
    logging.info(f"********************End return_funds(), crownConn.py*********************")


async def create_return_transaction(transaction_id, return_address, vout, final_return_amount, change_address, change_amount):
    try:
        logging.info(f"********************create_return_transaction(), crownConn.py*********************")
        #logging.info(f'return_address: {return_address}, type: {type(return_address)}')
        #logging.info(f'vout: {vout}, type: {type(vout)}')
        #logging.info(f'change_address: {change_address}, type: {type(change_address)}')
        #logging.info(f'final_return_amount: {final_return_amount}, type: {type(final_return_amount)}')
        #logging.info(f'change_amount: {change_amount}, type: {type(change_amount)}')

        # Define the RPC request payload for creating the return transaction
        payload = {
            'method': 'createrawtransaction',
            'params': [
                [{"txid": transaction_id, "vout": vout}],  # Specify the input transaction details
                {
                    return_address: final_return_amount,  # Specify the return address and amount
                    change_address: change_amount  # Specify the change address and amount
                }
            ],
            'jsonrpc': '1.0',
            'id': 1
        }

        # Convert the payload to JSON
        json_payload = json.dumps(payload)
        logging.info(f"Dumping json_payload from create_return_transaction: {json_payload}")

        # Set the headers for the request
        headers = {
            'Content-Type': 'application/json'
        }

        # Set the RPC authentication credentials
        auth = (rpc_user, rpc_password)

        # Send the RPC request with authentication
        response = requests.post(rpc_url, data=json_payload, headers=headers, auth=auth)

        # Raise an exception if the HTTP request failed
        response.raise_for_status()

        # Parse the JSON response
        json_response = response.json()
        logging.info(f"Dumping json_response from create_return_transaction: {json_response}")

        # Check if the RPC request was successful
        if 'result' in json_response:
            raw_transaction = json_response['result']
            return raw_transaction
        elif 'error' in json_response:
            error_message = json_response['error']['message']
            raise Exception(f"RPC request failed: {error_message}")

    except requests.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err}")
    except Exception as e:
        logging.error(f"An error occurred while creating the return transaction: {str(e)}")

    logging.info(f"********************End create_return_transaction(), crownConn.py*********************")
    return None

async def sign_raw_transaction(raw_transaction):#
    logging.info(f"********************sign_raw_transaction(), crownConn.py*********************")
    MAX_ATTEMPTS = 40  # 15 seconds * 40 attempts = 10 minutes
    SLEEP_DURATION = 15  # Time in seconds between attempts

    for attempt in range(MAX_ATTEMPTS):
        try:
            #logging.info(f'Dumping raw_transaction from sign_raw_transaction: {raw_transaction}')
            # Define the RPC request payload
            payload = {
                'method': 'signrawtransaction',
                'params': [raw_transaction],
                'jsonrpc': '1.0',
                'id': 1
            }

            # Convert the payload to JSON
            json_payload = json.dumps(payload)

            # Set the headers for the request
            headers = {
                'Content-Type': 'application/json'
            }

            # Set the RPC authentication credentials
            auth = (rpc_user, rpc_password)

            # Send the RPC request with authentication
            response = requests.post(rpc_url, data=json_payload, headers=headers, auth=auth)

            # Raise an exception if the HTTP request failed
            response.raise_for_status()

            # Parse the JSON response
            json_response = response.json()
            logging.info(f"Dumping json_response from sign_raw_transaction: {json_response}")

            # Check if the RPC request was successful
            if 'result' in json_response and 'hex' in json_response['result']:
                if json_response['result'].get('complete', False):
                    signed_raw_transaction = json_response['result']['hex']
                    logging.info(f'Successfully signed raw transaction: {signed_raw_transaction}')
                    return signed_raw_transaction
                else:
                    # 'complete' is False, so log a message and continue the loop
                    logging.info(f"Transaction not fully signed. Waiting for a bit.")
                    time.sleep(SLEEP_DURATION)
                    continue
            elif 'error' in json_response:
                error_message = json_response['error']['message']
                logging.error(f"RPC request failed: {error_message}")
                raise Exception(f"RPC request failed: {error_message}")
            else:
                logging.error("Unexpected response format")

        except requests.HTTPError as http_err:
            logging.error(f"HTTP error occurred: {http_err}")
            break  # exit the loop on HTTP errors
        except Exception as e:
            logging.error(f"An error occurred while signing the transaction: {str(e)}")
            break  # exit the loop on any other errors

    logging.error(f"Exceeded maximum attempts to sign transaction. Transaction could not be fully signed.")
    raise Exception("Exceeded maximum attempts to sign transaction. Transaction could not be fully signed.")
    logging.info(f"********************End sign_raw_transaction(), crownConn.py*********************")

async def broadcast_transaction(signed_raw_transaction):
    logging.info(f"********************broadcast_transaction(), crownConn.py*********************")
    try:
        # Define the RPC request payload
        payload = {
            'method': 'sendrawtransaction',
            'params': [signed_raw_transaction],
            'jsonrpc': '1.0',
            'id': 1
        }

        # Convert the payload to JSON
        json_payload = json.dumps(payload)
        #logging.info(f"JSON payload: {json_payload}")

        # Set the headers for the request
        headers = {
            'Content-Type': 'application/json'
        }

        # Set the RPC authentication credentials
        auth = (rpc_user, rpc_password)

        # Send the RPC request with authentication
        response = requests.post(rpc_url, data=json_payload, headers=headers, auth=auth)
        logging.info(f"Response status: {response.status_code}, body: {response.text}")
        # Check the response status
        if response.status_code == 200:
            # Parse the JSON response
            json_response = response.json()
            #logging.info(f"Dumping json_response from broadcast_transaction: {json_response}")
            # Check if the RPC request was successful
            if 'result' in json_response:
                transaction_id = json_response['result']
                return transaction_id
            elif 'error' in json_response:
                error_message = json_response['error']['message']
                lower_error_message = error_message.lower()
                if 'insufficient priority' in lower_error_message:
                    logging.error("Insufficient priority error occurred while trying to send the transaction. Consider increasing the transaction fee.")
                elif 'insufficient funds' in lower_error_message:
                    logging.error("Insufficient funds error occurred while trying to send the transaction.")
                elif 'double spend' in lower_error_message:
                    logging.error("Double spend error occurred while trying to send the transaction.")
                elif 'invalid address' in lower_error_message:
                    logging.error("Invalid address error occurred while trying to send the transaction.")
                # and so on for other errors...
                raise Exception(f"RPC request failed: {error_message}")
        else:
            raise Exception("Error connecting to the Crown wallet RPC server")

    except Exception as e:
        logging.error(f"An error occurred while broadcasting the transaction: {str(e)}")

    logging.info(f"********************End broadcast_transaction(), crownConn.py*********************")

async def get_sender_address(transaction_id):
    try:
        logging.info(f"********************get_sender_address(), crownConn.py*********************")
        # Define the RPC request payload
        payload = {
            'method': 'getrawtransaction',
            'params': [transaction_id],
            'jsonrpc': '1.0',
            'id': 1
        }
        #logging.info(f"Payload for get_sender_address: {payload}")

        # Convert the payload to JSON
        json_payload = json.dumps(payload)

        # Set the headers for the request
        headers = {
            'Content-Type': 'application/json'
        }

        # Set the RPC authentication credentials
        auth = (rpc_user, rpc_password)

        # Send the RPC request with authentication
        #logging.info("Sending getrawtransaction request...")
        response = requests.post(rpc_url, data=json_payload, headers=headers, auth=auth)
        response.raise_for_status()

        # Print the response content for troubleshooting
        #logging.info(f"Response content: {response.content}")

        # Parse the JSON response
        json_response = response.json()
        #logging.info(f"Received json_response response: {json_response}")

        # Check if the RPC request was successful
        if 'result' in json_response:
            raw_transaction_hex = json_response['result']
            #logging.info(f"Raw transaction hex: {raw_transaction_hex}")

            # Define the RPC request payload for decoding the raw transaction
            payload = {
                'method': 'decoderawtransaction',
                'params': [raw_transaction_hex],
                'jsonrpc': '1.0',
                'id': 1
            }

            # Convert the payload to JSON
            json_payload = json.dumps(payload)

            # Send the RPC request with authentication
            #logging.info("Sending decoderawtransaction request...")
            response = requests.post(rpc_url, data=json_payload, headers=headers, auth=auth)
            response.raise_for_status()

            # Parse the JSON response
            json_response = response.json()
            #logging.info(f"Received decoderawtransaction response: {json_response}")

            # Extract the sender address from the inputs
            vin = json_response.get('result', {}).get('vin', [])
            #logging.info(f"Vin data: {vin}")
            for v in vin:
                prev_tx_id = v.get('txid')
                #logging.info(f"Type of json_response: {type(json_response)}")
                #logging.info(f"Type of v: {type(v)}")
                
                if prev_tx_id:
                    raw_tx = await get_raw_transaction(prev_tx_id)  # You will need to implement this function
                    #logging.info(f"Type of raw_tx: {type(raw_tx)}")
                    #logging.info(f"Dump raw_tx: {raw_tx}")

                    # Decode the raw transaction
                    prev_tx = await decode_raw_transaction(raw_tx.get('result', ''))  # You will need to implement this function
                    #logging.info(f"Type of prev_tx after decoding: {type(prev_tx)}")
                    #logging.info(f"Dump prev_tx after decoding: {prev_tx}")

                    prev_vout_list = prev_tx.get('vout', [])
                    #logging.info(f"prev_vout_list: {prev_vout_list}")
                    prev_vout_index = v.get('vout')
                    #logging.info(f"prev_vout_index: {prev_vout_index}")

                    if prev_vout_index < len(prev_vout_list):
                        prev_vout = prev_vout_list[prev_vout_index]
                        if 'scriptPubKey' in prev_vout and 'addresses' in prev_vout['scriptPubKey']:
                            addresses = prev_vout['scriptPubKey']['addresses']
                            #logging.info(f"Address found in vin element: {addresses}")
                            return addresses[0] if addresses else None
                        else:
                            logging.info(f"No 'scriptPubKey' or 'addresses' found in vin element: {v}")
                            continue
                    else:
                        logging.info(f"prev_vout_index out of range for vout list: {prev_vout_list}")

    except Exception as e:
        logging.error(f"An error occurred while retrieving the sender address: {str(e)}")
        logging.info(f"********************End get_sender_address(), crownConn.py*********************")

async def get_raw_transaction(transaction_id):
    try:
        logging.info(f"********************get_raw_transaction(), crownConn.py*********************")
        # Define the RPC request payload
        payload = {
            'method': 'getrawtransaction',
            'params': [transaction_id],
            'jsonrpc': '1.0',
            'id': 1
        }

        # Convert the payload to JSON
        json_payload = json.dumps(payload)

        # Set the headers for the request
        headers = {
            'Content-Type': 'application/json'
        }

        # Set the RPC authentication credentials
        auth = (rpc_user, rpc_password)

        # Send the RPC request with authentication
        response = requests.post(rpc_url, data=json_payload, headers=headers, auth=auth)

        # Raise an exception if the HTTP request failed
        response.raise_for_status()

        # Parse the JSON response
        json_response = response.json()

        # Check if the RPC request was successful
        if 'result' in json_response:
            return json_response
        elif 'error' in json_response:
            error_message = json_response['error']['message']
            raise Exception(f"RPC request failed: {error_message}")

    except requests.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err}")
    except Exception as e:
        logging.error(f"An error occurred while getting the raw transaction: {str(e)}")

    logging.info(f"********************End get_raw_transaction(), crownConn.py*********************")
    return None

async def decode_raw_transaction(raw_tx):
    logging.info(f"********************decode_raw_transaction(), crownConn.py*********************")
    payload = {
        'method': 'decoderawtransaction',
        'params': [raw_tx],
        'jsonrpc': '1.0',
        'id': 1
    }

    json_payload = json.dumps(payload)
    headers = {'Content-Type': 'application/json'}
    auth = (rpc_user, rpc_password)

    response = requests.post(rpc_url, data=json_payload, headers=headers, auth=auth)
    response.raise_for_status()

    json_response = response.json()

    if 'result' in json_response:
        return json_response['result']
    elif 'error' in json_response:
        error_message = json_response['error']['message']
        raise Exception(f"RPC request failed: {error_message}")

    logging.info(f"********************End decode_raw_transaction(), crownConn.py*********************")
    return None
