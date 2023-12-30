Please write a Python state machine with the following characteristics:

- The machine will describe the states of a physical mailbox door
- The machine will receive events and send SNS messages
- The object be initialized with two pieces of info: an SNS arn and a DynamoDB name
- It will be receiving only two possible events: "open" and "closed"
- There are three possible states: "OPEN", "CLOSED" and "AJAR"
- A counter of received events is saved to DynamoDB
- Reception of events is reflected in a DynamoDB counter called "open"
- Every time an "open" event is received, a DynamoDB "open" entry counter is incremented by one
- Every time a "closed" event is received, the DynamicDB "open" entry counter is reset to 0
- If the DynamoDB "open" entry is not there, it is created.
- The beginning state is CLOSED
- Transition from CLOSED to OPEN happens when the first "open" event is received
- In OPEN state, send an SNS message on entry to the state
- Transition from OPEN to AJAR happens when a second "open" event is received
- In AJAR state, send an SNS message on entry to the state
- In AJAR state, using the DynamoDB counter as a guide, implement an exponential backoff strategy for sending messages
  assuming the continued reception of "open" events at 10 minute intervals
- In AJAR state, in calculating the backoff timer, do not sleep; use the event counter to determine when to send a
  message
- Transition from AJAR to CLOSED when a "closed" event is received
- Transition from OPEN to CLOSED when a "closed" event is received
- In CLOSED state, send a SNS message except when the DynamoDB "open" enter counter is already 0 



