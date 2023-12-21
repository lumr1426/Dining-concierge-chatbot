import json
import os
import re
import botocore.exceptions
import logging
import boto3

from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from botocore.exceptions import ClientError, WaiterError


REGION = 'us-east-1'
HOST = 'OPENSEARCH_HOST_URL'
INDEX = 'restaurants'


def lambda_handler(event, context):
    print('Received event: ' + json.dumps(event))
    
    #============ Receiving query from SQS ========================
    
    # Create an SQS client
    sqs = boto3.client('sqs')

    # Specify the URL of the SQS queue
    queue_url = 'QUEUE_URL'

    # Receive message(s) from the queue
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,  
        MessageAttributeNames=['All'],  # Include message attributes
        WaitTimeSeconds=20  # Adjust to control how long Lambda waits for a message
    )

    # formatting to a valid json file
    raw_body = response['Messages'][0]['Body']
    message_receipt_handle = response['Messages'][0]['ReceiptHandle']
    raw_body_double_quote = raw_body.replace('\'', '"')
    queue_data = json.loads(raw_body_double_quote)
    
    # Delete the message
    sqs.delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=message_receipt_handle
    )
    
    # Getting attributes from the SQS queue
    cuisine = queue_data["cuisine"]["originalValue"]
    num_of_people = queue_data["number_people"]["originalValue"]
    dining_time = queue_data['time']['resolutions'][0]['value']
    email = queue_data['phone']['resolutions'][0]['value']
    location = queue_data['city']['originalValue']
    date = queue_data['date']['originalValue']

    #============ Searching through OpenSearch ========================
    
    # query result got from opensearch
    results = query(cuisine)
    
    #============ Searching more on DynamoDB & Creating SES message ========================
    
    # searching dynamodb using info from opensearch
    # result in form {"restaurant_id": aaa, "cuisine": bbb}
    ses_message = f'Hello! Here are my {cuisine} restaurant suggestions for {num_of_people} people, for {date} at {dining_time}: '
    
    # Getting restaurant info from dynamodb
    restaurant_count = 0
    
    for result in results:
        restaurant_id = result['restaurant_id']
        db_info = lookup_data({'id': restaurant_id})
        restaurant_name = db_info["name"]
        restaurant_address = db_info['location']["address1"]
        restaurant_count+=1
        recommend_message = f'{restaurant_count}. {restaurant_name}, located at {restaurant_address} '
        ses_message+=recommend_message
    
    ses_message = ses_message[:-2]+'. Enjoy your meal!'

    #============ Sending email with SES ====================
    
    ses_client = boto3.client('ses', region_name=REGION)
    
    ses_mail_sender = SesMailSender(ses_client)
    
    sender_email = 'SENDER_EMAIL'
    receiver_email = [email]
    dest = SesDestination(receiver_email)
    subject_name = 'Restaurant recommendations: Chatbot'
    html_content = f"<p>{ses_message}</p>"
    ses_mail_sender.send_email(source=sender_email, destination=dest, text=ses_message, subject=subject_name, html=html_content)

    #============ Return status code ========================

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': '*',
        },
        'body': json.dumps({'results': 'success'})
    }
    
    # ==================== END ===============================

# Function for looking up dynamodb
def lookup_data(key, db=None, table='yelp-restaurants'):
    if not db:
        db = boto3.resource('dynamodb')
    table = db.Table(table)
    try:
        response = table.get_item(Key=key)
    except ClientError as e:
        print('Error', e.response['Error']['Message'])
    else:
        print(response['Item'])
        return response['Item']
        

def query(term):
    q = {'size': 3, 'query': {'function_score': {
                'query': {'multi_match': {'query': term}},
                'random_score': {},
            }
        }
    }

    client = OpenSearch(hosts=[{
        'host': HOST,
        'port': 443
    }],
                        http_auth=get_awsauth(REGION, 'es'),
                        use_ssl=True,
                        verify_certs=True,
                        connection_class=RequestsHttpConnection)

    res = client.search(index=INDEX, body=q)
    print(res)

    hits = res['hits']['hits']
    results = []
    for hit in hits:
        results.append(hit['_source'])

    return results


def get_awsauth(region, service):
    cred = boto3.Session().get_credentials()
    return AWS4Auth(cred.access_key,
                    cred.secret_key,
                    region,
                    service,
                    session_token=cred.token)

class SesMailSender:
    """Encapsulates functions to send emails with Amazon SES."""
    def __init__(self, ses_client):
        """
        :param ses_client: A Boto3 Amazon SES client.
        """
        self.ses_client = ses_client
# snippet-end:[python.example_code.ses.SesMailSender]

# snippet-start:[python.example_code.ses.SendEmail]
    def send_email(self, source, destination, subject, text, html, reply_tos=None):
        """
        Sends an email.

        Note: If your account is in the Amazon SES  sandbox, the source and
        destination email accounts must both be verified.

        :param source: The source email account.
        :param destination: The destination email account.
        :param subject: The subject of the email.
        :param text: The plain text version of the body of the email.
        :param html: The HTML version of the body of the email.
        :param reply_tos: Email accounts that will receive a reply if the recipient
                          replies to the message.
        :return: The ID of the message, assigned by Amazon SES.
        """
        send_args = {
            'Source': source,
            'Destination': destination.to_service_format(),
            'Message': {
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': text}, 'Html': {'Data': html}}}}
        if reply_tos is not None:
            send_args['ReplyToAddresses'] = reply_tos
        try:
            response = self.ses_client.send_email(**send_args)
            message_id = response['MessageId']
            # logger.info(
            #     "Sent mail %s from %s to %s.", message_id, source, destination.tos)
        except ClientError:
            # logger.exception(
            #     "Couldn't send mail from %s to %s.", source, destination.tos)
            raise
        else:
            return message_id
            
class SesDestination:
    """Contains data about an email destination."""
    def __init__(self, tos, ccs=None, bccs=None):
        """
        :param tos: The list of recipients on the 'To:' line.
        :param ccs: The list of recipients on the 'CC:' line.
        :param bccs: The list of recipients on the 'BCC:' line.
        """
        self.tos = tos
        self.ccs = ccs
        self.bccs = bccs

    def to_service_format(self):
        """
        :return: The destination data in the format expected by Amazon SES.
        """
        svc_format = {'ToAddresses': self.tos}
        if self.ccs is not None:
            svc_format['CcAddresses'] = self.ccs
        if self.bccs is not None:
            svc_format['BccAddresses'] = self.bccs
        return svc_format
