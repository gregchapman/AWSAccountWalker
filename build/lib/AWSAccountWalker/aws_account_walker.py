#!/usr/bin/env python
import os
import time
import csv
import logging
import sys
import datetime
import json
import fnmatch
import re
import botocore.exceptions
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError, EndpointConnectionError
import concurrent.futures
from threading import Lock

# boto3 will be required
import boto3


from datetime import date

# Configure logging at the start of your script or within a main function
def configure_logging():
    logging.basicConfig(
        level=logging.ERROR,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("aws_account_manager.log"),
            #logging.StreamHandler()  # Uncomment if you want console output as well
        ]
    )

class AWSAccountManager:
    def __init__(self, testing=True):
        self.logger = logging.getLogger(self.__class__.__name__)  # Create a named logger
        #self.logger.setLevel(logging.DEBUG)  # Optional: Set a specific logging level
        self.default_region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        self.testing = testing
        self.aws_account_ids = self.get_active_accounts()
        self.retry_regions = ['us-east-1', 'us-gov-west-1']  # Add 'us-gov-west-1' for GovCloud fallback

    def assume_role(self, account_id, region_name=None):
        if region_name is None:
            region_name = self.default_region
        sts_client = boto3.client('sts', region_name=region_name)
        arn_prefix = "arn:aws-us-gov" if "us-gov" in region_name else "arn:aws"
        role_arn = f"{arn_prefix}:iam::{account_id}:role/OrganizationAccountAccessRole"

        try:
            assumed_role = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName="OrganizationAccessSession"
            )
            self.logger.info(f"Successfully assumed role for account {account_id} in region {region_name}")
            return assumed_role['Credentials']
        except (ClientError, EndpointConnectionError) as error:
            self.logger.debug(f"Error assuming role in account {account_id}, region {region_name}: {error}")
            return None

    def list_available_regions(self, service='ec2', fallback=False):
        try:
            client = boto3.client(service, region_name=self.default_region)
            regions = client.describe_regions()
            return [region['RegionName'] for region in regions['Regions'] if region['RegionName'].startswith('us-')]
        except (ClientError, EndpointConnectionError) as error:
            if not fallback:
                self.logger.debug(f"Error listing regions, trying 'us-gov-west-1': {error}")
                self.default_region = 'us-gov-west-1'
                return self.list_available_regions(service, fallback=True)
            else:
                self.logger.error(f"Final error listing regions in fallback region 'us-gov-west-1': {error}")
                return []

    def get_active_accounts(self, fallback=False):
        client = boto3.client('organizations', region_name=self.default_region)
        active_accounts = []
        try:
            paginator = client.get_paginator('list_accounts')
            for page in paginator.paginate():
                for account in page['Accounts']:
                    if account['Status'] != 'SUSPENDED':
                        active_accounts.append(account['Id'])
            self.logger.debug(f"{active_accounts}")
            return active_accounts
        except (ClientError, EndpointConnectionError) as error:
            if not fallback:
                self.logger.error(f"Error getting accounts, trying 'us-gov-west-1': {error}")
                self.default_region = 'us-gov-west-1'
                return self.get_active_accounts(fallback=True)
            else:
                self.logger.error(f"Final error getting accounts in fallback region 'us-gov-west-1': {error}")
                return []

    def process_accounts(self, account_processor, region_processor=None):
            """
            Process each active account with the given account_processor function.
            If region_processor is provided, it will also process each region within each account.
            """
            with ThreadPoolExecutor(max_workers=9) as executor:
                # Create a future for each account processing
                future_to_account = {executor.submit(self.process_account, account_id, account_processor, region_processor): account_id for account_id in self.aws_account_ids}
                for future in as_completed(future_to_account):
                    account_id = future_to_account[future]
                    try:
                        future.result()
                        self.logger.info(f"Completed processing for account: {account_id}")
                    except Exception as exc:
                        self.logger.error(f"Error processing account {account_id}: {exc}")

    def process_account(self, account_id, account_processor, region_processor):
        """
        Process a single account with the given account_processor function.
        If region_processor is provided, process each region within the account.
        """
        # Call the account-level processor
        self.logger.info(f"process_accout -> Processing for account: {account_id}")
        account_processor(account_id)

        # If a region-level processor is provided, list regions and process each
        if region_processor:
            print(f"{region_processor}")
            regions = self.list_available_regions()
            self.logger.info(f"process_account -> checking for regional instructions {account_id}, {regions}")
            for region in regions:
                self.logger.info(f"{region}")
                #session = boto3.Session(region_name=region)  # Create a session per region
                credentials = self.assume_role(account_id, region)
                if credentials:
                    session = boto3.Session(
                        aws_access_key_id=credentials['AccessKeyId'],
                        aws_secret_access_key=credentials['SecretAccessKey'],
                        aws_session_token=credentials['SessionToken'],
                        region_name=region
                    )
                self.logger.info(f"calling region_processor -> {session}, {region}, {account_id}")
                
                region_processor(session, region, account_id, self.logger)
    
    def create_session_for_account_region(self, account_id, region):
        credentials = self.assume_role(account_id, region)
        if credentials:
            session = boto3.Session(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
                region_name=region
            )
            return session
        else:
            self.logger.error(f"Could not assume role for account {account_id} in region {region}")
            return None

    def execute_account_tasks(self, account_task, region_task=None):
        try:
            with ThreadPoolExecutor() as executor:
                futures = {executor.submit(account_task, account_id): account_id for account_id in self.aws_account_ids}
                for future in as_completed(futures):
                    account_id = futures[future]
                    try:
                        future.result()  # This blocks until the account task is complete
                        self.logger.info(f"Account task completed for account: {account_id}")
                        # Here, submit region tasks for each account after its account task completes
                        if region_task:
                            regions = self.list_available_regions()
                            for region in regions:
                                # Ensure this is the correct way to obtain the session for each region
                                session = self.create_session_for_account_region(account_id, region)
                                if session:
                                    self.logger.info(f"Submitting region task for {account_id} in {region}")
                                    executor.submit(region_task, session, account_id, region, self.logger)
                    except Exception as e:
                        self.logger.error(f"execute_account_tasks -> Error processing account {account_id}: {e}")
        except Exception as e:
            self.logger.error(f"Failed to execute account or region tasks: {e}")

def account_processor(account_id):
    print(f"Processing global services for account {account_id}")

def region_processor(session, region, account_id, logger):
    logger.info(f"Starting region-level task for account {account_id} in region {region}")
    # Your existing processing logic
    print(f"Processing region {region} for account {account_id}")
    
def main():
    #logging.basicConfig(level=logging.INFO)
    configure_logging()
    manager = AWSAccountManager()
    manager.process_accounts()

if __name__ == "__main__":
    configure_logging()
    manager = AWSAccountManager()
    manager.process_accounts(account_processor, region_processor)
