import json

import boto3

from datetime import datetime

def check_input(information):
    # check number of people is not negative
    if len(information['number_people']['resolutions']) == 0 or int(information['number_people']['resolutions'][0]['value']) <= 0:
        return False
    # check date time
    if len(information['date']['resolutions']) == 0:
        return False
    else:
        now = datetime.now()
        input_date = datetime.strptime(information['date']['resolutions'][0]['value'], "%Y-%m-%d").date()
        current_date = datetime.strptime(now.strftime("%Y-%m-%d"), "%Y-%m-%d").date()
        if input_date < current_date:
            return False
        elif input_date == current_date:
            # check if time given is not in the past
            if len(information['time']['resolutions']) == 0:
                return False
            else:
                now = datetime.now()
                input_time = datetime.strptime(information['time']['resolutions'][0]['value'], "%H:%M").time()
                current_time = datetime.strptime(now.strftime("%H:%M"), "%H:%M").time()
                input_hour, input_min, _ = str(input_time).split(":")
                curret_hour, current_min, _ = str(current_time).split(":")
                #print(input_hour, input_min, curret_hour, current_min)
                if (int(input_hour) + 4) % 24 < int(curret_hour):
                    return False
                if (int(input_hour) + 4) % 24 == int(curret_hour) and int(input_min) < int(current_min):
                    return False
        else:
            # check if time given is not in the past
            if len(information['time']['resolutions']) == 0:
                return False
    # check if a valid phone number is given
    if len(information['phone']['resolutions']) == 0:
        return False
    # otherwise, it is ok
    return True


def lambda_handler(event, context):
    response = {
        "dialogAction": {
            "type": "Close",
            "fulfillmentState": "Fulfilled",
            "message": {
                  "contentType": "PlainText",
                  "content": "Sorry we are experiencing some problems. Please try again later."
            },
        }
    }
    # Error Handling:
    if not check_input(event['currentIntent']['slotDetails']):
        response['dialogAction']['fulfillmentState'] = "Failed"
        response['dialogAction']['message']['content'] = "The time you entered or the number of people you told us is wrong. Please try again."
        return response
    # push the information to an SQS queue (Q1)
    sqs = boto3.client('sqs', aws_access_key_id='ACCESS_KEY', aws_secret_access_key= 'SECRET_ACCESS_KEY')
    sqs_response = sqs.send_message(
        QueueUrl='QUEUE_URL',
        MessageBody=json.dumps(event['currentIntent']['slotDetails']),
        MessageGroupId='normal'
    )
    # Reponse back to client
    if 'ResponseMetadata' in sqs_response and 'HTTPStatusCode' in sqs_response['ResponseMetadata']:
        if sqs_response['ResponseMetadata']['HTTPStatusCode'] == 200:
            response['dialogAction']['message']['content'] = "You are all set! You will receive a message later on your phone."
    return response
