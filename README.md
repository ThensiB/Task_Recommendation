# Task Recommendation System

A personalized task management system that uses AI to recommend tasks based on user goals and preferences.

## Features

- **AI-Powered Task Recommendations**: Get personalized task suggestions based on your goals and existing tasks
- **User Authentication**: Secure login and registration system
- **Task Management**: Mark tasks as completed or in progress
- **Statistics**: View your task completion statistics and history
- **DynamoDB Integration**: Cloud storage capabilities with AWS DynamoDB (with local storage fallback)

## Technology Stack

- **Backend**: FastAPI, Python
- **Frontend**: HTML, CSS, JavaScript
- **Database**: AWS DynamoDB (with JSON file fallback)
- **AI**: OpenAI GPT-4 via LangChain
- **Authentication**: JWT token-based authentication

## Setup and Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/task-recommender.git
   cd task-recommender
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with the following variables:
   ```
   OPENAI_API_KEY=your_openai_api_key
   AWS_ACCESS_KEY_ID=your_aws_access_key_id
   AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
   AWS_REGION=your_aws_region
   SECRET_KEY=your_jwt_secret_key
   ```

4. Run the application:
   ```bash
   python app.py
   ```

5. Access the application at `http://127.0.0.1:8000`

## Usage

1. Register for an account or log in
2. Enter a task goal in the input field
3. Click "Get Task Recommendations" to receive AI-generated task suggestions
4. View and manage your tasks on the dashboard
5. Mark tasks as completed as you progress

## Notes

- If AWS DynamoDB credentials are not provided or invalid, the system will automatically fall back to local JSON file storage
- This application is designed for demonstration and learning purposes