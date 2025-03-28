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
    def save_task(username, task):
        """Save a single task for a user"""
        all_tasks = _load_data(TASKS_FILE)
        
        # If task_id not provided, generate one
        if not task.get('task_id'):
            task['task_id'] = str(uuid.uuid4())
            
        task_item = {
            'task_id': task.get('task_id'),
            'username': username,
            'title': task.get('title'),
            'description': task.get('description'),
            'priority': task.get('priority'),
            'estimated_duration': task.get('estimated_duration'),
            'status': task.get('status', 'pending'),
            'category': task.get('category', ''),
            'due_date': task.get('due_date'),
            'due_time': task.get('due_time'),
            'reminder': task.get('reminder', False),
            'created_at': datetime.now().isoformat()
        }
        
        all_tasks.append(task_item)
        _save_data(all_tasks, TASKS_FILE)
        return task_item
    
    def save_tasks(username, tasks):
        """Save multiple tasks for a user"""
        all_tasks = _load_data(TASKS_FILE)
        saved_tasks = []
        
        for task in tasks:
            task_id = task.get('task_id', str(uuid.uuid4()))
            task_item = {
                'task_id': task_id,
                'username': username,
                'title': task.get('title'),
                'description': task.get('description'),
                'priority': task.get('priority'),
                'estimated_duration': task.get('estimated_duration'),
                'status': task.get('status', 'pending'),
                'category': task.get('category', ''),
                'due_date': task.get('due_date'),
                'due_time': task.get('due_time'),
                'reminder': task.get('reminder', False),
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
    
    def update_task(username, task_id, task_data):
        """Update task details"""
        all_tasks = _load_data(TASKS_FILE)
        
        for i, task in enumerate(all_tasks):
            if task.get('task_id') == task_id and task.get('username') == username:
                # Preserve original data that shouldn't be updated
                task_data['username'] = username
                task_data['task_id'] = task_id
                task_data['created_at'] = task.get('created_at')
                task_data['status'] = task_data.get('status', task.get('status'))
                task_data['updated_at'] = datetime.now().isoformat()
                
                # Update the task
                all_tasks[i] = task_data
                _save_data(all_tasks, TASKS_FILE)
                return True
                
        return False
    
    def delete_task(username, task_id):
        """Delete a task"""
        all_tasks = _load_data(TASKS_FILE)
        
        for i, task in enumerate(all_tasks):
            if task.get('task_id') == task_id and task.get('username') == username:
                del all_tasks[i]
                _save_data(all_tasks, TASKS_FILE)
                return True
                
        return False
    
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
        def save_task(username, task):
            """Save a single task for a user"""
            table = dynamodb.Table(TASKS_TABLE)
            
            # If task_id not provided, generate one
            if not task.get('task_id'):
                task['task_id'] = str(uuid.uuid4())
                
            task_item = {
                'task_id': task.get('task_id'),
                'username': username,
                'title': task.get('title'),
                'description': task.get('description'),
                'priority': task.get('priority'),
                'estimated_duration': task.get('estimated_duration'),
                'status': task.get('status', 'pending'),
                'category': task.get('category', ''),
                'due_date': task.get('due_date'),
                'due_time': task.get('due_time'),
                'reminder': task.get('reminder', False),
                'created_at': datetime.now().isoformat()
            }
            
            try:
                table.put_item(Item=task_item)
                return task_item
            except (ClientError, NoCredentialsError, EndpointConnectionError) as e:
                print(f"Error saving task: {e}")
                return None
        
        def save_tasks(username, tasks):
            """Save multiple tasks for a user"""
            table = dynamodb.Table(TASKS_TABLE)
            saved_tasks = []
            
            for task in tasks:
                task_id = task.get('task_id', str(uuid.uuid4()))
                task_item = {
                    'task_id': task_id,
                    'username': username,
                    'title': task.get('title'),
                    'description': task.get('description'),
                    'priority': task.get('priority'),
                    'estimated_duration': task.get('estimated_duration'),
                    'status': task.get('status', 'pending'),
                    'category': task.get('category', ''),
                    'due_date': task.get('due_date'),
                    'due_time': task.get('due_time'),
                    'reminder': task.get('reminder', False),
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
        
        def update_task(username, task_id, task_data):
            """Update task details"""
            table = dynamodb.Table(TASKS_TABLE)
            
            # First verify the task belongs to the user
            try:
                response = table.get_item(Key={'task_id': task_id})
                task = response.get('Item')
                
                if not task or task.get('username') != username:
                    return False
                
                # Prepare update expression
                update_expression = "set "
                expression_attribute_values = {
                    ':u': datetime.now().isoformat()
                }
                
                # Add all fields to update
                fields = ['title', 'description', 'priority', 'estimated_duration', 'category', 'status', 'due_date', 'due_time', 'reminder']
                for i, field in enumerate(fields):
                    if field in task_data:
                        update_expression += f"#{field} = :{field}, "
                        expression_attribute_values[f':{field}'] = task_data[field]
                
                # Add updated_at field
                update_expression += "updated_at = :u"
                
                # Create attribute names mapping
                expression_attribute_names = {f"#{field}": field for field in fields if field in task_data}
                
                # Update the item
                response = table.update_item(
                    Key={'task_id': task_id},
                    UpdateExpression=update_expression,
                    ExpressionAttributeNames=expression_attribute_names,
                    ExpressionAttributeValues=expression_attribute_values,
                    ReturnValues="UPDATED_NEW"
                )
                
                return True
            except (ClientError, NoCredentialsError, EndpointConnectionError) as e:
                print(f"Error updating task: {e}")
                return False
        
        def delete_task(username, task_id):
            """Delete a task"""
            table = dynamodb.Table(TASKS_TABLE)
            
            # First verify the task belongs to the user
            try:
                response = table.get_item(Key={'task_id': task_id})
                task = response.get('Item')
                
                if not task or task.get('username') != username:
                    return False
                
                # Delete the task
                table.delete_item(Key={'task_id': task_id})
                return True
            except (ClientError, NoCredentialsError, EndpointConnectionError) as e:
                print(f"Error deleting task: {e}")
                return False

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
        def save_task(username, task):
            """Save a single task for a user"""
            all_tasks = _load_data(TASKS_FILE)
            
            # If task_id not provided, generate one
            if not task.get('task_id'):
                task['task_id'] = str(uuid.uuid4())
                
            task_item = {
                'task_id': task.get('task_id'),
                'username': username,
                'title': task.get('title'),
                'description': task.get('description'),
                'priority': task.get('priority'),
                'estimated_duration': task.get('estimated_duration'),
                'status': task.get('status', 'pending'),
                'category': task.get('category', ''),
                'due_date': task.get('due_date'),
                'due_time': task.get('due_time'),
                'reminder': task.get('reminder', False),
                'created_at': datetime.now().isoformat()
            }
            
            all_tasks.append(task_item)
            _save_data(all_tasks, TASKS_FILE)
            return task_item
        
        def save_tasks(username, tasks):
            """Save multiple tasks for a user"""
            all_tasks = _load_data(TASKS_FILE)
            saved_tasks = []
            
            for task in tasks:
                task_id = task.get('task_id', str(uuid.uuid4()))
                task_item = {
                    'task_id': task_id,
                    'username': username,
                    'title': task.get('title'),
                    'description': task.get('description'),
                    'priority': task.get('priority'),
                    'estimated_duration': task.get('estimated_duration'),
                    'status': task.get('status', 'pending'),
                    'category': task.get('category', ''),
                    'due_date': task.get('due_date'),
                    'due_time': task.get('due_time'),
                    'reminder': task.get('reminder', False),
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
        
        def update_task(username, task_id, task_data):
            """Update task details"""
            all_tasks = _load_data(TASKS_FILE)
            
            for i, task in enumerate(all_tasks):
                if task.get('task_id') == task_id and task.get('username') == username:
                    # Preserve original data that shouldn't be updated
                    task_data['username'] = username
                    task_data['task_id'] = task_id
                    task_data['created_at'] = task.get('created_at')
                    task_data['status'] = task_data.get('status', task.get('status'))
                    task_data['updated_at'] = datetime.now().isoformat()
                    
                    # Update the task
                    all_tasks[i] = task_data
                    _save_data(all_tasks, TASKS_FILE)
                    return True
                    
            return False
        
        def delete_task(username, task_id):
            """Delete a task"""
            all_tasks = _load_data(TASKS_FILE)
            
            for i, task in enumerate(all_tasks):
                if task.get('task_id') == task_id and task.get('username') == username:
                    del all_tasks[i]
                    _save_data(all_tasks, TASKS_FILE)
                    return True
                    
            return False
        
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