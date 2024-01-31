"""
This module defines the MailboxStateMachine class to manage the state of a physical mailbox. It
interacts with AWS services, specifically DynamoDB for maintaining a counter of mailbox
open/close events and SNS for sending notifications based on the mailbox's state. The mailbox
can be in one of three states: OPEN, CLOSED, or AJAR, transitioning between these states based
on the received events.

The main function at the bottom of the module facilitates testing the MailboxStateMachine with a
series of predefined events and simulates a time delay between them.
"""
import datetime
import os
import time

import boto3
import pytz  # For handling timezone
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
        self.sns_client = boto3.client('sns')
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(dynamodb_name)
        self.state = self.get_current_state()
        self.sns_arn = sns_arn
        self.ajar_message_count = 1

    def get_current_state(self):
        """
        Retrieves the current state of the mailbox from DynamoDB.

        Returns:
            str: The current state of the mailbox ('OPEN', 'CLOSED', 'AJAR').
        """
        db_value = self.get_db_value()

        if db_value == 0:
            state_value = "CLOSED"
        elif db_value == 1:
            state_value = "OPEN"
        else:
            state_value = "AJAR"

        return state_value

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
            self.transition_to_closed()
            self.reset_db_value()  # Reset the counter in DynamoDB for closed events

    def increment_db_value(self):
        """
        Increments the value associated with the 'open' key in the DynamoDB table and adds a timestamp.
        """
        current_time = self.get_current_timestamp()
        try:
            self.table.update_item(
                Key={'id': 'open'},
                UpdateExpression='SET #val = if_not_exists(#val, :zero) + :inc, #ts = :time',
                ExpressionAttributeNames={'#val': 'value', '#ts': 'timestamp'},
                ExpressionAttributeValues={':inc': 1, ':zero': 0, ':time': current_time}
            )
        except ClientError as e:
            print(f"Error updating DynamoDB: {e}")

    def reset_db_value(self):
        """
        Resets the value associated with the 'open' key in the DynamoDB table to 0 and adds a timestamp.
        """
        current_time = self.get_current_timestamp()
        try:
            self.table.update_item(
                Key={'id': 'open'},
                UpdateExpression='SET #val = :zero, #ts = :time',
                ExpressionAttributeNames={'#val': 'value', '#ts': 'timestamp'},
                ExpressionAttributeValues={':zero': 0, ':time': current_time}
            )
        except ClientError as e:
            print(f"Error resetting DynamoDB: {e}")

    @staticmethod
    def get_current_timestamp():
        """
        Returns the current timestamp in a formatted string.
        """
        utc_now = datetime.datetime.now(pytz.utc)
        central_time = utc_now.astimezone(pytz.timezone('US/Central'))
        return central_time.strftime('%Y%m%d%H%M%S')

    def transition_to_open(self):
        """
        Transitions the state machine to the OPEN state and sends an SNS notification.
        """
        self.state = "OPEN"
        self.send_sns_message("Mailbox OPEN")

    def transition_to_ajar(self):
        """
        Transitions the state machine to the AJAR state and sends an SNS notification.
        """
        self.state = "AJAR"
        self.send_sns_message("Mailbox AJAR")

    def transition_to_closed(self):
        """
        Transitions the state machine to the CLOSED state.
        Sends an SNS notification if the 'open' counter is greater than 0.
        """
        self.state = "CLOSED"
        if self.get_db_value() > 1:
            self.send_sns_message("Mailbox CLOSED")

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

    def handle_ajar_state(self):
        """
        Manages the AJAR state by sending SNS messages based on an exponential backoff strategy.
        Determines if a message should be sent based on the current count of 'open' events.
        The message is sent when the counter is a power of 2.

        Explanation:
         - The condition counter & (counter - 1) checks if counter is a power of 2. This works
           because powers of 2 in binary form have a single '1' followed by '0's, and
           subtracting 1 from such a number results in a binary number with '1's in all the
           places where the original number had '0's. The bitwise AND of such numbers is 0.
         - The check counter > 0 ensures that the condition does not send a message when
           the counter is 0.
         - This logic will trigger a message when the counter reaches 1, 2, 4, 8, 16, and so on.

        Progression Summary:
         - At 20 minutes, the counter reaches 2, and a message is sent.
         - At 40 minutes, the counter reaches 4, and another message is sent.
         - At 80 minutes, the counter reaches 8, and another message is sent.
         - At 160 minutes, the counter reaches 16, and another message is sent.
         - At 320 minutes, the counter reaches 32, and another message is sent.
         - At 640 minutes, the counter reaches 64, and another message is sent.
         - At 1280 minutes, the counter reaches 128, and another message is sent.
        """
        counter = self.get_db_value()

        # Check if the counter is a power of 2
        if counter & (counter - 1) == 0 and counter > 0:
            self.send_sns_message(f"Mailbox still AJAR, event count: {counter}")


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
        # OPEN, but no CLOSED message should be received
        "open", "closed",
        # OPEN, AJAR and CLOSED messages should be received
        "open", "open", "closed",
        # OPEN, 1 AJAR, and CLOSED messages should be received
        "open", "open", "open", "closed",
        # OPEN, 2 AJAR, and CLOSED messages should be received
        "open", "open", "open", "open", "closed",
    ]

    for event in test_events:
        mailbox.handle_event(event)
        print(f"Event:'{event}', State: {mailbox.state}, DB: {mailbox.get_db_value()}")
        time.sleep(10)  # Add a 10-second delay between events

    mailbox.reset_db_value()


if __name__ == "__main__":
    main()
