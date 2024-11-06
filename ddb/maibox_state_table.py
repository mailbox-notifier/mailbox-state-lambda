"""
This module provides functionality to interact with AWS DynamoDB. It includes
capabilities to create a new DynamoDB table and initialize a key/value pair within it.
Specifically, it creates a table named 'mailbox-state-key' and initializes a key 'open'
with an unsigned integer value set to 0.

Requirements:
- AWS SDK for Python (Boto3)
- Properly configured AWS credentials
"""

import datetime

import boto3
import pytz  # For handling timezone
from botocore.exceptions import ClientError


def create_dynamodb_table(table_name):
    """
    Creates a DynamoDB table with the specified table name.

    The table is created with a single primary key attribute 'id' of type String.
    It sets the provisioned read and write capacity units to 1.

    Args:
        table_name (str): The name of the table to create.

    Prints the status of table creation or an error message if the table already exists
    or if there is an exception during table creation.
    """
    dynamodb = boto3.client('dynamodb')

    try:
        response = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'id',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'id',
                    'AttributeType': 'S'
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 1,
                'WriteCapacityUnits': 1
            }
        )
        print(f"Table creation initiated, status: {response['TableDescription']['TableStatus']}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"Table {table_name} already exists.")
        else:
            print(f"Error creating table: {e}")


def create_initial_key_value(table_name, key_name, initial_value):
    """
    Creates an initial key/value pair in the specified DynamoDB table.

    Args:
        table_name (str): The name of the DynamoDB table to update.
        key_name (str): The key of the item to create.
        initial_value (int): The initial value to set for the key.

    Adds a new item with the specified key and value to the table.
    Prints a message indicating the action taken or an error if it occurs.
    """
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)

    # Get current time in UTC and convert it to US Central Time (UTC-6)
    utc_now = datetime.datetime.now(pytz.utc)
    central_time = utc_now.astimezone(pytz.timezone('US/Central'))

    try:
        response = table.put_item(
            Item={
                'id': key_name,
                'value': initial_value,
                'timestamp': central_time.strftime('%Y%m%d%H%M%S')  # Formatting the timestamp
            }
        )
        print(f"Key '{key_name}' created with initial value {initial_value} and timestamp {central_time}")
    except ClientError as e:
        print(f"Error putting item: {e}")


def wait_for_table_creation(table_name):
    """
    Waits for the specified DynamoDB table to become active.

    Args:
        table_name (str): The name of the DynamoDB table to check.
    """
    dynamodb = boto3.client('dynamodb')
    waiter = dynamodb.get_waiter('table_exists')
    try:
        waiter.wait(TableName=table_name)
    except ClientError as e:
        print(f"Error waiting for table creation: {e}")


def main():
    """
    Main function to execute table creation and item insertion.

    It defines the table name and key/value pair details, then calls functions
    to create the DynamoDB table and insert the initial key/value pair.
    """
    table_name = 'mailbox-state-v2'
    key_name = 'open'
    initial_value = 0

    print("Creating DynamoDB table")
    create_dynamodb_table(table_name)

    # Wait for the table to become active
    print("Waiting for table to become active...")
    wait_for_table_creation(table_name)

    print("Creating initial key/value")
    create_initial_key_value(table_name, key_name, initial_value)
    print("Done")


if __name__ == '__main__':
    main()
