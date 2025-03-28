# AI-Powered Task Management Web App

A smart task management system that leverages artificial intelligence to provide personalized task recommendations, productivity insights, and motivational support.

## 🌟 Key Features

### Task Management
- Create, update, and delete tasks with priority levels
- Set due dates and times for tasks
- Mark tasks as completed or in progress
- Organize tasks by priority (high, medium, low)
- Task categorization and filtering

### AI Integration
- **Smart Task Recommendations**: Get personalized task suggestions based on your goals
- **Procrastination Analysis**: AI-powered insights into your task completion patterns
- **Personalized Motivation**: Dynamic motivational content that adapts to your progress
- **Sentiment-Based Advice**: Contextual advice based on your task completion status
- **Daily Inspirational Quotes**: AI-generated quotes to boost productivity

### Analytics & Insights
- Task completion statistics
- Priority-based completion rates
- Procrastination pattern detection
- Visual progress tracking
- Calendar view for task scheduling

### User Experience
- Responsive, modern UI with Bootstrap 5
- Interactive calendar interface
- Real-time task updates
- Personalized dashboard
- Secure user authentication

## 🛠️ Technology Stack

### Backend
- **Framework**: FastAPI (Python)
- **Database**: AWS DynamoDB (with JSON file fallback)
- **Authentication**: JWT token-based
- **AI Integration**: OpenAI GPT-4 via LangChain
- **API Documentation**: FastAPI automatic docs

### Frontend
- **Framework**: Bootstrap 5
- **Styling**: Custom CSS
- **JavaScript**: Vanilla JS
- **Icons**: Bootstrap Icons
- **Calendar**: FullCalendar.js

### AI Features
- Task recommendation generation
- Procrastination pattern analysis
- Motivational content generation
- Sentiment-based advice
- Dynamic daily quotes

## 🚀 Setup and Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/task-management-system.git
   cd task-management-system
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv venv
   # On Windows
   .\venv\Scripts\activate
   # On Unix or MacOS
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Create a `.env` file with:
   ```
   OPENAI_API_KEY=your_openai_api_key
   AWS_ACCESS_KEY_ID=your_aws_access_key_id
   AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
   AWS_REGION=your_aws_region
   SECRET_KEY=your_jwt_secret_key
   ```

5. **Run the application**:
   ```bash
   python app.py
   ```

6. **Access the application**:
   - Main application: `http://127.0.0.1:8000`
   - API documentation: `http://127.0.0.1:8000/docs`

## 📱 Usage Guide

### Getting Started
1. Register for a new account or log in
2. Navigate to the dashboard
3. Start by adding your first task

### Task Management
1. **Adding Tasks**:
   - Click "Add New Task"
   - Fill in task details (title, description, priority, due date)
   - Set reminders if needed

2. **Managing Tasks**:
   - View tasks in list or calendar view
   - Mark tasks as complete
   - Edit task details
   - Delete tasks

3. **AI Recommendations**:
   - Enter your goal or task description
   - Get AI-generated task suggestions
   - Review and add recommended tasks

### Using the Calendar
1. Switch to calendar view
2. View tasks by day, week, or month
3. Drag and drop tasks to reschedule
4. Click on events to view/edit details

### Productivity Insights
1. View your task completion statistics
2. Check procrastination analysis
3. Read personalized motivational advice
4. Track your progress over time

## 🔒 Security Features

- JWT token-based authentication
- Password hashing
- Secure session management
- Protected API endpoints
- Environment variable protection

## 📊 Data Storage

- Primary: AWS DynamoDB
- Fallback: Local JSON storage
- Automatic data synchronization
- Backup and recovery options

## 🙏 Acknowledgments

- OpenAI for GPT-4 API
- FastAPI team for the excellent framework
- Bootstrap team for the UI components
- All contributors and users of the system
