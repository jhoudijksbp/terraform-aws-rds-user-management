import os
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

        master_username = os.environ['master_username']
        print(f"Master username: {master_username}")
        # TODO: 
        # - Make Secretsmanager class
        # iam_user='ccv_admin_iam',  should by fully configurable
        # user="ccv_admin" should be fully configurable
        # secretName = "db_master_secret_rds_sandbox_jho" should be fully configurable
        # rds_aurora.rds_create_user(connection_master easier/nicer way to use functions between classes?
        # Check errorhandling: Be sure on what is fatal and what is a warning and how to notify about alert/warning.
        
        # initiate boto3 for SecretsManager and RDS
        client = boto3.client('secretsmanager')
        rdsb3  = boto3.client('rds')
        
        # Load classes
        db = Aurora()
        
        # Only select secrets with a specific tag-value
        response = client.list_secrets(Filters=[{"Key": "tag-value", "Values": [DEFAULT_SECRET_TYPE]}])
        secretlist = response['SecretList']
        
        print('secretlist:')
        print(secretlist)
        
        # Save all available secrets in a list.
        while "NextToken" in response:
            response = client.list_secrets(NextToken=response['NextToken'])
            secretlist = secretlist + response['SecretList']
        
        # Loop over all secrets and try to manage al these secrets/users
        for secret in secretlist:

            # Retrieve the secret value of the specific Secret.
            response  = client.get_secret_value(SecretId=secret['ARN'])
            db_secret = json.loads(response['SecretString'])

            # Get a connection with the RDS instance
            conn = db.get_connection(endpoint=db_secret['host'], 
                                     port=db_secret['port'], 
                                     iam_user="ccv_admin_iam", 
                                     user="ccv_admin", 
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


class Aurora:
    def rds_manage_user(self, connection, secret):
        
        print (f"Check if user: {secret['username']} exists")
        exists = self.rds_user_exists(connection, secret['username'])
        print (f"Result user exits: {exists}")
        
        return
        
    def rds_user_exists(self, connection, username):
        
        exists = False
        cursor = connection.cursor()
        query  = "SELECT EXISTS(SELECT 1 FROM mysql.user WHERE user = %s) AS existing"
        data   = (username, )
        
        # Execute the query
        cursor.execute(query, data)
        result = cursor.fetchone()
        
        if result[0] == 1:
            exists = True
        
        return exists
        
    def rds_drop_user(self, connection, username):
        
        print (f"drop MySQL user: {username}")
        
        cursor = connection.cursor(prepared=True)
        
        # Temporary drop this user
        sql = f"DROP USER {username}@'%';"
        cursor.execute(sql)      
    
    def rds_create_user(self, connection, username):
        
        try:
            print (f"create MySQL user: {username}")
            
            cursor = connection.cursor(prepared=True)
            
            # Create a new user
            sql = f"CREATE USER {username} IDENTIFIED WITH AWSAuthenticationPlugin AS 'RDS'"
            cursor.execute(sql)
            
            # Granting this user to be able to create other users
            sql = f"GRANT create user on *.* to {username} with grant option;"
            cursor.execute(sql)
            
            # Grant select on Mysql tables
            sql = f"grant select on *.* to {username} with grant option;"
            cursor.execute(sql)
            
            sql = "flush privileges;"
            cursor.execute(sql)
            
            print('privileges flushed!')
            
        except BaseException as err:
            print(f"Unexpected {err=}, {type(err)=}")

    def close_connection(self, connection):
        connection.close()
        
    def get_connection(self, endpoint, port, iam_user, user, rds, rds_aurora):
        
        try:
            
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
            
                print(err)
                print('Connection failed while using the IAM user!')
                print('Will try to connect with default master user')
                
                secretName = "db_master_secret_rds_sandbox_jho"
                secm       = boto3.client('secretsmanager')
                secret     = secm.get_secret_value(SecretId=secretName)
                db_secret  = json.loads(secret['SecretString'])
                
                connection_master = connector.connect(host=endpoint,
                                                      user=db_secret['username'],
                                                      password=db_secret['password'],
                                                      port=port)
                                               
                print('Connected with MySQL database')
                result = rds_aurora.rds_create_user(connection_master,
                                                    iam_user)
                                                    
                print(f"User: {iam_user} created")
                
        except BaseException as err:
            
            print(err)

        except BaseException as err:
            print(f"Unexpected {err=}, {type(err)=}")