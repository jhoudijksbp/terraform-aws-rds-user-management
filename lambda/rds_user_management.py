import os
import argparse
import base64
import json
import logging
import time
import boto3
import sys
from aurora import Aurora
import urllib.request
from botocore.exceptions import ClientError
from secrets_manager import SecretsManagerSecret

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DEFAULT_SECRET_TYPE        = "RDS"
DEFAULT_MASTER_SECRET_TYPE = "MASTER_RDS"

def main(event, context):
    
    try:
        
        responseStatus = "SUCCESS"
        responseData   = {"Value":"", "Error":""}
        
        logger.info(f"RequestType: {event['RequestType']}")

        # Only send a response to Cloudformation when the RequestType is Update or Delete
        if event['RequestType'] == 'Delete':
            sendResponse(event, context, responseStatus, responseData)
            return

        logger.info(event)
        logger.info("Start managing RDS Aurora users")

        # initiate boto3 for SecretsManager and RDS
        client                 = boto3.client('secretsmanager')
        rdsb3                  = boto3.client('rds')
        secrets_manager        = SecretsManagerSecret(client)
    
        # Default master user secrets
        masterSecrets = client.list_secrets(Filters=[{"Key": "tag-value", "Values": [DEFAULT_MASTER_SECRET_TYPE]}])
    
        # Load classes
        db = Aurora()
        
        logger.info("Start retrieving all secrets from Secretsmanager")
        
        # Only select secrets with a specific tag-value
        responseCreds   = client.list_secrets(Filters=[{"Key": "tag-value", "Values": [DEFAULT_SECRET_TYPE]}])
        secretlistCreds = responseCreds['SecretList']
        
        logger.info("All secrets listed!")
        
        # Save all available secrets in a list.
        while "NextToken" in responseCreds:
            responseCreds   = client.list_secrets(NextToken=responseCreds['NextToken'])
            secretlistCreds = secretlistCreds + responseCreds['SecretList']
        
        # Loop over all secrets and try to manage al these secrets/users
        for secret in secretlistCreds:

            # Retrieve the secret value of the specific Secret.
            response             = client.get_secret_value(SecretId=secret['ARN'])
            db_secret            = json.loads(response['SecretString'])
            secrets_manager.name = response['Name']
            
            logger.info(f"secretvalue successfully loaded: {response['Name']}")
            
            # Retrieve the secret value of the privileges secret
            privName     = response['Name'].replace('db_user','db_user_privs',1)
            responsePriv = client.get_secret_value(SecretId=privName)
            db_privs    = json.loads(responsePriv['SecretString'])
            
            logger.info(f"secretvalue successfully loaded: {privName}")
            
            # Retrieve Master secet value
            master_secret_arn = None    
            for item in masterSecrets['SecretList']:
                for tag in item['Tags']:
                    if tag['Key'] == 'CL_IDENTIFIER' and tag['Value'] == db_secret['dbInstanceIdentifier']:
                        master_secret_arn = item['ARN']

            if master_secret_arn is None:
                raise Exception(f"Could not retrieve master secret value for: {db_secret['dbInstanceIdentifier']}")
            
            # Add privileges to the secret
            db_secret['privileges'] = db_privs['privileges']
            
            # Populate default IAM user which will be used by this Lambda
            master_iam_user = "rds_user_mgmt_lambda_iam_user"
            
            # Get a connection with the RDS instance
            conn = db.get_connection(endpoint   = db_secret['host'], 
                                     port       = db_secret['port'], 
                                     iam_user   = master_iam_user, 
                                     secretArn = master_secret_arn,
                                     rds        = rdsb3,
                                     rds_aurora = db)
            
            # If a drop attribtue is in the secret we will drop the user
            if "drop" in db_secret:
                db.rds_drop_user(connection=conn, username=db_secret['username'])
                logger.info(f"User: {db_secret['username']} dropped")
            
            # With this connection we can create the user if it not exists and see if the user has all the correct permissions.
            passwd = db.rds_manage_user(conn, db_secret)
            
            # Check if another password is generated and save it to the secret
            if db_secret['password'] != passwd:
                
                # Set password on IAM for IAM users
                if db_secret['authentication'] == "IAM":
                    passwd = 'IAM'
                
                logger.info('A new password is generated: We need to save a new version of the secret')
                db_secret['password'] = passwd
                db_secret.pop("privileges")
                secret = json.dumps(db_secret)
                
                # Save value in Secretsmanager
                secrets_manager.put_value(secret_value=secret)
                logger.info('Secret saved with new password!')
                
            # Close the database connection
            db.close_connection(conn) 
        
        # Send response to signed URL
        responseData['Value']="User management Lambda successfully executed!"
        sendResponse(event, context, responseStatus, responseData)
        
        return {
            'statusCode': 200,
            'body': json.dumps('Lambda successfully executed!')
        }

    except BaseException as err:
        logger.error(f"Unexpected {err=}, {type(err)=}")
        
        # Send Response to seigned
        responseData['Error'] = str(err)
        responseData['Value'] = "User management Lambda FAILED!"
        responseStatus        = "FAILED"
        
        sendResponse(event, context, responseStatus, responseData)
        
        return {
            'statusCode': 500,
            'body': json.dumps('Error in Lambda please check logs')
        }

# Send the response to a signed url endpoint.
def sendResponse(event, context, responseStatus, responseData):
  
  reason = "See the details in CloudWatch Log Stream: " + context.log_stream_name
  if responseStatus == "FAILED":
      reason = f"Error: {responseData['Error']} see more info in Cloudwatch: {context.log_stream_name}"
  
  responseBody = {
    "Status": responseStatus,
    "Reason": reason,
    "PhysicalResourceId": context.log_stream_name,
    "StackId": event['StackId'],
    "RequestId": event['RequestId'],
    "LogicalResourceId": event['LogicalResourceId'],
    "Data": responseData
  }
  
  logger.info(responseBody)
  logger.info('ResponseURL: {}'.format(event['ResponseURL']))
  
  data = json.dumps(responseBody).encode('utf-8')
  
  req  = urllib.request.Request(event['ResponseURL'], data, headers={'Content-Length': len(data), 'Content-Type': ''})
  req.get_method = lambda: 'PUT'
  response = urllib.request.urlopen(req) 
  logger.info(f'response.status: {response.status}, ' + f'response.reason: {response.reason}')
 