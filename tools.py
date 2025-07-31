import httpx
from livekit.agents import function_tool
import os
from datetime import datetime
from typing import Optional, List
from utils import format_time_for_db, validate_user_id

# The URL of the MCP server (configurable for deployment)
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")

# Global variables to store the correct user_id and call_id
CORRECT_USER_ID = None
CORRECT_CALL_ID = None

def set_correct_ids(user_id: str, call_id: str) -> None:
    """Set the correct user_id and call_id to be used by all tools"""
    global CORRECT_USER_ID, CORRECT_CALL_ID
    CORRECT_USER_ID = user_id
    CORRECT_CALL_ID = call_id
    print(f"DEBUG: Set correct IDs - user_id: {user_id}, call_id: {call_id}")

async def call_mcp_endpoint(endpoint: str, data: dict, user_id: str = None, call_id: str = None) -> dict:
    """Call an MCP endpoint with the correct user_id and call_id"""
    global CORRECT_USER_ID, CORRECT_CALL_ID
    
    # Use the correct IDs if available, otherwise use the provided ones
    actual_user_id = CORRECT_USER_ID if CORRECT_USER_ID else user_id
    actual_call_id = CORRECT_CALL_ID if CORRECT_CALL_ID else call_id
    
    # Validate user_id
    validated_user_id = None
    try:
        if actual_user_id:
            validated_user_id = validate_user_id(actual_user_id)
        else:
            print("WARNING: No user_id provided for MCP call")
    except ValueError:
        print(f"WARNING: Invalid user_id format: {actual_user_id}")
        # Try to use the global ID directly without validation
        if CORRECT_USER_ID:
            try:
                validated_user_id = validate_user_id(CORRECT_USER_ID)
                print(f"Using global user_id instead: {CORRECT_USER_ID}")
            except ValueError:
                print(f"WARNING: Global user_id is also invalid: {CORRECT_USER_ID}")
                # Use the raw value as a last resort
                validated_user_id = CORRECT_USER_ID
    
    # Make the API call
    async with httpx.AsyncClient() as client:
        headers = {}
        if validated_user_id:
            headers["X-User-Id"] = validated_user_id
        if actual_call_id:
            headers["X-Call-Id"] = actual_call_id
        
        response = await client.post(
            f"{MCP_SERVER_URL}/{endpoint}",
            json=data,
            headers=headers
        )
        response.raise_for_status()
        return response.json()

@function_tool
async def schedule_appointment(patient_name: str, assigned_doctor: str, appointment_date: str, appointment_time: str, appointment_reason: str, user_id: str = None, call_id: str = None) -> str:
    """
    Schedules an appointment for a patient with a doctor.
    """
    # Format time consistently before sending to server
    formatted_time = format_time_for_db(appointment_time)
    
    # Call the MCP endpoint with the correct user_id and call_id
    response = await call_mcp_endpoint(
        "schedule_appointment",
        {
            "patient_name": patient_name,
            "assigned_doctor": assigned_doctor,
            "appointment_date": appointment_date,
            "appointment_time": formatted_time,  # Using formatted time in HH:MM:SS format
            "appointment_reason": appointment_reason,
        },
        user_id=user_id,
        call_id=call_id
    )
    
    result = response["result"]
    
    print(f"DEBUG (schedule_appointment): Function called, result: {result}")
    
    # Update appointment status if we have access to the context
    print(f"DEBUG (schedule_appointment): Checking for CURRENT_CALL_CONTEXT...")
    print(f"DEBUG (schedule_appointment): globals() has CURRENT_CALL_CONTEXT: {hasattr(globals(), 'CURRENT_CALL_CONTEXT')}")
    print(f"DEBUG (schedule_appointment): CURRENT_CALL_CONTEXT value: {globals().get('CURRENT_CALL_CONTEXT')}")
    
    if hasattr(globals(), 'CURRENT_CALL_CONTEXT') and globals().get('CURRENT_CALL_CONTEXT'):
        ctx = globals()['CURRENT_CALL_CONTEXT']
        result_str = str(result).lower()
        print(f"DEBUG (schedule_appointment): Tool returned: {result}")
        print(f"DEBUG (schedule_appointment): Result string for analysis: '{result_str}'")
        
        # Check each condition separately for debugging
        has_successfully = "successfully" in result_str
        has_appointment_scheduled = "appointment scheduled successfully" in result_str
        no_however = "however" not in result_str
        no_openings = "openings at" not in result_str
        
        print(f"DEBUG (schedule_appointment): Conditions - successfully: {has_successfully}, appointment_scheduled: {has_appointment_scheduled}, no_however: {no_however}, no_openings: {no_openings}")
        
        # Only mark as booked if the appointment was actually scheduled, not just when alternative times are suggested
        if has_successfully and has_appointment_scheduled and no_however and no_openings:
            ctx.appointment_status = 'Booked'
            print(f"DEBUG (schedule_appointment): Updated appointment_status to 'Booked'")
        else:
            print(f"DEBUG (schedule_appointment): Appointment not actually booked - response suggests alternatives or failure")
    
    return result

@function_tool
async def check_availability(doctor_name: str, appointment_date: str, appointment_time: str, user_id: str = None, call_id: str = None) -> str:
    """
    Checks the availability of a doctor at a specific time.
    """
    # Format time consistently before sending to server
    formatted_time = format_time_for_db(appointment_time)
    
    # Call the MCP endpoint with the correct user_id and call_id
    response = await call_mcp_endpoint(
        "check_availability",
        {
            "doctor_name": doctor_name,
            "appointment_date": appointment_date,
            "appointment_time": formatted_time
        },
        user_id=user_id,
        call_id=call_id
    )
    
    return response["result"]

@function_tool
async def reschedule_appointment(appointment_id: str, new_date: str, new_time: str, user_id: str = None, call_id: str = None) -> str:
    """
    Reschedules an existing appointment.
    """
    # Format time consistently before sending to server
    formatted_time = format_time_for_db(new_time)
    
    # Call the MCP endpoint with the correct user_id and call_id
    response = await call_mcp_endpoint(
        "reschedule_appointment",
        {
            "appointment_id": appointment_id,
            "new_date": new_date,
            "new_time": formatted_time
        },
        user_id=user_id,
        call_id=call_id
    )
    
    result = response["result"]
    
    # Update appointment status if we have access to the context
    if hasattr(globals(), 'CURRENT_CALL_CONTEXT') and globals().get('CURRENT_CALL_CONTEXT'):
        ctx = globals()['CURRENT_CALL_CONTEXT']
        result_str = str(result).lower()
        print(f"DEBUG (reschedule_appointment): Tool returned: {result}")
        if "successfully" in result_str:
            ctx.appointment_status = 'Rescheduled'
            print(f"DEBUG (reschedule_appointment): Updated appointment_status to 'Rescheduled'")
    
    return result

@function_tool
async def cancel_appointment(appointment_id: str, user_id: str = None, call_id: str = None) -> str:
    """
    Cancels an existing appointment.
    """
    # Call the MCP endpoint with the correct user_id and call_id
    response = await call_mcp_endpoint(
        "cancel_appointment",
        {"appointment_id": appointment_id},
        user_id=user_id,
        call_id=call_id
    )
    
    result = response["result"]
    
    # Update appointment status if we have access to the context
    if hasattr(globals(), 'CURRENT_CALL_CONTEXT') and globals().get('CURRENT_CALL_CONTEXT'):
        ctx = globals()['CURRENT_CALL_CONTEXT']
        result_str = str(result).lower()
        print(f"DEBUG (cancel_appointment): Tool returned: {result}")
        if "successfully" in result_str:
            ctx.appointment_status = 'Cancelled'
            print(f"DEBUG (cancel_appointment): Updated appointment_status to 'Cancelled'")
    
    return result

@function_tool
async def get_doctor_details_for_user(user_id: str = None, call_id: str = None) -> list:
    """
    Fetches the doctor details for a given user_id.
    """
    # Call the MCP endpoint with the correct user_id and call_id
    response = await call_mcp_endpoint(
        "get_doctor_details_for_user",
        {},
        user_id=user_id,
        call_id=call_id
    )
    
    return response["result"]

@function_tool
async def add_call_history(
    caller_number: str,
    called_number: str,
    call_start: str,
    call_end: str,
    call_duration: str,
    call_status: str,
    appointment_status: str,
    call_summary: str,
    user_id: str = None,
    call_id: str = None,
) -> str:
    """
    Adds a call history record to the database.
    """
    # Keep datetime strings as-is for call history (they're already in ISO format)
    # Don't use format_time_for_db for datetime fields, only for time fields
    formatted_call_start = call_start
    formatted_call_end = call_end
    
    # Call the MCP endpoint with the correct user_id and call_id
    response = await call_mcp_endpoint(
        "add_call_history",
        {
            "caller_number": caller_number,
            "called_number": called_number,
            "call_start": formatted_call_start,
            "call_end": formatted_call_end,
            "call_duration": call_duration,
            "call_status": call_status,
            "appointment_status": appointment_status,
            "call_summary": call_summary,
        },
        user_id=user_id,
        call_id=call_id
    )
    
    return response["result"]

@function_tool
async def call_mcp(tool_name: str, args: dict) -> dict:
    """
    Calls an MCP tool dynamically.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{MCP_SERVER_URL}/{{tool_name}}",
            json=args,
        )
        response.raise_for_status()
        return response.json()

@function_tool
async def get_available_slots(doctor_name: str, appointment_date: str, user_id: str = None, call_id: str = None) -> list:
    """
    Fetches available 30-minute appointment slots for a given doctor on a specific date.
    """
    # Call the MCP endpoint with the correct user_id and call_id
    response = await call_mcp_endpoint(
        "get_available_slots",
        {
            "doctor_name": doctor_name,
            "appointment_date": appointment_date,
        },
        user_id=user_id,
        call_id=call_id
    )
    
    return response["result"]

@function_tool
def get_today_date() -> str:
    """
    Returns the current date in YYYY-MM-DD format.
    """
    return datetime.now().strftime("%Y-%m-%d")

@function_tool
async def summarize_call(transcript: str) -> str:
    """
    Summarizes a given conversation transcript using an LLM.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{MCP_SERVER_URL}/summarize_call",
            json={
                "transcript": transcript,
            },
        )
        response.raise_for_status()
        return response.json()["result"]

@function_tool
async def get_appointment_details(patient_name: str, user_id: str = None, call_id: str = None, assigned_doctor: Optional[str] = None, appointment_date: Optional[str] = None) -> List[dict]:
    """
    Fetches appointment details based on patient name, doctor, and date.
    """
    # Call the MCP endpoint with the correct user_id and call_id
    response = await call_mcp_endpoint(
        "get_appointment_details",
        {
            "patient_name": patient_name,
            "assigned_doctor": assigned_doctor,
            "appointment_date": appointment_date,
        },
        user_id=user_id,
        call_id=call_id
    )
    
    return response["result"]

@function_tool
async def list_appointments_for_patient(patient_name: str, user_id: str = None, call_id: str = None) -> List[dict]:
    """
    Lists all upcoming appointments for a given patient.
    """
    # Call the MCP endpoint with the correct user_id and call_id
    response = await call_mcp_endpoint(
        "list_appointments_for_patient",
        {
            "patient_name": patient_name,
        },
        user_id=user_id,
        call_id=call_id
    )
    
    return response["result"]

@function_tool
async def get_user_id_by_agent_phone(agent_phone: str, call_id: str = None) -> Optional[str]:
    """
    Fetches the user_id associated with a given agent_phone from user_settings.
    """
    try:
        # This function doesn't need a user_id since it's used to get the user_id
        response = await call_mcp_endpoint(
            "get_user_id_by_agent_phone",
            {
                "agent_phone": agent_phone,
            },
            user_id=None,
            call_id=call_id
        )
        
        if response and "result" in response:
            return response["result"]
        else:
            print(f"No user_id found for agent_phone: {agent_phone}")
            return None
    except Exception as e:
        print(f"Error getting user_id by agent phone: {e}")
        return None

@function_tool
async def get_user_settings(user_id: str = None, call_id: str = None) -> Optional[dict]:
    """
    Fetches the entire user settings object for a given user_id.
    """
    # Call the MCP endpoint with the correct user_id and call_id
    response = await call_mcp_endpoint(
        "get_user_settings",
        {},
        user_id=user_id,
        call_id=call_id
    )
    
    return response["result"]