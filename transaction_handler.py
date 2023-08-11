#!/usr/bin/env python3

import sys
import logging
import requests
import json
import asyncio
import mysql.connector
from collections import deque
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, RPC_USER, RPC_PASSWORD
from crownConn import get_transaction_info, return_funds, get_sender_address

# Create a MySQL connection
db = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME
)

# Define a queue to store incoming wallet notifications
notification_queue = deque()

# Configure logging
logging.basicConfig(filename='error_log_tx_handler.txt',
                    level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')

async def main():
    try:
        logging.info(f"********************main(), transaction_handler.py*********************")
        # Define a flag to track whether a return transaction is being processed
        is_processing_return = False

        # Get the transaction ID from the command-line argument
        transaction_id = sys.argv[1]
        logging.info(f"Transaction ID: {transaction_id}")

        # Retrieve transaction details using the gettransaction command
        transaction_info = await get_transaction_info(transaction_id)
        logging.info(f"Printing transaction info: {transaction_info}")

        if transaction_info:
            # Extract relevant information from the transaction details
            confirmations = transaction_info.get('confirmations', 0)
            amount = transaction_info.get('amount', 0)
            address = transaction_info.get('details', [])[0].get('address')
            vout = transaction_info.get('details', [])[0].get('vout')

            if amount < 0:
                logging.info(f"Wallet transaction or confirmation detected in txid: {transaction_id}")
            elif confirmations >= 6:
                logging.info(f"Transaction confirmed with 1 or more confs: {transaction_id}")
                try:
                    # Check if the address is a valid payment address
                    if await is_valid_payment_address(address) is True:
                        amount = transaction_info.get('amount', 0)
                        logging.info(f"Dump amount: {amount}, type: {type(amount)}")
                        cleaned_amount = float(''.join(filter(str.isdigit, str(amount))))
                        # Check which tier the user pays
                        if amount == 10.10:
                            tier = "1"
                            logging.info(f"10.10 CRW sent in txid: {transaction_id}")
                            await activate_account(address, tier)
                        elif amount == 50.50:
                            tier = "2"
                            logging.info(f"50.50 CRW sent in txid: {transaction_id}")
                            await activate_account(address, tier)
                        elif amount == 100.10:
                            tier = "3"
                            logging.info(f"100.10 CRW sent in txid: {transaction_id}")
                            await activate_account(address, tier)
                        elif amount == 500.50:
                            tier = "4"
                            logging.info(f"500.50 CRW sent in txid: {transaction_id}")
                            await activate_account(address, tier)
                        elif amount == 1000.10:
                            tier = "5"
                            logging.info(f"1000.10 CRW sent in txid: {transaction_id}")
                            await activate_account(address, tier)
                        else:
                            logging.info(f"Payment doesn't match any amounts, returning funds.")
                            
                            # Check if a return transaction is already being processed
                            if not is_processing_return:
                                sender_address = await get_sender_address(transaction_id)
                                if sender_address is not None:
                                    logging.info(f"Sender address found, {sender_address} running return_funds function.")
                                    # Set the flag to indicate that a return transaction is being processed
                                    success, is_processing_return = await return_funds(transaction_id, sender_address, amount, vout)
                                    if success:
                                        logging.info("FUNDS SENT!!")
                                    else:
                                        logging.error("Failed to send funds.")
                            else:
                                logging.info("A return transaction is already being processed. Waiting for the previous return transaction to complete.")

                    else: # This is for other types of transactions throughout the game.
                        logging.info(f"Not a payment address, must be another type of tx: {transaction_id}")

                except KeyError:
                    logging.error("Missing transaction amount in transaction details")
                except Exception as e:
                    logging.error(f"An error occurred while processing transaction: {str(e)}")
            else:
                # Handle initial recognition event
                if confirmations <= 5:
                    #logging.info(f"Seen transaction, but 5 or less confirms: {transaction_id}")

                    # Process any queued notifications while waiting for the return transaction to complete
                    while notification_queue:
                        notification = notification_queue.popleft()
                        process_notification(notification)
        else:
            logging.error(f"Issue with transaction info: {transaction_id}")
        # Reset the flag back to False since the return transaction is completed
        is_processing_return = False
        logging.info(f"********************END main(), transaction_handler.py*********************")
    except IndexError:
        logging.error("Transaction ID argument missing")
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")


async def is_valid_payment_address(address):
    try:
        # Check if the address exists in the players table
        query = "SELECT * FROM players WHERE payment_address = %s"
        with db.cursor() as cursor:
            cursor.execute(query, (address,))
            result = cursor.fetchone()

            # If there is a result, the address exists
            if result:
                return True
            else:
                logging.info("Payment address does not exist in the players table.")
                return False

    except Exception as e:
        logging.error(f"An error occurred while checking the payment address validity: {str(e)}")

    return False


async def activate_account(payment_address, tier):
    try:
        # Retrieve the Discord ID associated with the payment address
        query = "SELECT discord_id FROM players WHERE payment_address = %s"
        with db.cursor() as cursor:
            cursor.execute(query, (payment_address,))
            result = cursor.fetchone()
            discord_id = result[0] if result else None

            if discord_id:
                # Update the activated field and tier for the given payment address
                update_query = "UPDATE players SET activated = true, tier = %s WHERE payment_address = %s"
                values = (tier, payment_address)
                cursor.execute(update_query, values)

                # Commit the changes
                db.commit()

                logging.info(f"Activating account for address: {payment_address} with tier: {tier}")
                logging.info(f"Location for player with discord_id: {discord_id} added to player_location table.")
                
    except Exception as e:
        logging.error(f"An error occurred while activating the account: {str(e)}")

def process_notification(notification):
    # Process the wallet notification
    logging.info(f"Processing wallet notification: {notification}")
    # Add your logic here to handle the specific notification

def print_sys_argv():
    for arg in sys.argv:
        logging.info(f"Printing args {arg}")

if __name__ == "__main__":
    asyncio.run(main())