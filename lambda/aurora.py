import boto3
import json
import os
import sys
from mysql import connector
from mysql.connector import Error

class Aurora:
    def rds_manage_user(self, connection, secret):
        
        print (f"Check if user: {secret['username']} exists")
        exists = self.rds_user_exists(connection, secret['username'])
        print (f"Result user exits: {exists}")
        
        # Create the user because it does not exist
        if exists == False:
            result = self.rds_create_user(conn=connection,
                                          username=secret['username'],
                                          password=secret['password'],
                                          usertype='credentials')
        

        # Check server permissions 
        
        
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
        print (f"User dropped: {username}")
        
    def rds_create_iam_user(self, connection, username):
        
        try:
            print (f"create MySQL user: {username}")
            
            cursor = connection.cursor(prepared=True)
            sql    = f"CREATE USER {username} IDENTIFIED WITH AWSAuthenticationPlugin AS 'RDS'"
            cursor.execute(sql)
            
            # Granting this user to be able to create other users
            sql = f"GRANT create user on *.* to {username} with grant option;"
            cursor.execute(sql)
            
            # Grant select on Mysql tables
            sql = f"grant select on *.* to {username} with grant option;"
            cursor.execute(sql)
            
            # Grant select on Mysql tables
            sql = f"grant reload on *.* to {username} with grant option;"
            cursor.execute(sql)
            
            sql = "flush privileges;"
            cursor.execute(sql)
            
            print('privileges flushed!')
            
        except BaseException as err:
            print(f"Unexpected {err=}, {type(err)=}")
            
    def rds_create_user(self, conn, username, password, usertype='IAM'):
        
        try:
            print (f"create MySQL user: {username}")
            
            cursor = conn.cursor(prepared=True)
            
            # Create a new user
            if usertype == 'IAM':
                sql = f"CREATE USER {username} IDENTIFIED WITH AWSAuthenticationPlugin AS 'RDS'"
            else:
                print('create user based on credentials')
                sql = f"CREATE USER {username} IDENTIFIED BY '{password}'"
                
            #data = (username, password)
            cursor.execute(sql)
            
            # Granting this user to be able to create other users
            #sql = f"GRANT create user on *.* to {username} with grant option;"
            #cursor.execute(sql)
            
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
                
                secretName = os.environ['SECRET_NAME'] 
                secm       = boto3.client('secretsmanager')
                secret     = secm.get_secret_value(SecretId=secretName)
                db_secret  = json.loads(secret['SecretString'])
                
                connection_master = connector.connect(host=endpoint,
                                                      user=db_secret['username'],
                                                      password=db_secret['password'],
                                                      port=port)
                #print('drop user')                                      
                #test = self.rds_drop_user(connection=connection_master, username=iam_user)
                #print('user dropped...exiting now.')
                #sys.exit(0)
                                               
                print('Connected with MySQL database')
                result = rds_aurora.rds_create_iam_user(connection_master, iam_user)
                                                    
                print(f"User: {iam_user} created")
                
        except BaseException as err:
            
            print(err)

        except BaseException as err:
            print(f"Unexpected {err=}, {type(err)=}")