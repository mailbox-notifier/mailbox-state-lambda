"""
This module defines the MailboxStateMachine class to manage the state of a physical mailbox. It
interacts with AWS services, specifically DynamoDB for maintaining a counter of mailbox
open/close events and SNS for sending notifications based on the mailbox's state. The mailbox
can be in one of three states: OPEN, CLOSED, or AJAR, transitioning between these states based
on the received events.

The main function at the bottom of the module facilitates testing the MailboxStateMachine with a
series of predefined events and simulates a time delay between them.
"""
import os
import time

import boto3
from botocore.exceptions import ClientError


class MailboxStateMachine:
    """
     A state machine for managing the state of a mailbox.

     Attributes:
         state (str): The current state of the mailbox ('OPEN', 'CLOSED', 'AJAR').
         sns_client: The Boto3 SNS client for sending notifications.
         dynamodb: The Boto3 DynamoDB resource.
         table: The DynamoDB table for storing the event count.
         sns_arn (str): The ARN of the SNS topic for sending notifications.
         ajar_message_count (int): Counter for the number of messages sent in the AJAR state.

     Methods:
         handle_event: Process an incoming mailbox event ('open' or 'closed').
         increment_db_value: Increments the counter in DynamoDB for 'open' events.
         reset_db_value: Resets the counter in DynamoDB for 'closed' events.
         transition_to_open: Handles the transition to the OPEN state.
         transition_to_ajar: Handles the transition to the AJAR state.
         transition_to_closed: Handles the transition to the CLOSED state.
         get_db_value: Retrieves the current counter value from DynamoDB.
         send_sns_message: Sends a message to the configured SNS topic.
         handle_ajar_state: Manages the AJAR state, including sending messages based on
           an exponential backoff strategy.
     """

    def __init__(self, sns_arn, dynamodb_name):
        self.state = "CLOSED"
        self.sns_client = boto3.client('sns')
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(dynamodb_name)
        self.sns_arn = sns_arn
        self.ajar_message_count = 0

    def handle_event(self, event):
        """
        Processes an incoming event and updates the mailbox state accordingly.

        Args:
            event (str): The event type, either 'open' or 'closed'.
        """
        if event == "open":
            self.increment_db_value()
            if self.state == "CLOSED":
                self.transition_to_open()
            elif self.state == "OPEN":
                self.transition_to_ajar()
            elif self.state == "AJAR":
                self.handle_ajar_state()  # Handle AJAR state logic
        elif event == "closed":
            self.reset_db_value()
            self.transition_to_closed()

    def increment_db_value(self):
        """
        Increments the value associated with the 'open' key in the DynamoDB table.
        Handles and logs any potential errors in the update process.
        """
        try:
            self.table.update_item(
                Key={'id': 'open'},
                UpdateExpression='SET #val = if_not_exists(#val, :zero) + :inc',
                ExpressionAttributeNames={'#val': 'value'},
                ExpressionAttributeValues={':inc': 1, ':zero': 0}
            )
        except ClientError as e:
            print(f"Error updating DynamoDB: {e}")

    def reset_db_value(self):
        """
        Resets the value associated with the 'open' key in the DynamoDB table to 0.
        Handles and logs any potential errors in the reset process.
        """
        try:
            self.table.update_item(
                Key={'id': 'open'},
                UpdateExpression='SET #val = :zero',
                ExpressionAttributeNames={'#val': 'value'},
                ExpressionAttributeValues={':zero': 0}
            )
        except ClientError as e:
            print(f"Error resetting DynamoDB: {e}")


    def transition_to_open(self):
        """
        Transitions the state machine to the OPEN state and sends an SNS notification.
        """
        self.state = "OPEN"
        self.send_sns_message("Mailbox is now OPEN")

    def transition_to_ajar(self):
        """
        Transitions the state machine to the AJAR state and sends an SNS notification.
        """
        self.state = "AJAR"
        self.send_sns_message("Mailbox is AJAR")

    def transition_to_closed(self):
        """
        Transitions the state machine to the CLOSED state.
        Sends an SNS notification if the 'open' counter is greater than 0.
        """
        self.state = "CLOSED"
        if self.get_db_value() > 0:
            self.send_sns_message("Mailbox is now CLOSED")

    def get_db_value(self):
        """
        Retrieves the current value of the 'open' key from DynamoDB.

        Returns:
            int: The current value associated with the 'open' key.
        """
        try:
            response = self.table.get_item(Key={'id': 'open'})
            return int(response['Item'].get('value', 0))
        except ClientError as e:
            print(f"Error getting 'open' value from DynamoDB: {e}")
            return 0

    def send_sns_message(self, message):
        """
        Sends a notification message to the configured SNS topic.

        Args:
            message (str): The message to be sent.
        """
        try:
            self.sns_client.publish(
                TopicArn=self.sns_arn,
                Message=message,
            )
        except ClientError as e:
            print(f"Error sending SNS message: {e}")

    # Implement exponential backoff logic for AJAR state
    def handle_ajar_state(self):
        """
        Manages the AJAR state by sending SNS messages based on an exponential backoff strategy.
        Determines if a message should be sent based on the current count of 'open' events.
        """
        counter = self.get_db_value()
        # Assuming an exponential backoff strategy with a base of 2
        if counter >= 2 ** (self.ajar_message_count + 1):
            self.ajar_message_count += 1
            self.send_sns_message(f"Mailbox still AJAR, message count: {self.ajar_message_count}")


def main():
    """
    Main function for testing the MailboxStateMachine.

    Reads AWS configuration from environment variables, creates an instance of MailboxStateMachine,
    and processes a series of test events.
    """
    sns_arn = os.getenv('MAILBOX_SNS_ARN')
    dynamodb_name = os.getenv('MAILBOX_DYNAMODB_TABLE')

    if not sns_arn or not dynamodb_name:
        print("Error: SNS_ARN and DYNAMODB_TABLE environment variables are required.")
        return

    mailbox = MailboxStateMachine(sns_arn, dynamodb_name)

    # Example test events
    test_events = [
        "open", "open", "closed",
        "open", "open", "open", "closed",
        "open", "open", "open", "open", "open", "open", "open", "open", "open", "closed"
    ]
    for event in test_events:
        mailbox.handle_event(event)
        print(f"Handled event '{event}', current state: {mailbox.state}")
        time.sleep(30)  # Add a 30-second delay between events


if __name__ == "__main__":
    main()
