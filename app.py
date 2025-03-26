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
      "status": "pending"
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
        tasks = db.get_user_tasks(username)
        task_stats = db.get_task_stats(username)
        
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "username": username,
                "tasks": tasks,
                "task_history": task_stats
            }
        )
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

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

@app.get("/tasks")
async def get_tasks(request: Request):
    try:
        current_user = await get_current_user(request)
        username = current_user["username"]
        return db.get_user_tasks(username)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

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

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True) 