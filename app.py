from fastapi import FastAPI, Request, Form, HTTPException, Depends, status, Cookie
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os
import json
from datetime import datetime, timedelta
from json_cleaner import clean_json_response
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import db
import auth
import traceback
from auth import Token, User, authenticate_user, create_access_token, get_current_user, get_password_hash
import uuid
import random

load_dotenv()

app = FastAPI(title="Task Recommendation System")

# Create templates and static directories if they don't exist
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Setup LangChain components
llm = ChatOpenAI(model='gpt-4')

# Function to get daily quote
async def get_daily_quote():
    prompt = """
    Generate an inspirational quote that will motivate someone to be productive and achieve their goals.
    The quote should be concise, memorable, and uplifting.
    Return the response in this exact JSON format:
    {
        "quote": "The quote text",
        "author": "Author name"
    }
    """
    try:
        response = await llm.ainvoke(prompt)
        return json.loads(response.content)
    except Exception as e:
        print(f"Error generating quote: {e}")
        return {"quote": "The only way to do great work is to love what you do.", "author": "Steve Jobs"}

# Function to get a random quote (not date-seeded)
async def get_random_quote():
    prompt = """
    Generate a unique and inspiring quote about productivity, success, or personal growth.
    The quote should be different from common motivational quotes.
    Return the response in this exact JSON format:
    {
        "quote": "The quote text",
        "author": "Author name"
    }
    """
    try:
        response = await llm.ainvoke(prompt)
        return json.loads(response.content)
    except Exception as e:
        print(f"Error generating random quote: {e}")
        return {"quote": "Success is not final, failure is not fatal: It is the courage to continue that counts.", "author": "Winston Churchill"}

# Function to generate personalized feedback based on user's task history
async def get_personalized_feedback(username):
    task_stats = db.get_task_stats(username)
    user_tasks = db.get_user_tasks(username)
    
    # Default feedback if no tasks are present
    if task_stats is None or isinstance(task_stats, str) or task_stats.get('total', 0) == 0:
        return {
            "message": "Welcome to your task dashboard! Start adding tasks to receive personalized feedback.",
            "type": "welcome",
            "completed_count": 0,
            "recent_tasks": []
        }
    
    # Get completed tasks
    completed_tasks = [task for task in user_tasks if task.get('status') == 'completed']
    completed_count = task_stats.get('completed', 0)
    
    # Sort completed tasks by most recent
    recent_completed = sorted(
        completed_tasks, 
        key=lambda x: x.get('task_id', ''), 
        reverse=True
    )[:3]  # Get the 3 most recent
    
    # Create prompt for personalized feedback
    prompt = f"""
    Based on the following task statistics and recent completed tasks, generate personalized feedback:
    
    Total Tasks: {task_stats.get('total', 0)}
    Completed Tasks: {completed_count}
    Pending Tasks: {task_stats.get('pending', 0)}
    
    Recent Completed Tasks:
    {json.dumps(recent_completed, indent=2)}
    
    Generate feedback that:
    1. Acknowledges their progress
    2. Provides specific encouragement based on their task completion patterns
    3. Suggests ways to improve productivity
    4. Includes a motivational message
    
    Return the response in this exact JSON format:
    {{
        "message": "Main feedback message",
        "type": "feedback_type (e.g., high_achiever, progress, consistency)",
        "completed_count": {completed_count},
        "recent_tasks": {json.dumps(recent_completed)}
    }}
    """
    
    try:
        response = await llm.ainvoke(prompt)
        return json.loads(response.content)
    except Exception as e:
        print(f"Error generating feedback: {e}")
        return {
            "message": "Keep up the good work! Your progress is showing.",
            "type": "general",
            "completed_count": completed_count,
            "recent_tasks": recent_completed
        }

# Function to analyze procrastination patterns based on task history
def analyze_procrastination_patterns(username):
    user_tasks = db.get_user_tasks(username)
    
    # Default response if not enough task data
    if not user_tasks or len(user_tasks) < 3:
        return {
            "has_patterns": False,
            "message": "Not enough task history to analyze patterns. Complete more tasks to see insights.",
            "recommendations": ["Continue completing tasks to generate insights."],
            "stats": {}
        }
    
    # Extract completed tasks
    completed_tasks = [task for task in user_tasks if task.get('status') == 'completed']
    pending_tasks = [task for task in user_tasks if task.get('status') == 'pending']
    
    if len(completed_tasks) < 2:
        return {
            "has_patterns": False,
            "message": "Complete more tasks to analyze procrastination patterns.",
            "recommendations": ["Mark tasks as complete when you finish them to build your history."],
            "stats": {
                "completed_count": len(completed_tasks),
                "pending_count": len(pending_tasks)
            }
        }
    
    # Analyze priority patterns
    high_priority_completed = [task for task in completed_tasks if task.get('priority') == 'high']
    medium_priority_completed = [task for task in completed_tasks if task.get('priority') == 'medium']
    low_priority_completed = [task for task in completed_tasks if task.get('priority') == 'low']
    
    high_priority_pending = [task for task in pending_tasks if task.get('priority') == 'high']
    
    # Calculate completion rates
    high_priority_total = len(high_priority_completed) + len([t for t in pending_tasks if t.get('priority') == 'high'])
    high_completion_rate = len(high_priority_completed) / high_priority_total if high_priority_total > 0 else 0
    
    medium_priority_total = len(medium_priority_completed) + len([t for t in pending_tasks if t.get('priority') == 'medium'])
    medium_completion_rate = len(medium_priority_completed) / medium_priority_total if medium_priority_total > 0 else 0
    
    low_priority_total = len(low_priority_completed) + len([t for t in pending_tasks if t.get('priority') == 'low'])
    low_completion_rate = len(low_priority_completed) / low_priority_total if low_priority_total > 0 else 0
    
    # Analyze overdue tasks
    current_date = datetime.now().date()
    overdue_tasks = [
        task for task in pending_tasks 
        if task.get('due_date') and datetime.strptime(task.get('due_date'), '%Y-%m-%d').date() < current_date
    ]
    
    # Identify procrastination patterns
    patterns = []
    recommendations = []
    
    # Pattern 1: More low priority tasks completed than high priority
    if (len(low_priority_completed) > len(high_priority_completed) and 
        high_priority_total > 0 and low_priority_total > 0):
        patterns.append("You tend to complete low-priority tasks before high-priority ones")
        recommendations.append("Try tackling high-priority tasks first thing in your day")
    
    # Pattern 2: Low completion rate for high priority tasks
    if high_completion_rate < 0.5 and high_priority_total >= 3:
        patterns.append("You complete less than half of your high-priority tasks")
        recommendations.append("Break down high-priority tasks into smaller, more manageable sub-tasks")
    
    # Pattern 3: Many overdue tasks
    if len(overdue_tasks) > 2:
        patterns.append(f"You have {len(overdue_tasks)} overdue tasks")
        recommendations.append("Set more realistic due dates or allocate specific time blocks for tasks")
    
    # Pattern 4: Completing easier tasks regardless of priority
    if (low_completion_rate > high_completion_rate and 
        medium_completion_rate > high_completion_rate and
        high_priority_total > 1):
        patterns.append("You tend to complete easier tasks first, regardless of priority")
        recommendations.append("Try the 'eat the frog' technique: tackle your most difficult task first")
    
    # Calculate average time to complete tasks by priority
    # This would require task completion timestamps
    avg_completion_time = {
        "high": "N/A",
        "medium": "N/A",
        "low": "N/A"
    }
    
    message = ""
    has_patterns = len(patterns) > 0
    
    if has_patterns:
        message = "Based on your task history, we've identified potential procrastination patterns."
    else:
        message = "Great job! We don't see obvious procrastination patterns in your task history."
        recommendations = ["Continue your current workflow, it's working well!"]
    
    if not recommendations:
        recommendations = ["Try the Pomodoro technique: 25 minutes of focused work followed by a 5-minute break"]
    
    stats = {
        "completed_tasks": {
            "high": len(high_priority_completed),
            "medium": len(medium_priority_completed),
            "low": len(low_priority_completed)
        },
        "completion_rates": {
            "high": round(high_completion_rate * 100),
            "medium": round(medium_completion_rate * 100),
            "low": round(low_completion_rate * 100)
        },
        "overdue_tasks": len(overdue_tasks),
        "patterns_detected": len(patterns)
    }
    
    return {
        "has_patterns": has_patterns,
        "message": message,
        "patterns": patterns,
        "recommendations": recommendations,
        "stats": stats
    }

# Function to generate personalized motivational advice based on procrastination patterns
async def generate_motivational_advice(username):
    procrastination_data = analyze_procrastination_patterns(username)
    user_tasks = db.get_user_tasks(username)
    
    # Default response if not enough data
    if not procrastination_data or not procrastination_data.get('patterns') or not user_tasks:
        return {
            "heading": "Ready to accomplish something today?",
            "main_advice": "Start with a small step on any task to build momentum.",
            "secondary_advice": [
                "Break large tasks into smaller parts.",
                "Eliminate distractions before you begin.",
                "Remember why this task matters to you."
            ],
            "incomplete_tasks": []
        }
    
    # Extract pending tasks and analyze completion patterns
    pending_tasks = [task for task in user_tasks if task.get('status') == 'pending']
    completed_tasks = [task for task in user_tasks if task.get('status') == 'completed']
    
    # Calculate completion rate and analyze sentiment
    total_tasks = len(user_tasks)
    completed_count = len(completed_tasks)
    completion_rate = completed_count / total_tasks if total_tasks > 0 else 0
    
    # Analyze overdue tasks
    current_date = datetime.now().date()
    overdue_tasks = [
        task for task in pending_tasks 
        if task.get('due_date') and datetime.strptime(task.get('due_date'), '%Y-%m-%d').date() < current_date
    ]
    
    # Determine sentiment based on completion patterns
    sentiment = "neutral"
    if completion_rate >= 0.8:
        sentiment = "celebratory"
    elif completion_rate >= 0.6:
        sentiment = "encouraging"
    elif len(overdue_tasks) > 2:
        sentiment = "urgent"
    elif completion_rate < 0.3:
        sentiment = "motivational"
    
    # Create prompt for personalized advice
    prompt = f"""
    Based on the following task statistics and patterns, generate personalized motivational advice:
    
    Completion Rate: {completion_rate:.1%}
    Total Tasks: {total_tasks}
    Completed Tasks: {completed_count}
    Pending Tasks: {len(pending_tasks)}
    Overdue Tasks: {len(overdue_tasks)}
    
    Sentiment to Use: {sentiment}
    
    Procrastination Patterns:
    {json.dumps(procrastination_data.get('patterns', []), indent=2)}
    
    Pending Tasks:
    {json.dumps(pending_tasks, indent=2)}
    
    Generate advice that:
    1. Uses the specified sentiment tone ({sentiment})
    2. Provides specific, actionable advice for completing pending tasks
    3. Addresses any procrastination patterns identified
    4. Includes task-specific recommendations
    5. Offers practical strategies for overcoming obstacles
    
    Return the response in this exact JSON format:
    {{
        "heading": "Motivational heading that matches the sentiment",
        "main_advice": "Primary piece of actionable advice",
        "secondary_advice": ["List of specific, actionable tips"],
        "task_specific": ["List of task-specific recommendations"],
        "incomplete_tasks": {json.dumps(pending_tasks[:3])}
    }}
    """
    
    try:
        response = await llm.ainvoke(prompt)
        return json.loads(response.content)
    except Exception as e:
        print(f"Error generating motivational advice: {e}")
        return {
            "heading": "Let's tackle those pending tasks!",
            "main_advice": "Break down your tasks into smaller, manageable steps.",
            "secondary_advice": [
                "Set specific time blocks for focused work.",
                "Eliminate distractions during work sessions.",
                "Take regular breaks to maintain energy."
            ],
            "task_specific": [],
            "incomplete_tasks": pending_tasks[:3]
        }

# Simplified JSON Schema for tasks
TASK_SCHEMA = """
{
  "tasks": [
    {
      "title": "Task title",
      "description": "Detailed description of the task",
      "priority": "high/medium/low",
      "estimated_duration": "estimated time to complete",
      "category": "optional category",
      "status": "pending",
      "due_date": "YYYY-MM-DD",
      "due_time": "HH:MM",
      "reminder": true/false
    }
  ],
  "reasoning": "Explanation of why these tasks are recommended",
  "next_steps": ["Suggested next step 1", "Suggested next step 2"]
}
"""

prompt_template = """
You are a task management assistant that helps users organize and prioritize their tasks.
Based on the user's input and existing task history, provide personalized task recommendations.
Consider the user's goals, priorities, and time constraints.

Each task should have a clear title, description, priority level (high, medium, or low), and estimated duration.

IMPORTANT: Return ONLY a valid JSON object with no extra text, markdown formatting, or code blocks.
Use exactly this JSON structure:

{schema}

USER QUERY: {query}
"""

# Create custom tools for file storage
class DbTool:
    def get_user_tasks(self, username):
        return db.get_user_tasks(username)
    
    def save_user_tasks(self, username, tasks):
        return db.save_tasks(username, tasks)
    
    def get_task_stats(self, username):
        return db.get_task_stats(username)

db_tool = DbTool()

class UserRegister(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    user = authenticate_user(username, password)
    if not user:
        return RedirectResponse(
            url=f"/login?error=Incorrect username or password",
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = None):
    return templates.TemplateResponse("register.html", {"request": request, "error": error})

@app.post("/register")
async def register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    # Check if passwords match
    if password != confirm_password:
        return RedirectResponse(
            url="/register?error=Passwords do not match",
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    # Check if username already exists
    existing_user = db.get_user(username)
    if existing_user:
        return RedirectResponse(
            url="/register?error=Username already exists",
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    # Create user
    hashed_password = get_password_hash(password)
    user = db.create_user(username, hashed_password, email)
    
    if not user:
        return RedirectResponse(
            url="/register?error=Failed to create user",
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        current_user = await get_current_user(request)
        username = current_user["username"]
        
        # Get today's inspirational quote
        daily_quote = await get_daily_quote()
        
        # Get personalized feedback
        feedback = await get_personalized_feedback(username)
        
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "username": username,
                "daily_quote": daily_quote,
                "feedback": feedback
            }
        )
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    try:
        current_user = await get_current_user(request)
        username = current_user["username"]
        
        # Get user details
        user_details = db.get_user(username)
        email = user_details.get("email", "")
        
        # Get task statistics
        task_stats = db.get_task_stats(username)
        
        return templates.TemplateResponse(
            "profile.html",
            {
                "request": request,
                "username": username,
                "email": email,
                "task_history": task_stats
            }
        )
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request):
    try:
        current_user = await get_current_user(request)
        username = current_user["username"]
        tasks = db.get_user_tasks(username)
        task_history = db.get_task_stats(username)
        procrastination = analyze_procrastination_patterns(username)
        
        # Get today's date in YYYY-MM-DD format
        today = datetime.now().strftime("%Y-%m-%d")
        
        return templates.TemplateResponse(
            "tasks.html",
            {
                "request": request,
                "username": username,
                "tasks": tasks,
                "task_history": task_history,
                "procrastination": procrastination,
                "today": today
            }
        )
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        raise e

@app.post("/recommend")
async def recommend_tasks(request: Request, query: str = Form(...)):
    try:
        current_user = await get_current_user(request)
        username = current_user["username"]
        
        # Get user's existing tasks to provide context
        tasks = db.get_user_tasks(username)
        task_context = ""
        if tasks:
            task_context = f"\n\nUser's existing tasks: {json.dumps(tasks)}\n"
        
        # Create the prompt with the task context
        full_prompt = prompt_template.format(
            schema=TASK_SCHEMA,
            query=query
        ) + task_context
        
        # Direct LLM call with simple context
        try:
            chat_completion = llm.invoke(full_prompt)
            output_text = chat_completion.content
            
            if not output_text or not output_text.strip():
                # Create a fallback response if LLM returns empty response
                fallback = {
                    "tasks": [{"title": "Review Request", "description": "Please try again with more details about what you'd like to work on.", 
                              "priority": "medium", "estimated_duration": "10 minutes", "status": "pending"}],
                    "reasoning": "I wasn't able to process your request properly. Could you provide more details?",
                    "next_steps": ["Try again with more specific information"]
                }
                return JSONResponse(content=fallback)
            
            # Clean the output to get valid JSON
            cleaned_json = clean_json_response(output_text)
            
            try:
                # Parse the JSON
                result = json.loads(cleaned_json)
                
                # Make sure tasks have required fields
                for task in result.get("tasks", []):
                    if "status" not in task:
                        task["status"] = "pending"
                
                # Save tasks
                db.save_tasks(username, result.get("tasks", []))
                
                return JSONResponse(content=result)
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                # Provide a fallback response
                fallback = {
                    "tasks": [{"title": "Try Again", "description": "I had trouble understanding your request. Could you rephrase it?", 
                            "priority": "medium", "estimated_duration": "5 minutes", "status": "pending"}],
                    "reasoning": "There was an issue with processing your request.",
                    "next_steps": ["Try a simpler or more specific request"]
                }
                return JSONResponse(content=fallback)
        except Exception as llm_error:
            print(f"LLM error: {str(llm_error)}")
            fallback = {
                "tasks": [{"title": "Service Issue", "description": "There was a temporary issue with the AI service. Please try again later.", 
                          "priority": "medium", "estimated_duration": "5 minutes", "status": "pending"}],
                "reasoning": "The service encountered a temporary issue.",
                "next_steps": ["Try again in a few moments"]
            }
            return JSONResponse(content=fallback)
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        raise e
    except Exception as e:
        print(f"Recommend error: {str(e)}")
        print(traceback.format_exc())
        fallback = {
            "tasks": [{"title": "System Error", "description": "There was an issue with processing your request.", 
                      "priority": "medium", "estimated_duration": "5 minutes", "status": "pending"}],
            "reasoning": "The system encountered an error. Please try again.",
            "next_steps": ["Try a different request"]
        }
        return JSONResponse(content=fallback)

@app.get("/api/tasks")
async def get_tasks(request: Request):
    try:
        current_user = await get_current_user(request)
        username = current_user["username"]
        return db.get_user_tasks(username)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/tasks")
async def add_task(request: Request, task: dict):
    try:
        current_user = await get_current_user(request)
        username = current_user["username"]
        
        # Add task_id if not present
        if "task_id" not in task:
            task["task_id"] = str(uuid.uuid4())
        
        # Ensure the task has a status
        if "status" not in task:
            task["status"] = "pending"
        
        # Handle due date and time
        if task.get("due_date") is None or task.get("due_date") == "":
            task["due_date"] = None
        if task.get("due_time") is None or task.get("due_time") == "":
            task["due_time"] = None
            
        # Ensure reminder field exists
        if "reminder" not in task:
            task["reminder"] = False
            
        # Save the task
        db.save_task(username, task)
        
        return {"status": "success", "message": "Task added successfully", "task": task}
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        raise e

@app.put("/update-task/{task_id}")
async def update_task(request: Request, task_id: str, task_data: dict):
    try:
        current_user = await get_current_user(request)
        username = current_user["username"]
        
        # Verify task belongs to the user
        tasks = db.get_user_tasks(username)
        task_exists = any(task["task_id"] == task_id for task in tasks)
        
        if not task_exists:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Update the task
        task_data["task_id"] = task_id  # Ensure task_id is in the data
        success = db.update_task(username, task_id, task_data)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update task")
            
        return {"status": "success", "message": "Task updated successfully"}
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        raise e

@app.delete("/delete-task/{task_id}")
async def delete_task(request: Request, task_id: str):
    try:
        current_user = await get_current_user(request)
        username = current_user["username"]
        
        # Verify task belongs to the user
        tasks = db.get_user_tasks(username)
        task_exists = any(task["task_id"] == task_id for task in tasks)
        
        if not task_exists:
            raise HTTPException(status_code=404, detail="Task not found")
            
        # Delete the task
        success = db.delete_task(username, task_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete task")
            
        return {"status": "success", "message": "Task deleted successfully"}
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        raise e

@app.post("/prioritize-tasks")
async def prioritize_tasks(request: Request):
    try:
        current_user = await get_current_user(request)
        username = current_user["username"]
        
        # Get user tasks
        tasks = db.get_user_tasks(username)
        
        if not tasks:
            return {"status": "success", "message": "No tasks to prioritize"}
        
        # Only prioritize pending tasks
        pending_tasks = [task for task in tasks if task["status"] == "pending"]
        
        if not pending_tasks:
            return {"status": "success", "message": "No pending tasks to prioritize"}
        
        # Prioritize - Simple algorithm that assigns high priority to the first 1/3 of tasks,
        # medium to the middle 1/3, and low to the last 1/3
        task_count = len(pending_tasks)
        high_count = max(1, int(task_count * 0.33))
        medium_count = max(1, int(task_count * 0.33))
        
        for i, task in enumerate(pending_tasks):
            if i < high_count:
                task["priority"] = "high"
            elif i < high_count + medium_count:
                task["priority"] = "medium"
            else:
                task["priority"] = "low"
        
        # Update all tasks
        for task in pending_tasks:
            db.update_task(username, task["task_id"], task)
            
        return {"status": "success", "message": "Tasks prioritized successfully"}
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        raise e

@app.post("/complete-task/{task_id}")
async def complete_task(request: Request, task_id: str):
    try:
        current_user = await get_current_user(request)
        username = current_user["username"]
        
        # Verify task belongs to the user
        tasks = db.get_user_tasks(username)
        task_exists = any(task["task_id"] == task_id for task in tasks)
        
        if not task_exists:
            raise HTTPException(status_code=404, detail="Task not found")
            
        response = db.update_task_status(task_id, "completed")
        if not response:
            raise HTTPException(status_code=500, detail="Failed to update task")
            
        return {"status": "success", "message": "Task marked as completed"}
    except HTTPException as e:
        if e.status_code == 401:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        raise e

@app.get("/api/quote/daily")
async def api_daily_quote(request: Request):
    """Endpoint to get the daily quote"""
    try:
        # Check if user is authenticated
        await get_current_user(request)
        return await get_daily_quote()
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/api/quote/random")
async def api_random_quote(request: Request):
    """Endpoint to get a random quote"""
    try:
        # Check if user is authenticated
        await get_current_user(request)
        return await get_random_quote()
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/api/feedback")
async def api_feedback(request: Request):
    """Endpoint to get personalized feedback"""
    try:
        # Check if user is authenticated
        current_user = await get_current_user(request)
        username = current_user["username"]
        return await get_personalized_feedback(username)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/api/procrastination")
async def api_procrastination(request: Request):
    """Endpoint to get procrastination analysis"""
    try:
        # Check if user is authenticated
        current_user = await get_current_user(request)
        username = current_user["username"]
        return analyze_procrastination_patterns(username)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/api/motivation")
async def api_motivation(request: Request):
    """Endpoint to get personalized motivational advice"""
    try:
        # Check if user is authenticated
        current_user = await get_current_user(request)
        username = current_user["username"]
        return await generate_motivational_advice(username)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/calendar", response_class=HTMLResponse)
async def calendar_page(request: Request):
    try:
        current_user = await get_current_user(request)
        username = current_user["username"]
        
        return templates.TemplateResponse(
            "calendar.html",
            {
                "request": request,
                "username": username
            }
        )
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/api/tasks/calendar")
async def get_calendar_tasks(request: Request):
    try:
        current_user = await get_current_user(request)
        username = current_user["username"]
        tasks = db.get_user_tasks(username)
        
        # Convert tasks to calendar events
        events = []
        for task in tasks:
            if task.get("due_date"):  # Only include tasks with due dates
                event = {
                    "id": task.get("task_id"),
                    "title": task.get("title"),
                    "start": task.get("due_date"),
                    "end": task.get("due_date"),  # For now, using same date for end
                    "className": f"{task.get('priority', 'medium')}-priority-event",
                    "extendedProps": {
                        "description": task.get("description", ""),
                        "priority": task.get("priority", "medium"),
                        "status": task.get("status", "pending"),
                        "estimated_duration": task.get("estimated_duration", "")
                    }
                }
                
                if task.get("status") == "completed":
                    event["className"] += " completed-event"
                
                if task.get("due_time"):
                    event["start"] = f"{task.get('due_date')}T{task.get('due_time')}"
                    event["end"] = f"{task.get('due_date')}T{task.get('due_time')}"
                
                events.append(event)
        
        return events
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/api/tasks/{task_id}")
async def get_task_details(request: Request, task_id: str):
    try:
        current_user = await get_current_user(request)
        username = current_user["username"]
        tasks = db.get_user_tasks(username)
        
        task = next((task for task in tasks if task.get("task_id") == task_id), None)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return task
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True) 