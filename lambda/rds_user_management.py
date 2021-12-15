import argparse
import base64
import json
import logging
from pprint import pprint
import time
import boto3
import pymysql
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
DEFAULT_SECRET_TYPE = "RDS"

def main(event, context):
    
    try:

        print('start_new')
        
        # First get all secrets
        client = boto3.client('secretsmanager')
        
        response = client.list_secrets(Filters=[{"Key": "tag-value", "Values": [DEFAULT_SECRET_TYPE]}])
        secretlist = response['SecretList']
        
        while "NextToken" in response:
            response = client.list_secrets(NextToken=response['NextToken'])
            secretlist = secretlist + response['SecretList']

        print ('ITEMS:')
        print(len(secretlist))
    
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
        
        count=0
        for secret in secretlist:
            count +=1
            print('secret number: %s' % count)
            print(secret)
        
        
        print('end')
        
        return {
            'statusCode': 200,
            'body': json.dumps('Hello from Lambda!')
        }

    except BaseException as err:
        print(f"Unexpected {err=}, {type(err)=}")


class Aurora:
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

class SecretsManagerSecret:
    """Encapsulates Secrets Manager functions."""
    def __init__(self, secretsmanager_client):
        """
        :param secretsmanager_client: A Boto3 Secrets Manager client.
        """
        self.secretsmanager_client = secretsmanager_client
        self.name = None

    def _clear(self):
        self.name = None

    def create(self, name, secret_value):
        """
        Creates a new secret. The secret value can be a string or bytes.

        :param name: The name of the secret to create.
        :param secret_value: The value of the secret.
        :return: Metadata about the newly created secret.
        """
        self._clear()
        try:
            kwargs = {'Name': name}
            if isinstance(secret_value, str):
                kwargs['SecretString'] = secret_value
            elif isinstance(secret_value, bytes):
                kwargs['SecretBinary'] = secret_value
            response = self.secretsmanager_client.create_secret(**kwargs)
            self.name = name
            logger.info("Created secret %s.", name)
        except ClientError:
            logger.exception("Couldn't get secret %s.", name)
            raise
        else:
            return response

    def describe(self, name=None):
        """
        Gets metadata about a secret.

        :param name: The name of the secret to load. If `name` is None, metadata about
                     the current secret is retrieved.
        :return: Metadata about the secret.
        """
        if self.name is None and name is None:
            raise ValueError
        if name is None:
            name = self.name
        self._clear()
        try:
            response = self.secretsmanager_client.describe_secret(SecretId=name)
            self.name = name
            logger.info("Got secret metadata for %s.", name)
        except ClientError:
            logger.exception("Couldn't get secret metadata for %s.", name)
            raise
        else:
            return response

    def get_value(self, stage=None):
        """
        Gets the value of a secret.

        :param stage: The stage of the secret to retrieve. If this is None, the
                      current stage is retrieved.
        :return: The value of the secret. When the secret is a string, the value is
                 contained in the `SecretString` field. When the secret is bytes,
                 it is contained in the `SecretBinary` field.
        """
        if self.name is None:
            raise ValueError

        try:
            kwargs = {'SecretId': self.name}
            if stage is not None:
                kwargs['VersionStage'] = stage
            response = self.secretsmanager_client.get_secret_value(**kwargs)
            logger.info("Got value for secret %s.", self.name)
        except ClientError:
            logger.exception("Couldn't get value for secret %s.", self.name)
            raise
        else:
            return response

    def get_random_password(self, pw_length):
        """
        Gets a randomly generated password.

        :param pw_length: The length of the password.
        :return: The generated password.
        """
        try:
            response = self.secretsmanager_client.get_random_password(
                PasswordLength=pw_length)
            password = response['RandomPassword']
            logger.info("Got random password.")
        except ClientError:
            logger.exception("Couldn't get random password.")
            raise
        else:
            return password

    def put_value(self, secret_value, stages=None):
        """
        Puts a value into an existing secret. When no stages are specified, the
        value is set as the current ('AWSCURRENT') stage and the previous value is
        moved to the 'AWSPREVIOUS' stage. When a stage is specified that already
        exists, the stage is associated with the new value and removed from the old
        value.

        :param secret_value: The value to add to the secret.
        :param stages: The stages to associate with the secret.
        :return: Metadata about the secret.
        """
        if self.name is None:
            raise ValueError

        try:
            kwargs = {'SecretId': self.name}
            if isinstance(secret_value, str):
                kwargs['SecretString'] = secret_value
            elif isinstance(secret_value, bytes):
                kwargs['SecretBinary'] = secret_value
            if stages is not None:
                kwargs['VersionStages'] = stages
            response = self.secretsmanager_client.put_secret_value(**kwargs)
            logger.info("Value put in secret %s.", self.name)
        except ClientError:
            logger.exception("Couldn't put value in secret %s.", self.name)
            raise
        else:
            return response

    def update_version_stage(self, stage, remove_from, move_to):
        """
        Updates the stage associated with a version of the secret.

        :param stage: The stage to update.
        :param remove_from: The ID of the version to remove the stage from.
        :param move_to: The ID of the version to add the stage to.
        :return: Metadata about the secret.
        """
        if self.name is None:
            raise ValueError

        try:
            response = self.secretsmanager_client.update_secret_version_stage(
                SecretId=self.name, VersionStage=stage, RemoveFromVersionId=remove_from,
                MoveToVersionId=move_to)
            logger.info("Updated version stage %s for secret %s.", stage, self.name)
        except ClientError:
            logger.exception(
                "Couldn't update version stage %s for secret %s.", stage, self.name)
            raise
        else:
            return response

    def delete(self, without_recovery):
        """
        Deletes the secret.

        :param without_recovery: Permanently deletes the secret immediately when True;
                                 otherwise, the deleted secret can be restored within
                                 the recovery window. The default recovery window is
                                 30 days.
        """
        if self.name is None:
            raise ValueError

        try:
            self.secretsmanager_client.delete_secret(
                SecretId=self.name, ForceDeleteWithoutRecovery=without_recovery)
            logger.info("Deleted secret %s.", self.name)
            self._clear()
        except ClientError:
            logger.exception("Deleted secret %s.", self.name)
            raise

    def list(self, max_results):
        """
        Lists secrets for the current account.

        :param max_results: The maximum number of results to return.
        :return: Yields secrets one at a time.
        """
        try:
            paginator = self.secretsmanager_client.get_paginator('list_secrets')
            for page in paginator.paginate(
                    PaginationConfig={'MaxItems': max_results}):
                for secret in page['SecretList']:
                    yield secret
        except ClientError:
            logger.exception("Couldn't list secrets.")
            raise
    def list_all(self, max_results):
        """
        Lists secrets for the current account.

        :param max_results: The maximum number of results to return.
        :return: Yields secrets one at a time.
        """
        try:
            output = self('list_secrets')
            print(output['NextToken'])
            return output
        except ClientError:
            logger.exception("Couldn't list secrets.")
            raise
