"""
AWS Lambda function to manage the state of a physical mailbox.

This module defines a Lambda handler that responds to HTTP requests indicating the
opening or closing of a mailbox. It updates the mailbox state using the MailboxStateMachine
class and interacts with AWS services such as DynamoDB and SNS for state management and
notifications. The function expects to be triggered by AWS API Gateway with paths
corresponding to mailbox events.
"""

import os

from mailbox_state_machine import MailboxStateMachine

ERROR_MSG_DOOR_KEY_MISSING = 'MBS001 - Ignoring event as "door" key is missing.'
ERROR_MSG_ENV_VARS_MISSING = "MBS002 - SNS_ARN and DYNAMODB_TABLE environment variables are required."

def handler(event, context):
    print(f"event:\r{event}")

    if 'door' not in event:
        raise Exception(ERROR_MSG_DOOR_KEY_MISSING)

    # Process the event if water_level exists
    mailbox_status = event['door']

    sns_arn = os.getenv('MAILBOX_SNS_ARN')
    dynamodb_name = os.getenv('MAILBOX_DYNAMODB_TABLE')

    if not sns_arn or not dynamodb_name:
        raise Exception(ERROR_MSG_ENV_VARS_MISSING)

    mailbox = MailboxStateMachine(sns_arn, dynamodb_name)

    mailbox.handle_event(mailbox_status)

    print(f"Event:'{mailbox_status}', State: {mailbox.state}, DB: {mailbox.get_db_value()}")
