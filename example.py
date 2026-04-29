# Modify to purpose. Add tasks to the account_tasks and region_tasks sections. Add your own functions to support those tasks.
# In this example, account_tasks has no custom jobs, region_tasks does have custom jobs defined in additional functions:
# example_list_rds_instances
# example_list_aurora_instances
# Modify 'filename' to taste and modify setup_csv_file with the desired Headers
# Initial credentials taken from ENV vars. To do GovCloud partition, simply supply credentials in env variables. Upon failure, script 
# will change partitions as a fallback automatically.


import boto3
import logging
import csv
import datetime

from aws_account_walker import AWSAccountManager, configure_logging

#CSV file setup
filename = datetime.datetime.now().strftime("%Y%m%d%H%M") + "-rds-dbs.csv"
configure_logging()
manager = AWSAccountManager(testing=True)
logging.info(f"Processing start from requesting script.")

def setup_csv_file(filename):
    logging.info(f"setup_csv_file -> {filename}")
    with open(filename, 'w', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(['Account', 'Region', 'RDS Service', 'Type', 'Engine', 'Endpoint', 'TCP Port'])
        
# Define the account and region tasks
def account_task(account_id):
    logging.info(f"account_task -> Processing account {account_id}")
    print(f"Processing account {account_id}")
    
    #Your example Account or Global tasks begin here
    #######################################

def region_task(session, account_id, region, logger):
    logging.info(f"region_task -> Region {region} for account {account_id}")
    if region.startswith('us-'):            
        logging.info(f"Processing region {region} for account {account_id}")
        print(f"Processing region {region} for account {account_id}")
        
        #Your example regional tasks begin here
        #######################################
        rds_client = session.client('rds',region_name=region)
        # Execute example_ RDS and Aurora listing functions
        example_list_rds_instances(rds_client, account_id, region)
        example_list_aurora_clusters(rds_client, account_id, region)
        #######################################

    else:
        return

    
def example_list_rds_instances(rds_client, account_id, region):
    logging.info(f"list_rds_instances: {rds_client}, {account_id},{region}")
    print(f"list_rds_instances-> {rds_client}, {account_id},{region}")
    
    try:
        paginator = rds_client.get_paginator('describe_db_instances')
        page_iterator = paginator.paginate()

        for page in page_iterator:
            print(f"{page}")
            if page['DBInstances']:
                for instance in page['DBInstances']:
                    details = [
                        account_id,
                        region,
                        'RDS',
                        'Instance',
                        instance['Engine'],
                        instance['Endpoint']['Address'],
                        instance['Endpoint']['Port']
                    ]
                    logging.info(f"RDS Instance: {details}")
                    print(f"RDS Instance: {details}")
                    append_to_csv(filename, details)
                else:
                    print(f"DB instances = {page['DBInstances']}")
    except Exception as e:
            logging.error(f"Failed to execute tasks: {e}")
            print(f"Failed to execute tasks: {e}")

def example_list_aurora_clusters(rds_client, account_id, region):
    logging.info(f"list_aurora_clusters -> {rds_client}, {account_id},{region}")
    paginator = rds_client.get_paginator('describe_db_clusters')
    page_iterator = paginator.paginate()

    for page in page_iterator:
        for cluster in page['DBClusters']:
            details = [
                account_id,
                region,
                'Aurora',
                'Cluster',
                cluster['Engine'],
                cluster['Endpoint'],
                ''  # Port information for Aurora clusters may require additional logic
            ]
            logging.info(f"Aurora Cluster: {details}")
            append_to_csv(filename, details)

def append_to_csv(filename, data):
    logging.info(f"append_to_csv -> {filename}")
    with open(filename, 'a', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(data)


if __name__ == "__main__":
    logging.info(f"__main__")
    manager = AWSAccountManager(testing=True)
    setup_csv_file(filename)
    logging.info(f"__main__ call to 'manager' with tasks")
    manager.execute_account_tasks(account_task, region_task)
