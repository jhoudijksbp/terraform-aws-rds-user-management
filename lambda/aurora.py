import boto3
import json
import os
import sys
import logging
import secrets
import string
from mysql import connector
from mysql.connector import Error

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class Aurora:
    def rds_manage_user(self, connection, secret):
        
        passwd = secret['password']
        
        # First check if user exists
        logger.info(f"Check if user: {secret['username']} exists")
        exists = self.rds_user_exists(connection, secret['username'])
        logger.info(f"Result user exits: {exists}")
        
        # Create the user because it does not exist
        if exists == False:
            
            # Generate a password if needed.
            if passwd == "" or passwd == "will_get_generated_later":
                passwd = self.generate_password()
            
            # Try to create a user
            #result = self.rds_create_user(conn=connection,
            #                              username=secret['username'],
            #                              password=passwd,
            #                              usertype=secret['authentication'],
            #                              src_host=secret['src_host'])
            
        # Check server permissions 
        #if "global" in secret['privileges']:
        #    logger.info(f"Global permissions configured for user: {secret['username']}")
        #    
        #    self.rds_check_global_permissions(conn=connection,
        #                                      username=secret['username'],
        #                                      privs=secret['privileges']['global']['privileges'],
        #                                      src_host=secret['src_host'])
        #    
        #    logger.info(f"Global permissions done for user: {secret['username']}")
        #else:
        #    logger.info(f"No Global permissions configured")
            
            
        # Check database permissions
        #logger.info(f"Checking configured database permissions for: {secret['username']}")
        #
        #self.rds_check_database_permissions(conn=connection,
        #                                    username=secret['username'],
        #                                    privs=secret['privileges'],
        #                                    src_host=secret['src_host'])
                                  
        #logger.info(f"Database permissions done for user: {secret['username']}")
        
        return passwd
    
    def generate_password(self):
        alphabet = string.ascii_letters + string.digits + string.punctuation
        password = ''.join(secrets.choice(alphabet) for i in range(20))
        return password
        
    def rds_check_database_permissions(self, conn, username, privs, src_host):
        
        available_privileges = [
            "ALTER",
            "CREATE",
            "CREATE_ROUTINE",
            "CREATE_TMP_TABLE",
            "CREATE_VIEW",
            "DELETE",
            "DROP",
            "EXECUTE",
            "INDEX",
            "INSERT",
            "LOCK_TABLES",
            "SELECT",
            "SHOW_VIEW",
            "TRIGGER",
            "UPDATE"
            ]
        
        for key in privs:
            
            # Skip global permissions
            if key == 'global':
                continue
            
            # Check if configured permissions are in the set of available privileges
            if set(privs[key]['privileges']).issubset(available_privileges) == False:
                raise Exception('Unknown database privileges specified')
            
            # Convert privileges which should be granted to column names in MySQL
            priv_cols = [s.capitalize() + "_priv" for s in privs[key]['privileges']]
    
            # Create select query for getting global privileges
            all_cols = [s.capitalize() + "_priv" for s in available_privileges]
            all_columns = [s.capitalize() + "_priv," for s in available_privileges]
            
            query = "SELECT "
            # Generate part of the query to check permissions
            for col in all_cols:
                if col in priv_cols:
                    query = f"{query} CASE WHEN {col} = 'Y' THEN 1 ELSE 0 END AS {col},"
                else:
                    query = f"{query} CASE WHEN {col} = 'N' THEN 1 ELSE 0 END AS {col},"
            
            # remove last comma.        
            query = query[:-1]
            
            all_cols    = "".join(all_columns)
            all_cols    = all_cols[:-1]
            sql         = f"""{query}
                                FROM mysql.db
                               WHERE User = %s
                                 AND Host = %s
                                 AND Db = %s"""
                                 
            # Execute the query
            data   = (username, src_host, privs[key]['database'])
            cursor = conn.cursor()
            cursor.execute(sql, data)
            
            # Generate REVOKE and GRANT statements
            grant   = False
            grants  = []
            revokes = []
            result = cursor.fetchone()
            if result:
                
                row = dict(zip(cursor.column_names, result))
                
                for key, value in row.items():
                    
                    # So if the value is 1 we need to change something in current set of permissions
                    if value == 0:
                        
                        # Check if we need to grant or revoke
                        if key in priv_cols:
                            grants.append(key.replace('_priv','').upper())
                        else:
                            revokes.append(key.replace('_priv','').upper())
                
                # Generate revoke statement
                if len(revokes) > 0:
                    logger.info(f"REVOKE permissions: {','.join(revokes)}")
                    revoke_stmt = f"REVOKE {','.join(revokes)} ON `{privs[key]['database']}`.* TO {username}@'{src_host}'"
                    logger.debug(revoke_stmt)
                    cursor.execute(revoke_stmt)
                    logger.info(f"REVOKE done")
                    
                # Generate grant statement
                if len(grants) > 0:
                    logger.info(f"GRANT permissions: {','.join(revokes)}")
                    grant_stmt = f"GRANT {','.join(grants)} ON `{privs[key]['database']}`.* TO {username}@'{src_host}'"
                    logger.debug(grant_stmt)
                    cursor.execute(grant_stmt)
                    logger.info("GRANT done")
                
            else:
                logger.info(f"GRANT permissions: {','.join(privs[key]['privileges'])}")
                grant_stmt = f"GRANT {','.join(privs[key]['privileges'])} ON `{privs[key]['database']}`.* TO {username}@'{src_host}'"
                logger.debug(grant_stmt)
                cursor.execute(grant_stmt)
                logger.info("GRANT done")
        
            
        
        return
    
    def rds_check_global_permissions(self, conn, username, privs, src_host):
        
        # List of al Aurora/MySQL available global privileges
        available_privileges = [
            "ALTER",
            "ALTER_ROUTINE",
            "CREATE",
            "CREATE_ROUTINE",
            "CREATE_TMP_TABLE",
            "CREATE_USER",
            "CREATE_VIEW",
            "DELETE",
            "DROP",
            "EXECUTE",
            "FILE",
            "INDEX",
            "INSERT",
            "LOCK_TABLES",
            "PROCESS",
            "REFERENCES",
            "RELOAD",
            "SELECT",
            "SHOW_DB",
            "SHOW_VIEW",
            "SHUTDOWN",
            "SUPER",
            "TRIGGER",
            "UPDATE"
            ]
        
        # Check if configured privileges are existing privileges.
        if set(privs).issubset(available_privileges) == False:
            raise Exception('Unknown global privileges specified')
            
        # Convert privileges which should be granted to column names in MySQL
        priv_cols = [s.capitalize() + "_priv" for s in privs]

        # Create select query for getting global privileges
        all_cols = [s.capitalize() + "_priv" for s in available_privileges]
        all_columns = [s.capitalize() + "_priv," for s in available_privileges]
        
        query = "SELECT "
        # Generate part of the query to check permissions
        for col in all_cols:
            if col in priv_cols:
                query = f"{query} CASE WHEN {col} = 'Y' THEN 1 ELSE 0 END AS {col},"
            else:
                query = f"{query} CASE WHEN {col} = 'N' THEN 1 ELSE 0 END AS {col},"
        
        # remove last comma.        
        query = query[:-1]
        
        all_cols    = "".join(all_columns)
        all_cols    = all_cols[:-1]
        sql         = f"""{query}
                            FROM mysql.user
                           WHERE User = %s
                             AND Host = %s"""
                             
        # Execute the query
        data   = (username, src_host)
        cursor = conn.cursor()
        cursor.execute(sql, data)
        
        logger.info('query is exceuted')
        result = cursor.fetchone()

        # Query should deliver data otherwise something is wrong
        if result is None:
            raise Exception('No user found while checking global permissions!')
    
        # Create a dictionary of the row with column_names
        row    = dict(zip(cursor.column_names, result))
        
        # Generate REVOKE and GRANT statements
        grants  = []
        revokes = []
        for key, value in row.items():
            
            # So if the value is 1 we need to change something in current set of permissions
            if value == 0:
                
                # Check if we need to grant or revoke
                if key in priv_cols:
                    grants.append(key.replace('_priv','').upper())
                else:
                    revokes.append(key.replace('_priv','').upper())
        
        # Generate revoke statement
        if len(revokes) > 0:
            logger.info(f"REVOKE permissions: {','.join(revokes)}")
            revoke_stmt = f"REVOKE {','.join(revokes)} ON *.* TO {username}@'{src_host}'"
            cursor.execute(revoke_stmt)
            logger.info(f"REVOKE done")
            
        # Generate grant statement
        if len(grants) > 0:
            logger.info(f"GRANT permissions: {','.join(revokes)}")
            grant_stmt = f"GRANT {','.join(grants)} ON *.* TO {username}@'{src_host}'"
            logger.info(grant_stmt)
            cursor.execute(grant_stmt)
        
        return
        
    #def rds_execute_query(self, connection, query):
    #
    #    
    #
    #    return
    #     
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
        
        logger.info(f"drop MySQL user: {username}")
        
        cursor = connection.cursor(prepared=True)
        
        # Temporary drop this user
        sql = f"DROP USER {username}@'%';"
        cursor.execute(sql)
        logger.info(f"User dropped: {username}")
        
    def rds_create_iam_user(self, connection, username):
        
        try:
            logger.info(f"create MySQL user: {username}")
            
            cursor = connection.cursor(prepared=True)
            sql    = f"CREATE USER {username} IDENTIFIED WITH AWSAuthenticationPlugin AS 'RDS'"
            cursor.execute(sql)
            
            # Grant permissions to IAM_USER
            sql = f"grant SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, RELOAD, PROCESS, REFERENCES, INDEX, ALTER, SHOW DATABASES, CREATE TEMPORARY TABLES, LOCK TABLES, EXECUTE, CREATE VIEW, SHOW VIEW, CREATE ROUTINE, ALTER ROUTINE, CREATE USER, EVENT, TRIGGER on *.* to {username} with grant option;"
            cursor.execute(sql)
    
            sql = "flush privileges;"
            cursor.execute(sql)
            
            logger.info('privileges flushed!')
            
        except BaseException as err:
            print(f"Unexpected {err=}, {type(err)=}")
            
    def rds_create_user(self, conn, username, password, usertype, src_host):
        
        try:
            logger.info(f"create MySQL user: {username}")
            
            cursor = conn.cursor(prepared=True)
            
            # Create a new user
            if usertype == 'IAM':
                sql = f"CREATE USER {username}@'{src_host}' IDENTIFIED WITH AWSAuthenticationPlugin AS 'RDS'"
            else:
                logger.info('create user based on credentials')
                sql = f"CREATE USER {username}@'{src_host}' IDENTIFIED BY '{password}'"
                
            cursor.execute(sql)
        
            sql = "flush privileges;"
            cursor.execute(sql)
            
            logger.info('privileges flushed!')
            
        except BaseException as err:
            logger.error(f"Unexpected {err=}, {type(err)=}")

    def close_connection(self, connection):
        connection.close()
        
    def get_connection(self, endpoint, port, iam_user, user, rds, rds_aurora):
        
        try:
            
            # Generate IAM token for default account sbp_admin
            token = rds.generate_db_auth_token(DBHostname=endpoint,
                                               Port=port,
                                               DBUsername=iam_user)
            
            logger.info('IAM token generated')
            
            # Connect to MySQL
            try:
    
                logger.info('Trying to connect with IAM user to RDS MySQL')
                
                connection = connector.connect(host=endpoint,
                                               user=iam_user,
                                               password=token,
                                               port=port,
                                               ssl_ca="rds-ca-2019-root.pem")
                
                logger.info('Connection successfully with IAM user')
                
                return connection
                
            except BaseException as err:
            
                logger.info(err)
                logger.info('Connection failed while using the IAM user!')
                logger.info('Will try to connect with default master user')
                
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
                                               
                logger.info('Connected with MySQL database')
                result = rds_aurora.rds_create_iam_user(connection_master, iam_user)
                                                    
                logger.info(f"User: {iam_user} created")
                
        except BaseException as err:
            logger.error(err)

        except BaseException as err:
            logger.error(f"Unexpected {err=}, {type(err)=}")