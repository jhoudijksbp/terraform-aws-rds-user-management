import os
import argparse
import base64
import json
import logging
import time
import boto3
import sys
from aurora import Aurora
from botocore.exceptions import ClientError
from secrets_manager import SecretsManagerSecret

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DEFAULT_SECRET_TYPE = "RDS"

def main(event, context):
    
    try:
        
        logger.info("Start managing RDS Aurora users")
        
        # Environment variables
        master_username = os.environ['MASTER_USERNAME']
        master_secret   = os.environ['SECRET_NAME'] 

        # initiate boto3 for SecretsManager and RDS
        client                 = boto3.client('secretsmanager')
        rdsb3                  = boto3.client('rds')
        secrets_manager        = SecretsManagerSecret(client)
    
        # Load classes
        db = Aurora()
        
        # Only select secrets with a specific tag-value
        response = client.list_secrets(Filters=[{"Key": "tag-value", "Values": [DEFAULT_SECRET_TYPE]}])
        secretlist = response['SecretList']
        
        logger.info("All secrets listed!")
        
        # Save all available secrets in a list.
        while "NextToken" in response:
            response = client.list_secrets(NextToken=response['NextToken'])
            secretlist = secretlist + response['SecretList']
        
        # Loop over all secrets and try to manage al these secrets/users
        for secret in secretlist:
            
            try:

                # Retrieve the secret value of the specific Secret.
                response             = client.get_secret_value(SecretId=secret['ARN'])
                db_secret            = json.loads(response['SecretString'])
                secrets_manager.name = response['Name']
                
                logger.info(f"secret value loaded for: {db_secret['username']}")
    
                # Populate default IAM user which will be used by this Lambda
                master_iam_user = (f"{master_username}_iam")
    
                # Get a connection with the RDS instance
                conn = db.get_connection(endpoint=db_secret['host'], 
                                         port=db_secret['port'], 
                                         iam_user=master_iam_user, 
                                         user=master_username, 
                                         rds=rdsb3,
                                         rds_aurora=db)
                
                # With this connection we can create the user if it not exists and see if the user has all the correct permissions.
                passwd = db.rds_manage_user(conn, db_secret)
                
                # Check if another password is generated and save it to the secret
                if db_secret['password'] != passwd:
                    
                    # Set password on IAM for IAM users
                    if db_secret['authentication'] == "IAM":
                        passwd = 'IAM'
                    
                    logger.info('A new password is generated: We need to save a new version of the secret')
                    db_secret['password'] = passwd
                    secret                = json.dumps(db_secret)
                    
                    # Save value in Secretsmanager
                    secrets_manager.put_value(secret_value=secret)
                    logger.info('Secret saved with new password!')
                    
                # Close the database connection
                db.close_connection(conn)

            except BaseException as err:
                logger.error(f"Error managing user: {db_secret['username']}. Error: {err}")
        
        return {
            'statusCode': 200,
            'body': json.dumps('Lambda successfully executed!')
        }

    except BaseException as err:
        logger.error(f"Unexpected {err=}, {type(err)=}")