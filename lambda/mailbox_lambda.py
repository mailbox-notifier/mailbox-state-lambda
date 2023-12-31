"""
AWS Lambda function to manage the state of a physical mailbox.

This module defines a Lambda handler that responds to HTTP requests indicating the
opening or closing of a mailbox. It updates the mailbox state using the MailboxStateMachine
class and interacts with AWS services such as DynamoDB and SNS for state management and
notifications. The function expects to be triggered by AWS API Gateway with paths
corresponding to mailbox events.
"""

import json
import os

from mailbox_state_machine import MailboxStateMachine


def http_message(code, msg):
    """
    Constructs a formatted HTTP response message.

    Args:
        code (int): HTTP status code.
        msg (str): Response message body.

    Returns:
        dict: A dictionary representing the HTTP response.
    """
    return {
        'statusCode': code,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS'
        },
        'body': json.dumps(msg)
    }


def handler(event, context):
    """
    Handles incoming HTTP requests to manage mailbox state.

    This function is triggered by an HTTP request through AWS API Gateway. It extracts
    the mailbox state (open/closed) from the request path, updates the mailbox state using
    the MailboxStateMachine class, and returns an HTTP response.

    Args:
        event (dict): The event object containing request details.
        context (LambdaContext): Provides runtime information about the Lambda function execution.

    Returns:
        dict: The HTTP response object.
    """
    print(f"event:\n{event}")
    print(f"context:\n{context}")

    if 'open' in event['rawPath']:
        mailbox_status = 'open'
    elif 'closed' in event['rawPath']:
        mailbox_status = 'closed'
    else:
        print("Error: Invalid mailbox status.")
        return http_message(400, 'Invalid mailbox status.')

    sns_arn = os.getenv('MAILBOX_SNS_ARN')
    dynamodb_name = os.getenv('MAILBOX_DYNAMODB_TABLE')

    if not sns_arn or not dynamodb_name:
        print("Error: SNS_ARN and DYNAMODB_TABLE environment variables are required.")
        return http_message(500, 'SNS_ARN and DYNAMODB_TABLE environment variables are required.')

    mailbox = MailboxStateMachine(sns_arn, dynamodb_name)

    mailbox.handle_event(mailbox_status)
    print(f"Event:'{mailbox_status}', State: {mailbox.state}, DB: {mailbox.get_db_value()}")

    return http_message(200, 'Success')
