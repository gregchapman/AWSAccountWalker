# AWSAccountWalker

**Import it. Define your tasks. Walk every account.**

AWSAccountWalker is a Python class you import into your own scripts. It handles the tedious mechanics of iterating an AWS Organization — enumerating accounts, assuming roles, creating sessions, managing threads — so your script only contains the logic you care about such as gettng the details of RDS, Lambda, Step Functions, etc., resources.

## The Pattern

```python
from AWSAccountWalker import AWSAccountManager

manager = AWSAccountManager()

def my_account_task(account_id):
    # Your code here — runs once per account
    pass

def my_region_task(session, account_id, region, logger):
    # Your code here — runs once per account/region with a ready-to-use boto3 session
    ec2 = session.client('ec2', region_name=region)
    # do whatever you need...

manager.execute_account_tasks(my_account_task, my_region_task)
```

That's it. You write the task functions. The walker does the rest.

## What You Get

When you instantiate `AWSAccountManager`, it immediately:
1. Enumerates all active (non-suspended) accounts in your Organization
2. Provides multithreaded execution across those accounts (9 workers)
3. Assumes `OrganizationAccountAccessRole` in each account for you
4. Hands your region task a fully-authenticated boto3 `Session` per account/region
5. Falls back between Commercial and GovCloud partitions automatically

You never write `sts:AssumeRole` boilerplate again.

## Installation

```bash
pip install .
```

Or from the wheel:

```bash
pip install dist/AWSAccountWalker-0.1.1-py3-none-any.whl
```

### Dependency

- `boto3 >= 1.21.28`

## Your Script Structure

Every script that uses AWSAccountWalker follows the same skeleton:

```python
from AWSAccountWalker import AWSAccountManager
from AWSAccountWalker.aws_account_walker import configure_logging

configure_logging()
manager = AWSAccountManager()

# 1. Define what to do per-account (global services, account-level checks, etc.)
def account_task(account_id):
    print(f"Account: {account_id}")

# 2. Define what to do per-region (regional resources, inventories, etc.)
def region_task(session, account_id, region, logger):
    # 'session' is already authenticated to this account+region
    client = session.client('whatever-service', region_name=region)
    # your logic here...

# 3. Run it
manager.execute_account_tasks(account_task, region_task)
```

### Task Function Signatures

| Task Type | Signature | Called |
|-----------|-----------|--------|
| Account | `account_task(account_id)` | Once per active account |
| Region | `region_task(session, account_id, region, logger)` | Once per account × US region |

The `session` in `region_task` is a boto3 Session with assumed-role credentials already configured. Just call `session.client('service')` and go.

## Execution Methods

```python
# Parallel accounts, sequential regions within each
manager.process_accounts(account_task, region_task)

# Parallel accounts AND parallel regions (maximum speed)
manager.execute_account_tasks(account_task, region_task)

# Account-level only, no region iteration
manager.execute_account_tasks(account_task)
```

## Credentials

The walker reads credentials from the **standard boto3 credential chain**:

1. Environment variables — `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`
2. Shared credentials file — `~/.aws/credentials`
3. AWS config file — `~/.aws/config`
4. Instance metadata (EC2, ECS, Lambda)

The initial credentials must have permission to:
- `organizations:ListAccounts`
- `sts:AssumeRole` on `OrganizationAccountAccessRole` in member accounts
- `ec2:DescribeRegions`

Typically you run from the **management account** or a **delegated admin** with an appropriate role.

### Role Assumption

The walker assumes `OrganizationAccountAccessRole` in each target account. ARN prefix is determined automatically:

- Commercial: `arn:aws:iam::<account_id>:role/OrganizationAccountAccessRole`
- GovCloud: `arn:aws-us-gov:iam::<account_id>:role/OrganizationAccountAccessRole`

### Default Region

Reads `AWS_DEFAULT_REGION` from environment, falls back to `us-east-1`. If commercial endpoints fail, automatically retries against `us-gov-west-1`.

## Region Scope

Only **US regions** (`us-*`) are iterated. Modify `list_available_regions()` if you need broader coverage.

## Testing Mode

```python
manager = AWSAccountManager(testing=True)   # default
manager = AWSAccountManager(testing=False)
```

The `testing` flag is stored as `self.testing` and available for your task functions to check. The walker itself does not gate behavior on it — it's a convention for your scripts to implement dry-run or subset logic:

```python
def region_task(session, account_id, region, logger):
    if manager.testing:
        print(f"[DRY RUN] Would process {account_id}/{region}")
        return
    # real work here...
```

## Creating a Session Manually

If you need a session outside the task loop:

```python
session = manager.create_session_for_account_region('123456789012', 'us-west-2')
if session:
    s3 = session.client('s3')
```

## Logging

`configure_logging()` writes to `aws_account_manager.log` at ERROR level. The logger is passed into your region tasks. Adjust verbosity:

```python
import logging
logging.basicConfig(level=logging.INFO, ...)
```

## Complete Example (example.py)

The included `example.py` walks all accounts/regions to inventory RDS instances and Aurora clusters into a CSV:

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...

python example.py
# Output: 202604291200-rds-dbs.csv
```

## Caveats

- **Thread safety:** If your tasks write to shared files, add a `threading.Lock`.
- **Rate limiting:** 9 concurrent threads making AssumeRole + API calls can trigger throttling in large orgs. Reduce `max_workers` or add backoff if needed.
- **Role name:** Hardcoded to `OrganizationAccountAccessRole`. Update `assume_role()` if your org uses a different role.
- **Region filter:** US-only. Change `list_available_regions()` for other regions.

## Project Structure

```
AWSAccountWalker/
├── AWSAccountWalker/
│   ├── __init__.py                # Exports AWSAccountManager
│   └── aws_account_walker.py     # The class you import
├── dist/
│   ├── AWSAccountWalker-0.1.1.tar.gz
│   └── AWSAccountWalker-0.1.1-py3-none-any.whl
├── example.py                     # RDS/Aurora inventory — copy and modify
├── setup.py
└── README.md
```

## Author

Greg Chapman — greg@mousetrax.com

## Version

0.1.1
