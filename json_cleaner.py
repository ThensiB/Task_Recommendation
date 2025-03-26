import re
import json

def clean_json_response(response):
    """Clean the response to extract just the JSON object"""
    # Remove markdown code blocks if present
    response = re.sub(r"```(?:json)?[\s\n]*|```[\s\n]*$", "", response)
    
    # Try to extract JSON if there's surrounding text
    json_start = response.find("{")
    json_end = response.rfind("}")
    
    if json_start >= 0 and json_end >= 0:
        response = response[json_start:json_end+1]
    
    # Additional cleanup
    response = response.strip()
    
    # Validate that the result is valid JSON
    try:
        json.loads(response)
        return response
    except json.JSONDecodeError:
        # Return a minimal valid JSON if parsing fails
        return json.dumps({
            "tasks": [
                {
                    "title": "Default Task", 
                    "description": "Please try a more specific request", 
                    "priority": "medium", 
                    "estimated_duration": "10 minutes"
                }
            ], 
            "reasoning": "I had trouble understanding that request.", 
            "next_steps": ["Try a simpler request"]
        }) 