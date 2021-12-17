import argparse
import base64
import json
import logging
import time
import boto3
from mysql import connector
from mysql.connector import Error
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
DEFAULT_SECRET_TYPE = "RDS"

def main(event, context):
    
    try:

        # TODO: 
        # - Make Secretsmanager class
        # iam_user='ccv_admin_iam',  should by fully configurable
        # user="ccv_admin" should be fully configurable
        
        # initiate boto3 for SecretsManager and RDS
        client = boto3.client('secretsmanager')
        rdsb3  = boto3.client('rds')
        
        # Load classes
        db            = Aurora()
        
        # Only select secrets with a specific tag-value
        response = client.list_secrets(Filters=[{"Key": "tag-value", "Values": [DEFAULT_SECRET_TYPE]}])
        secretlist = response['SecretList']
        
        # Save all available secrets in a list.
        while "NextToken" in response:
            response = client.list_secrets(NextToken=response['NextToken'])
            secretlist = secretlist + response['SecretList']
    
        # whats next:
        # 1: Create a loop to go trough all secrets. 
        # 2: Connnect to endpoint
        #    2.1: First try to connect with default IAM account. If this works proceed to step 3
        #    2.2: Try to load secret for master account. 
        #    2.3: Connect with this master account.
        #    2.4: Create default IAM account with permissions te create users. 
        #    2.5: Connect again with this IAM account
        # 3: Check if the account exists, if not create this account. 
        # 4: Next step is to be able to specify permissions on global and database level. We will need to think about how to configure this
        
        # Loop over all secrets and try to manage al these secrets/users
        count=0
        for secret in secretlist:
            count +=1

            # Retrieve the secret value of the specific Secret.
            response  = client.get_secret_value(SecretId=secret['ARN'])
            db_secret = json.loads(response['SecretString'])
            
            print(db_secret['host'])

            # Get a connection with the RDS instance
            conn = db.get_connection(endpoint=db_secret['host'], 
                                     port=db_secret['port'], 
                                     iam_user="ccv_admin_iam", 
                                     user="ccv_admin", 
                                     rds=rdsb3)
        
        return {
            'statusCode': 200,
            'body': json.dumps('Hello from Lambda!')
        }

    except BaseException as err:
        print(f"Unexpected {err=}, {type(err)=}")


class Aurora:
    def get_connection(self, endpoint, port, iam_user, user, rds):
        
        try:
            
            print('get_connection')
            
            # Generate IAM token for default account sbp_admin
            token = rds.generate_db_auth_token(DBHostname=endpoint,
                                               Port=port,
                                               DBUsername=iam_user)
            
            print('IAM token generated')
            
            # Connect to MySQL
            try:
    
                print('Trying to connect with IAM user to RDS MySQL')
                
                connection = connector.connect(host=endpoint,
                                               user=iam_user,
                                               password=token,
                                               port=port,
                                               ssl_ca="rds-ca-2019-root.pem")
                
                print('Connection successfully with IAM user')
                
                return connection
                
            except BaseException as err:
            
                print('Connection failed while using the IAM user!')
                print(err)
        
        except BaseException as err:
            
            print('Connection failed while using the IAM user!')
            print(err)
        
            # In this case the sbp_admin_iam user is not working. Lets try to create it by using the default sbp_admin account
                
            # What should be the default secret manager (friendly) name
            #friendlyName = 'db-pass-' + endpoint.split('.')[0]
            
            # For now (TODO)
            #friendlyName = 'db-pass-default'
            
            # Initiate secretsmanager
            #secm = boto3.client('secretsmanager', region_name='eu-west-1')

            # Get Value from SecretManager
            #secret = secm.get_secret_value(SecretId=friendlyName)
    
            #connection = connector.connect(host=endpoint,
            #                               user=user,
            #                              password=secret['SecretString'])
            
            #print('Connection created with default admin account!')
            
            
            #rds_create_user(connection=connection,
            #                username='sbp_admin_iam')
            
            #return connection
            return       
        except BaseException as err:
            print(f"Unexpected {err=}, {type(err)=}")