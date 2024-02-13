"""
This module provides functionality to interact with AWS DynamoDB. It includes
capabilities to create a new DynamoDB table named 'mailbox-state' and initializes
a key 'closed' with a string value.

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
    Creates a DynamoDB table with the specified table name, using 'mailbox_status_value'
    as the primary key and 'mailbox_status_timestamp' as the sort key.

    Args:
        table_name (str): The name of the table to create.
    """
    dynamodb = boto3.client('dynamodb')

    try:
        response = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'mailbox_status_value',
                    'KeyType': 'HASH'  # Primary key
                },
                {
                    'AttributeName': 'mailbox_status_timestamp',
                    'KeyType': 'RANGE'  # Sort key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'mailbox_status_value',
                    'AttributeType': 'S'  # String
                },
                {
                    'AttributeName': 'mailbox_status_timestamp',
                    'AttributeType': 'S'  # String
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


def create_initial_key_value(table_name, initial_value):
    """
    Creates an initial item in the specified DynamoDB table with 'mailbox_status_value'
    as the key and 'mailbox_status_timestamp' for the record timestamp.

    Args:
        table_name (str): The name of the DynamoDB table to update.
        initial_value (str): The initial value for 'mailbox_status_value', defaults to 'closed'.
    """
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)

    # Get current time in UTC and convert it to US Central Time (UTC-6)
    utc_now = datetime.datetime.now(pytz.utc)
    central_time = utc_now.astimezone(pytz.timezone('US/Central'))

    try:
        response = table.put_item(
            Item={
                'mailbox_status_value': initial_value,
                'mailbox_status_timestamp': central_time.strftime('%Y-%m-%dT%H:%M:%S')  # ISO 8601 format
            }
        )
        print(f"Initial item created with value '{initial_value}' and timestamp {central_time.isoformat()}")
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

    It defines the table name and initializes an item with a value and timestamp.
    """
    table_name = 'mailbox-state'
    initial_value = 'closed'  # Initial value is now a string representing the status

    print("Creating DynamoDB table")
    create_dynamodb_table(table_name)

    # Wait for the table to become active
    print("Waiting for table to become active...")
    wait_for_table_creation(table_name)

    print("Creating initial item")
    create_initial_key_value(table_name, initial_value)
    print("Done")

if __name__ == '__main__':
    main()
