import boto3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Print loaded credentials
print("AWS Credentials from .env file:")
print(f"Region: {os.getenv('AWS_REGION')}")
print(f"Access Key ID: {os.getenv('AWS_ACCESS_KEY_ID')}")
secret = os.getenv('AWS_SECRET_ACCESS_KEY')
print(f"Secret Access Key: {secret[:4]}...{secret[-4:]} (length: {len(secret)})")

# Explicitly set credentials
dynamodb = boto3.resource(
    "dynamodb",
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

try:
    # Try to list tables directly using the resource
    print("\nAttempting to list tables using resource:")
    tables = list(dynamodb.tables.all())
    table_names = [table.name for table in tables]
    print(f"Found tables: {table_names}")
    
    # Try to describe the specific tables directly
    USERS_TABLE = "TaskRecommenderUsers"
    TASKS_TABLE = "TaskRecommenderTasks"
    
    print(f"\nLooking for table: {USERS_TABLE}")
    try:
        table = dynamodb.Table(USERS_TABLE)
        table_desc = table.meta.client.describe_table(TableName=USERS_TABLE)
        print(f"Table {USERS_TABLE} exists!")
    except Exception as e:
        print(f"Error describing {USERS_TABLE}: {str(e)}")
    
    print(f"\nLooking for table: {TASKS_TABLE}")
    try:
        table = dynamodb.Table(TASKS_TABLE)
        table_desc = table.meta.client.describe_table(TableName=TASKS_TABLE)
        print(f"Table {TASKS_TABLE} exists!")
    except Exception as e:
        print(f"Error describing {TASKS_TABLE}: {str(e)}")
    
except Exception as e:
    print(f"\nError: {str(e)}") 