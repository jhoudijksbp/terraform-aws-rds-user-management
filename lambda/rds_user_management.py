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

logger = logging.getLogger(__name__)
DEFAULT_SECRET_TYPE = "RDS"

def main(event, context):
    
    try:
        
        # Environment variables
        master_username = os.environ['MASTER_USERNAME']
        master_secret   = os.environ['SECRET_NAME'] 

        # initiate boto3 for SecretsManager and RDS
        client = boto3.client('secretsmanager')
        rdsb3  = boto3.client('rds')
        
        # Load classes
        db = Aurora()
        
        # Only select secrets with a specific tag-value
        response = client.list_secrets(Filters=[{"Key": "tag-value", "Values": [DEFAULT_SECRET_TYPE]}])
        secretlist = response['SecretList']
        
        # Save all available secrets in a list.
        while "NextToken" in response:
            response = client.list_secrets(NextToken=response['NextToken'])
            secretlist = secretlist + response['SecretList']
        
        # Loop over all secrets and try to manage al these secrets/users
        for secret in secretlist:

            # Retrieve the secret value of the specific Secret.
            response  = client.get_secret_value(SecretId=secret['ARN'])
            db_secret = json.loads(response['SecretString'])

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
            resp = db.rds_manage_user(conn, db_secret)
            
            # Close the database connection
            db.close_connection(conn)
        
        return {
            'statusCode': 200,
            'body': json.dumps('Hello from Lambda!')
        }

    except BaseException as err:
        print(f"Unexpected {err=}, {type(err)=}")