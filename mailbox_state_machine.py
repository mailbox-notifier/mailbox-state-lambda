import boto3
from botocore.exceptions import ClientError


class MailboxStateMachine:
    def __init__(self, sns_arn, dynamodb_name):
        self.state = "CLOSED"
        self.sns_client = boto3.client('sns')
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(dynamodb_name)
        self.sns_arn = sns_arn

    def handle_event(self, event):
        if event == "open":
            self.increment_counter()
            if self.state == "CLOSED":
                self.transition_to_open()
            elif self.state == "OPEN":
                self.transition_to_ajar()
            # AJAR state does not transition on "open"
        elif event == "closed":
            self.reset_counter()
            self.transition_to_closed()

    def increment_counter(self):
        try:
            self.table.update_item(
                Key={'id': 'open'},
                UpdateExpression='ADD counter :inc',
                ExpressionAttributeValues={':inc': 1},
                ReturnValues="UPDATED_NEW"
            )
        except ClientError as e:
            print(f"Error updating DynamoDB: {e}")

    def reset_counter(self):
        try:
            self.table.put_item(
                Item={'id': 'open', 'counter': 0}
            )
        except ClientError as e:
            print(f"Error resetting DynamoDB: {e}")

    def transition_to_open(self):
        self.state = "OPEN"
        self.send_sns_message("Mailbox is now OPEN")

    def transition_to_ajar(self):
        self.state = "AJAR"
        self.send_sns_message("Mailbox is AJAR")

    def transition_to_closed(self):
        self.state = "CLOSED"
        if self.get_counter() > 0:
            self.send_sns_message("Mailbox is now CLOSED")

    def get_counter(self):
        try:
            response = self.table.get_item(Key={'id': 'open'})
            return response['Item'].get('counter', 0)
        except ClientError as e:
            print(f"Error getting counter from DynamoDB: {e}")
            return 0

    def send_sns_message(self, message):
        try:
            self.sns_client.publish(
                TopicArn=self.sns_arn,
                Message=message,
            )
        except ClientError as e:
            print(f"Error sending SNS message: {e}")

    # Implement exponential backoff logic for AJAR state
    def handle_ajar_state(self):
        if self.state != "AJAR":
            return

        counter = self.get_counter()
        # Assuming an exponential backoff strategy with a base of 2
        if counter >= 2 ** (self.ajar_message_count + 1):
            self.ajar_message_count += 1
            self.send_sns_message(f"Mailbox still AJAR, message count: {self.ajar_message_count}")


# Example Usage
mailbox = MailboxStateMachine("sns_arn_here", "dynamodb_name_here")
mailbox.handle_event("open")
mailbox.handle_event("open")
mailbox.handle_event("closed")
