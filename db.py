import boto3
import os
import json
import uuid
import time
from datetime import datetime
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
from dotenv import load_dotenv

load_dotenv()

# AWS Configuration
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

print(f"AWS Region: {AWS_REGION}")
print(f"Using AWS credentials: {'Configured' if AWS_ACCESS_KEY and AWS_SECRET_KEY else 'Missing'}")

# Check if AWS credentials are provided
if not AWS_ACCESS_KEY or not AWS_SECRET_KEY:
    print("WARNING: AWS credentials not found. Falling back to local storage.")
    # Local storage variables
    USERS_FILE = "users.json"
    TASKS_FILE = "tasks.json"
    
    # Local storage functions
    def _load_data(filename):
        """Load data from a JSON file"""
        try:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    return json.load(f)
            return []
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def _save_data(data, filename):
        """Save data to a JSON file"""
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    
    # User operations for local storage
    def get_user(username):
        """Get user by username"""
        users = _load_data(USERS_FILE)
        for user in users:
            if user["username"] == username:
                return user
        return None
    
    def create_user(username, hashed_password, email):
        """Create a new user"""
        users = _load_data(USERS_FILE)
        
        # Check if username already exists
        if any(user["username"] == username for user in users):
            return None
        
        new_user = {
            'username': username,
            'password': hashed_password,
            'email': email,
            'created_at': datetime.now().isoformat()
        }
        
        users.append(new_user)
        _save_data(users, USERS_FILE)
        return new_user
    
    # Task operations for local storage
    def save_tasks(username, tasks):
        """Save tasks for a user"""
        all_tasks = _load_data(TASKS_FILE)
        saved_tasks = []
        
        for task in tasks:
            task_id = str(uuid.uuid4())
            task_item = {
                'task_id': task_id,
                'username': username,
                'title': task.get('title'),
                'description': task.get('description'),
                'priority': task.get('priority'),
                'estimated_duration': task.get('estimated_duration'),
                'status': task.get('status', 'pending'),
                'category': task.get('category'),
                'created_at': datetime.now().isoformat()
            }
            
            all_tasks.append(task_item)
            saved_tasks.append(task_item)
        
        _save_data(all_tasks, TASKS_FILE)
        return saved_tasks
    
    def get_user_tasks(username):
        """Get all tasks for a user"""
        all_tasks = _load_data(TASKS_FILE)
        return [task for task in all_tasks if task.get('username') == username]
    
    def update_task_status(task_id, status):
        """Update task status"""
        all_tasks = _load_data(TASKS_FILE)
        
        for task in all_tasks:
            if task.get('task_id') == task_id:
                task['status'] = status
                task['updated_at'] = datetime.now().isoformat()
                _save_data(all_tasks, TASKS_FILE)
                return task
                
        return None
    
    def get_task_stats(username):
        """Get task statistics for a user"""
        tasks = get_user_tasks(username)
        
        if not tasks:
            return "No task history found."
        
        completed_tasks = [t for t in tasks if t.get('status') == 'completed']
        pending_tasks = [t for t in tasks if t.get('status') == 'pending']
        
        return {
            "total": len(tasks),
            "completed": len(completed_tasks),
            "pending": len(pending_tasks)
        }
    
    # Create empty files if they don't exist
    def initialize_storage():
        """Initialize JSON files if they don't exist"""
        if not os.path.exists(USERS_FILE):
            _save_data([], USERS_FILE)
            
        if not os.path.exists(TASKS_FILE):
            _save_data([], TASKS_FILE)
    
    # Initialize local storage
    initialize_storage()
    print("Using local file storage.")
    
else:
    # Initialize DynamoDB client
    try:
        # Table names
        USERS_TABLE = "TaskRecommenderUsers"
        TASKS_TABLE = "TaskRecommenderTasks"
        
        dynamodb = boto3.resource(
            'dynamodb',
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY
        )
        
        def create_tables_if_not_exist():
            """Create DynamoDB tables if they don't exist"""
            try:
                tables = list(dynamodb.tables.all())
                table_names = [table.name for table in tables]
                
                if USERS_TABLE not in table_names:
                    users_table = dynamodb.create_table(
                        TableName=USERS_TABLE,
                        KeySchema=[
                            {'AttributeName': 'username', 'KeyType': 'HASH'}
                        ],
                        AttributeDefinitions=[
                            {'AttributeName': 'username', 'AttributeType': 'S'}
                        ],
                        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                    )
                    users_table.meta.client.get_waiter('table_exists').wait(TableName=USERS_TABLE)
                    print(f"Created table {USERS_TABLE}")
                
                if TASKS_TABLE not in table_names:
                    tasks_table = dynamodb.create_table(
                        TableName=TASKS_TABLE,
                        KeySchema=[
                            {'AttributeName': 'task_id', 'KeyType': 'HASH'}
                        ],
                        AttributeDefinitions=[
                            {'AttributeName': 'task_id', 'AttributeType': 'S'},
                            {'AttributeName': 'username', 'AttributeType': 'S'}
                        ],
                        GlobalSecondaryIndexes=[
                            {
                                'IndexName': 'UserTasksIndex',
                                'KeySchema': [
                                    {'AttributeName': 'username', 'KeyType': 'HASH'}
                                ],
                                'Projection': {'ProjectionType': 'ALL'},
                                'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                            }
                        ],
                        ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                    )
                    tasks_table.meta.client.get_waiter('table_exists').wait(TableName=TASKS_TABLE)
                    print(f"Created table {TASKS_TABLE}")
                    
                return True
            except (ClientError, NoCredentialsError, EndpointConnectionError) as e:
                print(f"Error creating tables: {str(e)}")
                return False

        # User operations
        def get_user(username):
            """Get user by username"""
            table = dynamodb.Table(USERS_TABLE)
            try:
                response = table.get_item(Key={'username': username})
                return response.get('Item')
            except (ClientError, NoCredentialsError, EndpointConnectionError) as e:
                print(f"Error retrieving user: {e}")
                return None

        def create_user(username, hashed_password, email):
            """Create a new user"""
            table = dynamodb.Table(USERS_TABLE)
            user = {
                'username': username,
                'password': hashed_password,
                'email': email,
                'created_at': datetime.now().isoformat()
            }
            try:
                table.put_item(Item=user)
                return user
            except (ClientError, NoCredentialsError, EndpointConnectionError) as e:
                print(f"Error creating user: {e}")
                return None

        # Task operations
        def save_tasks(username, tasks):
            """Save tasks for a user"""
            table = dynamodb.Table(TASKS_TABLE)
            saved_tasks = []
            
            for task in tasks:
                task_id = str(uuid.uuid4())
                task_item = {
                    'task_id': task_id,
                    'username': username,
                    'title': task.get('title'),
                    'description': task.get('description'),
                    'priority': task.get('priority'),
                    'estimated_duration': task.get('estimated_duration'),
                    'status': task.get('status', 'pending'),
                    'category': task.get('category'),
                    'created_at': datetime.now().isoformat()
                }
                
                try:
                    table.put_item(Item=task_item)
                    saved_tasks.append(task_item)
                except (ClientError, NoCredentialsError, EndpointConnectionError) as e:
                    print(f"Error saving task: {e}")
            
            return saved_tasks

        def get_user_tasks(username):
            """Get all tasks for a user"""
            table = dynamodb.Table(TASKS_TABLE)
            try:
                response = table.query(
                    IndexName='UserTasksIndex',
                    KeyConditionExpression=boto3.dynamodb.conditions.Key('username').eq(username)
                )
                return response.get('Items', [])
            except (ClientError, NoCredentialsError, EndpointConnectionError) as e:
                print(f"Error retrieving tasks: {e}")
                return []

        def update_task_status(task_id, status):
            """Update task status"""
            table = dynamodb.Table(TASKS_TABLE)
            try:
                response = table.update_item(
                    Key={'task_id': task_id},
                    UpdateExpression="set #status = :s, updated_at = :u",
                    ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues={
                        ':s': status,
                        ':u': datetime.now().isoformat()
                    },
                    ReturnValues="UPDATED_NEW"
                )
                return response
            except (ClientError, NoCredentialsError, EndpointConnectionError) as e:
                print(f"Error updating task: {e}")
                return None

        def get_task_stats(username):
            """Get task statistics for a user"""
            tasks = get_user_tasks(username)
            
            if not tasks:
                return "No task history found."
            
            completed_tasks = [t for t in tasks if t.get('status') == 'completed']
            pending_tasks = [t for t in tasks if t.get('status') == 'pending']
            
            return {
                "total": len(tasks),
                "completed": len(completed_tasks),
                "pending": len(pending_tasks)
            }

        # Initialize tables
        if create_tables_if_not_exist():
            print("Successfully connected to DynamoDB.")
        else:
            raise Exception("Failed to create DynamoDB tables.")
            
    except Exception as e:
        print(f"Error connecting to DynamoDB: {str(e)}")
        print("Falling back to local storage...")
        
        # Local storage variables
        USERS_FILE = "users.json"
        TASKS_FILE = "tasks.json"
        
        # Local storage functions (same implementation as above)
        def _load_data(filename):
            """Load data from a JSON file"""
            try:
                if os.path.exists(filename):
                    with open(filename, 'r') as f:
                        return json.load(f)
                return []
            except (json.JSONDecodeError, FileNotFoundError):
                return []
        
        def _save_data(data, filename):
            """Save data to a JSON file"""
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
        
        # User operations for local storage
        def get_user(username):
            """Get user by username"""
            users = _load_data(USERS_FILE)
            for user in users:
                if user["username"] == username:
                    return user
            return None
        
        def create_user(username, hashed_password, email):
            """Create a new user"""
            users = _load_data(USERS_FILE)
            
            # Check if username already exists
            if any(user["username"] == username for user in users):
                return None
            
            new_user = {
                'username': username,
                'password': hashed_password,
                'email': email,
                'created_at': datetime.now().isoformat()
            }
            
            users.append(new_user)
            _save_data(users, USERS_FILE)
            return new_user
        
        # Task operations for local storage
        def save_tasks(username, tasks):
            """Save tasks for a user"""
            all_tasks = _load_data(TASKS_FILE)
            saved_tasks = []
            
            for task in tasks:
                task_id = str(uuid.uuid4())
                task_item = {
                    'task_id': task_id,
                    'username': username,
                    'title': task.get('title'),
                    'description': task.get('description'),
                    'priority': task.get('priority'),
                    'estimated_duration': task.get('estimated_duration'),
                    'status': task.get('status', 'pending'),
                    'category': task.get('category'),
                    'created_at': datetime.now().isoformat()
                }
                
                all_tasks.append(task_item)
                saved_tasks.append(task_item)
            
            _save_data(all_tasks, TASKS_FILE)
            return saved_tasks
        
        def get_user_tasks(username):
            """Get all tasks for a user"""
            all_tasks = _load_data(TASKS_FILE)
            return [task for task in all_tasks if task.get('username') == username]
        
        def update_task_status(task_id, status):
            """Update task status"""
            all_tasks = _load_data(TASKS_FILE)
            
            for task in all_tasks:
                if task.get('task_id') == task_id:
                    task['status'] = status
                    task['updated_at'] = datetime.now().isoformat()
                    _save_data(all_tasks, TASKS_FILE)
                    return task
                    
            return None
        
        def get_task_stats(username):
            """Get task statistics for a user"""
            tasks = get_user_tasks(username)
            
            if not tasks:
                return "No task history found."
            
            completed_tasks = [t for t in tasks if t.get('status') == 'completed']
            pending_tasks = [t for t in tasks if t.get('status') == 'pending']
            
            return {
                "total": len(tasks),
                "completed": len(completed_tasks),
                "pending": len(pending_tasks)
            }
        
        # Create empty files if they don't exist
        def initialize_storage():
            """Initialize JSON files if they don't exist"""
            if not os.path.exists(USERS_FILE):
                _save_data([], USERS_FILE)
                
            if not os.path.exists(TASKS_FILE):
                _save_data([], TASKS_FILE)
        
        # Initialize local storage
        initialize_storage()
        print("Using local file storage due to AWS connection issues.") 