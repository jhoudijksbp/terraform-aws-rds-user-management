import os
import json
import boto3
import pprint
from mysql import connector
from mysql.connector import Error

def main(event, context):
    
    try:
        
        # First get all RDS instances in this account
        rds = boto3.client('rds')
        
        # Get all RDS clusters
        response = rds.describe_db_clusters()
    
        # Loop through all clusters
        for cluster in response['DBClusters']:
            
            clustername = cluster['Endpoint'].split('.')[0]
            
            # Get connection with RDS
            connection = get_connection(endpoint=cluster['Endpoint'],
                                        port=3306,
                                        iam_user='sbp_admin_iam',
                                        user='sbp_admin')
            
            data = load_json('mysql_users.json', clustername)
            
            # Lets manage all these users
            manage_mysql_users(data, connection)

            return {
                'statusCode': 200,
                'body': json.dumps('Hello from Lambda!')
            }

    except BaseException as err:
        print(f"Unexpected {err=}, {type(err)=}")


def manage_mysql_users(data, connection):
    
    cursor = connection.cursor()
    query  = ("SELECT User FROM mysql.user;")
    cursor.execute(query)
    mysql_users = cursor.fetchall()
    cursor.close()
    

    for user in data:
        
        result = next((i for i, v in enumerate(mysql_users) if v[0] == user['username']), None)
        
        if result > 0:
            print('User: ' + user['username'] + ' already created!')
            continue
        
        cursor = connection.cursor()
        
        # Create a new user
        sql = "CREATE USER " + user['username'] + " IDENTIFIED WITH AWSAuthenticationPlugin AS 'RDS'"
        cursor.execute(sql)
        
        # Granting this user to be able to create other users
        sql = "grant select on *.* to " + user['username']  + "@'%'"
        cursor.execute(sql)
        
        print("User: " + user['username'] + " created!")

def load_json(json_file, part=None):
    with open(json_file) as json_file:
        data = json.load(json_file)
        
        # Only select a part of the data if a part is specified
        if part:
            data = data[part]

    return data

def rds_create_user(connection, username):
    
    try:
        print ('create MySQL user:' + username)
        
        cursor = connection.cursor(prepared=True)
        
        # Temporary drop this user
        sql = "DROP USER sbp_admin_iam@'%';"
        cursor.execute(sql)
        
        # Create a new user
        sql = "CREATE USER " + username + " IDENTIFIED WITH AWSAuthenticationPlugin AS 'RDS'"
        cursor.execute(sql)
        
        # Granting this user to be able to create other users
        sql = "grant create user on *.* to " + username + " with grant option;"
        cursor.execute(sql)
        
        # Grant select on Mysql tables
        sql = "grant select on *.* to " + username + " with grant option;"
        cursor.execute(sql)
        
        sql = "flush privileges;"
        cursor.execute(sql)
        
        print('privileges flushed!')
        
    except BaseException as err:
        print(f"Unexpected {err=}, {type(err)=}")


def get_connection(endpoint, port, iam_user, user):
    
    try:
        
        # initiate boto3 RDS
        rds = boto3.client('rds')
        
        # Generate IAM token for default account sbp_admin
        token = rds.generate_db_auth_token(DBHostname=endpoint,
                                           Port=port,
                                           DBUsername=iam_user)
        
        # Connect to MySQL
        try:

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
        
            # In this case the sbp_admin_iam user is not working. Lets try to create it by using the default sbp_admin account
                
            # What should be the default secret manager (friendly) name
            friendlyName = 'db-pass-' + endpoint.split('.')[0]
            
            # For now (TODO)
            friendlyName = 'db-pass-default'
            
            # Initiate secretsmanager
            secm = boto3.client('secretsmanager', region_name='eu-west-1')

            # Get Value from SecretManager
            secret = secm.get_secret_value(SecretId=friendlyName)
    
            connection = connector.connect(host=endpoint,
                                           user=user,
                                           password=secret['SecretString'])
            
            print('Connection created with default admin account!')
            
            
            rds_create_user(connection=connection,
                            username='sbp_admin_iam')
            
            return connection
                
    except BaseException as err:
        print(f"Unexpected {err=}, {type(err)=}")
