import json

import boto3

# LF0 should receive input from frontend S3 user's input
# and send requests to Amazon Lex Chatbot
# and forward the response from Amazon Lex Chatbot back to users

# global data structures
globalUserID = {"current": 100}


# make request to Amazon Lex
def request_to_lex(id, input):
    client = boto3.client('lex-runtime', region_name='us-east-1', aws_access_key_id='ACCESS_KEY', aws_secret_access_key= 'SECRET_ACCESS_KEY')
    response = client.post_text(
        botName='DiningConcierge',
        botAlias='testAlias',
        userId=id,
        inputText=input,
    )
    return response


def lambda_handler(event, context):
    # check if a userID is assigned
    currentUserID = str(globalUserID["current"])
    if 'id' not in event['messages'][0]['unstructured'].keys():
        globalUserID["current"] += 1
    else:
        currentUserID = event['messages'][0]['unstructured']['id']
    # send request to Amazon Lex Chatbot
    # and wait for resposne
    message = event['messages'][0]['unstructured']['text']
    lexResponse = request_to_lex(currentUserID, message)
    
    response = {
        "status_code": 200,
        "messages": [
            {
              "type": "unstructured",
              "unstructured": {
                "id": currentUserID,
                "text": "you are user#" + currentUserID + ": " + lexResponse['message'],
                }
            }
        ]
    }

    return response
