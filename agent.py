import re
import asyncio
from dotenv import load_dotenv
from livekit.agents import JobContext, WorkerOptions, cli, AgentSession, Agent, RoomInputOptions
from livekit.plugins import noise_cancellation, google
from prompts import AGENT_INSTRUCTION_TEMPLATE, SESSION_INSTRUCTION
from tools import (
    schedule_appointment,
    check_availability,
    reschedule_appointment,
    cancel_appointment,
    get_available_slots,
    get_today_date,
    add_call_history,
    call_mcp,
    get_doctor_details_for_user,
    get_user_id_by_agent_phone,
    get_appointment_details,
    list_appointments_for_patient,
    get_user_settings,
    set_correct_ids,
    summarize_call  # Keep import for internal use only
)
from datetime import datetime, timedelta # Import timedelta
import pytz # Import pytz
from typing import Any
import os

# Define Indian Standard Time (IST) timezone
IST = pytz.timezone('Asia/Kolkata')

load_dotenv()

def generate_fallback_summary(appointment_status: str, conversation_text: str = "") -> str:
    """Generate a fallback summary based on appointment status and conversation context"""
    
    # Base summary based on appointment status
    if appointment_status == "Booked":
        base_summary = "Patient called and successfully scheduled an appointment"
    elif appointment_status == "Rescheduled":
        base_summary = "Patient called and rescheduled an existing appointment"
    elif appointment_status == "Cancelled":
        base_summary = "Patient called and cancelled an appointment"
    else:
        base_summary = "Patient called the clinic"
    
    # Try to extract additional context from conversation
    if conversation_text:
        conversation_lower = conversation_text.lower()
        
        # Look for doctor names or specialties mentioned
        if "doctor" in conversation_lower or "dr." in conversation_lower:
            if "appointment" in conversation_lower:
                if appointment_status == "Booked":
                    return f"{base_summary} with a doctor"
                elif appointment_status == "Rescheduled":
                    return f"{base_summary} to a new time"
                elif appointment_status == "Cancelled":
                    return f"{base_summary} with a doctor"
        
        # Look for specific inquiries
        if "available" in conversation_lower or "slot" in conversation_lower:
            return f"{base_summary} and inquired about available appointment slots"
        elif "timing" in conversation_lower or "hours" in conversation_lower:
            return f"{base_summary} and asked about clinic timings"
        elif "address" in conversation_lower or "location" in conversation_lower:
            return f"{base_summary} and asked for clinic address"
    
    return base_summary + "."

def extract_call_context(ctx: Any) -> dict:
    """Extracts call_id, job_id, caller_number, called_number, call_start from context."""
    call_id = getattr(ctx.job, 'id', None)
    room_obj = getattr(ctx, 'room', None)
    room_name = getattr(room_obj, 'name', None) if room_obj else None
    caller_number = None
    if room_name:
        match = re.match(r"call-_([+0-9]+)_", room_name)
        if match:
            caller_number = match.group(1)
    # The called_number should ideally come from LiveKit context, but for now, use env var as fallback
    called_number = os.getenv("CLINIC_PHONE_NUMBER", "+912269539733") # This will be replaced by actual LiveKit data
    call_start = IST.localize(datetime.now()) # Use IST for call_start
    job_id = getattr(ctx.job, "id", None)

    return {
        "call_id": call_id,
        "caller_number": caller_number,
        "called_number": called_number,
        "call_start": call_start,
        "job_id": job_id
    }

class ClinicReceptionistAgent(Agent):
    def __init__(self, instructions: str, user_id: str, call_id: str, ctx=None) -> None:
        self.correct_user_id = user_id
        self.correct_call_id = call_id
        self._ctx = ctx
        
        super().__init__(
            instructions=instructions,
            llm=google.beta.realtime.RealtimeModel(
                voice="puck",
                temperature=0.8,
            ),
            tools = [
                schedule_appointment,
                check_availability,
                reschedule_appointment,
                cancel_appointment,
                get_available_slots,
                get_today_date,
                get_doctor_details_for_user,
                get_user_id_by_agent_phone,
                get_appointment_details,
                list_appointments_for_patient,
                get_user_settings
            ]
        )
    
    async def execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """Override the execute_tool method to fix user_id and call_id"""
        print(f"AGENT DEBUG: execute_tool called with tool_name='{tool_name}'")
        print(f"AGENT DEBUG: execute_tool called with args: {tool_args}")
        
        # Always use the correct user_id and call_id
        if 'user_id' in tool_args:
            original_user_id = tool_args['user_id']
            # Check for placeholder values or incorrect values
            if original_user_id != self.correct_user_id or original_user_id == "<user_id>" or original_user_id.startswith("123e4567"):
                tool_args['user_id'] = self.correct_user_id
        else:
            # If user_id is missing, add it
            tool_args['user_id'] = self.correct_user_id
        
        if 'call_id' in tool_args:
            original_call_id = tool_args['call_id']
            # Check for placeholder values or incorrect values
            if original_call_id != self.correct_call_id or original_call_id == "<call_id>" or original_call_id.isdigit():
                tool_args['call_id'] = self.correct_call_id
        else:
            # If call_id is missing, add it
            tool_args['call_id'] = self.correct_call_id
        
        # Call the parent method to execute the tool
        result = await super().execute_tool(tool_name, tool_args)
        
        # Check tool results and update appointment status
        result_str = str(result).lower()
        print(f"DEBUG (execute_tool): Tool '{tool_name}' returned: {result}")
        print(f"DEBUG (execute_tool): Result string (lowercase): {result_str}")
        
        if hasattr(self, '_ctx') and self._ctx:
            if tool_name == 'schedule_appointment':
                print(f"DEBUG (execute_tool): Schedule appointment result: '{result_str}'")
                
                # Check each condition separately for debugging
                has_successfully = "successfully" in result_str
                has_appointment_scheduled = "appointment scheduled successfully" in result_str
                no_however = "however" not in result_str
                no_openings = "openings at" not in result_str
                
                print(f"DEBUG (execute_tool): Conditions - successfully: {has_successfully}, appointment_scheduled: {has_appointment_scheduled}, no_however: {no_however}, no_openings: {no_openings}")
                
                if has_successfully and has_appointment_scheduled and no_however and no_openings:
                    self._ctx.appointment_status = 'Booked'
                    print(f"DEBUG (execute_tool): Updated appointment_status to 'Booked'")
                else:
                    print(f"DEBUG (execute_tool): Appointment not actually booked - response suggests alternatives or failure")
            elif tool_name == 'reschedule_appointment' and "successfully" in result_str:
                self._ctx.appointment_status = 'Rescheduled'
                print(f"DEBUG (execute_tool): Updated appointment_status to 'Rescheduled'")
            elif tool_name == 'cancel_appointment' and "successfully" in result_str:
                self._ctx.appointment_status = 'Cancelled'
                print(f"DEBUG (execute_tool): Updated appointment_status to 'Cancelled'")
        else:
            print(f"DEBUG (execute_tool): No context available to update appointment status")
        
        return result

async def entrypoint(ctx: JobContext) -> None:
    # --- Extract call metadata from LiveKit context ---
    context_info = extract_call_context(ctx)
    ctx.call_id = context_info["call_id"]
    ctx.caller_number = context_info["caller_number"]
    ctx.called_number = context_info["called_number"]
    ctx.call_start = context_info["call_start"]
    if context_info["job_id"]:
        ctx.job_id = context_info["job_id"]
    session = AgentSession()

    # --- Get user_id based on called_number ---
    user_id = await get_user_id_by_agent_phone(ctx.called_number, call_id=ctx.call_id)
    if not user_id:
        print(f"Error: No user_id found for called_number: {ctx.called_number}")
        # Generate a user-friendly message and potentially end the session
        session_instruction = "I'm sorry, I can't find your clinic's settings based on the number you're calling from. Please ensure you're calling from a registered number or contact support for assistance."
        await session.generate_reply(instructions=session_instruction)
        # For now, we'll proceed with a default user_id for logging, but in a real scenario, you might want to end the call here.
        ctx.user_id = "default_user_id" # Fallback for logging
    else:
        ctx.user_id = user_id
    # --- Set the correct user_id and call_id for all tool calls ---
    set_correct_ids(ctx.user_id, ctx.call_id)
    
    # --- Fetch doctor details before agent speaks ---
    doctor_details = await get_doctor_details_for_user(ctx.user_id, call_id=ctx.call_id)
    doctor_names = [d.get("name") for d in doctor_details]

    # --- Inject doctor names into the prompt/context for the LLM ---
    doctor_list_str = ', '.join(doctor_names)
    doctor_prompt = f"\n\n# Available doctors: {doctor_list_str}\nAlways use ONLY these names for doctor selection, prompts, and tool calls. Never invent or use any other doctor name."

    # --- Inject current date and clinic details into prompts ---
    today = datetime.now(IST).strftime("%Y-%m-%d") # Use IST for today's date
    clinic_details = {
        "clinic_name": os.getenv("CLINIC_NAME", "Syraa Multispeciality Clinic"),
        "clinic_address": os.getenv("CLINIC_ADDRESS", "123 MG Road, Bengaluru, Karnataka 560001"),
        "clinic_timings": os.getenv("CLINIC_TIMINGS", "Monday to Saturday, 9:00 AM to 7:00 PM; Sunday closed"),
        "clinic_phone": os.getenv("CLINIC_PHONE", "+91-98765-43210"),
        "clinic_services": os.getenv("CLINIC_SERVICES", "General Medicine, Pediatrics, Endocrinology, Cardiology, Diagnostics, Vaccinations, Health Checkups"),
    }
    agent_instruction = AGENT_INSTRUCTION_TEMPLATE.format(**clinic_details) + f"\n\n# Today's date: {today}\nAlways use this as the current date." + doctor_prompt
    session_instruction = f"{SESSION_INSTRUCTION}\n\n# Today's date: {today}\n" + doctor_prompt

    ctx.appointment_status = "Not Booked"

    # --- Tool call pre-processing hook ---
    orig_tool_call_handler = getattr(session, 'on_tool_call', None)
    async def tool_call_hook(tool_name, tool_args, *args, **kwargs):
        # Always use the correct user_id and call_id from context
        if 'user_id' in tool_args:
            tool_args['user_id'] = ctx.user_id
        
        if 'call_id' in tool_args:
            tool_args['call_id'] = ctx.call_id
        
        # Call the original handler if it exists
        if orig_tool_call_handler:
            return await orig_tool_call_handler(tool_name, tool_args, *args, **kwargs)
        return tool_args
    session.on_tool_call = tool_call_hook
    
    # --- Simple appointment status tracking using global state ---
    # Set up a global status tracker that tools can update
    import tools
    tools.CURRENT_CALL_CONTEXT = ctx  # Give tools access to the context
    
    # Initialize appointment status
    ctx.appointment_status = "Not Booked"
    print(f"DEBUG: Initialized appointment_status to: {ctx.appointment_status}")
    
    # --- Enhanced conversation capture for call summary ---
    ctx.conversation_log = []
    ctx.user_messages = []
    ctx.agent_responses = []
    ctx.tool_calls = []  # Track what tools were called
    
    def capture_transcript(transcript):
        print(f"DEBUG: Captured transcript: {transcript}")
        if hasattr(ctx, 'conversation_log'):
            ctx.conversation_log.append(transcript)
        setattr(ctx, "transcript", transcript)
    
    def capture_user_message(message):
        print(f"DEBUG: User said: {message}")
        if hasattr(ctx, 'user_messages'):
            ctx.user_messages.append(f"User: {message}")
    
    def capture_agent_response(response):
        print(f"DEBUG: Agent responded: {response}")
        if hasattr(ctx, 'agent_responses'):
            ctx.agent_responses.append(f"Agent: {response}")
    
    # Track tool usage for better summaries
    original_call_mcp_endpoint = tools.call_mcp_endpoint
    async def tracked_call_mcp_endpoint(endpoint: str, data: dict, user_id: str = None, call_id: str = None):
        result = await original_call_mcp_endpoint(endpoint, data, user_id, call_id)
        
        print(f"DEBUG (tracked_call_mcp_endpoint): Called {endpoint} with result: {result}")
        
        # Track tool calls for summary generation
        if hasattr(ctx, 'tool_calls'):
            if endpoint == "schedule_appointment":
                ctx.tool_calls.append(f"Scheduled appointment for {data.get('patient_name', 'patient')} with {data.get('assigned_doctor', 'doctor')} on {data.get('appointment_date', 'date')}")
                
                # Update appointment status based on the result
                result_str = str(result).lower() if result else ""
                print(f"DEBUG (tracked_call_mcp_endpoint): Schedule appointment result: '{result_str}'")
                
                # Check if appointment was actually scheduled successfully
                has_successfully = "successfully" in result_str
                has_appointment_scheduled = "appointment scheduled successfully" in result_str
                no_however = "however" not in result_str
                no_openings = "openings at" not in result_str
                
                print(f"DEBUG (tracked_call_mcp_endpoint): Conditions - successfully: {has_successfully}, appointment_scheduled: {has_appointment_scheduled}, no_however: {no_however}, no_openings: {no_openings}")
                
                if has_successfully and has_appointment_scheduled and no_however and no_openings:
                    ctx.appointment_status = 'Booked'
                    print(f"DEBUG (tracked_call_mcp_endpoint): Updated appointment_status to 'Booked'")
                else:
                    print(f"DEBUG (tracked_call_mcp_endpoint): Appointment not actually booked - response suggests alternatives or failure")
                    
            elif endpoint == "check_availability":
                ctx.tool_calls.append(f"Checked availability for {data.get('doctor_name', 'doctor')} on {data.get('appointment_date', 'date')}")
            elif endpoint == "reschedule_appointment":
                ctx.tool_calls.append(f"Rescheduled appointment {data.get('appointment_id', 'ID')} to {data.get('new_date', 'date')}")
                
                # Update appointment status for rescheduling
                result_str = str(result).lower() if result else ""
                if "successfully" in result_str:
                    ctx.appointment_status = 'Rescheduled'
                    print(f"DEBUG (tracked_call_mcp_endpoint): Updated appointment_status to 'Rescheduled'")
                    
            elif endpoint == "cancel_appointment":
                ctx.tool_calls.append(f"Cancelled appointment {data.get('appointment_id', 'ID')}")
                
                # Update appointment status for cancellation
                result_str = str(result).lower() if result else ""
                if "successfully" in result_str:
                    ctx.appointment_status = 'Cancelled'
                    print(f"DEBUG (tracked_call_mcp_endpoint): Updated appointment_status to 'Cancelled'")
                    
            elif endpoint == "get_available_slots":
                ctx.tool_calls.append(f"Retrieved available slots for {data.get('doctor_name', 'doctor')}")
        
        return result
    
    # Replace the function to track tool calls
    tools.call_mcp_endpoint = tracked_call_mcp_endpoint
    
    # Try multiple ways to capture conversation
    session.on("transcript", capture_transcript)
    session.on("user_speech", capture_user_message)
    session.on("agent_speech", capture_agent_response)

    async def on_session_close(ev):
        call_end = IST.localize(datetime.now()) # Use IST for call_end
        call_duration = str(call_end - ctx.call_start) if ctx.call_start else None
        call_start_str = ctx.call_start.isoformat() if ctx.call_start else None
        call_end_str = call_end.isoformat() if call_end else None
        
        print(f"DEBUG: ctx.call_start type: {type(ctx.call_start)}")
        print(f"DEBUG: ctx.call_start value: {ctx.call_start}")
        print(f"DEBUG: call_end type: {type(call_end)}")
        print(f"DEBUG: call_end value: {call_end}")
        print(f"DEBUG: Agent sending call_start: {call_start_str}")
        print(f"DEBUG: Agent sending call_end: {call_end_str}")
        call_status = "completed" # Assuming completed unless explicitly set otherwise
        appointment_status = getattr(ctx, "appointment_status", "Not Booked")

        # Generate call summary based on available data
        call_summary = "Patient called the clinic."
        
        # Try to build a better summary from conversation log and appointment status
        try:
            # Check if we have conversation log
            conversation_log = getattr(ctx, 'conversation_log', [])
            full_transcript = getattr(ctx, 'transcript', '')
            
            print(f"DEBUG: Conversation log length: {len(conversation_log)}")
            print(f"DEBUG: Full transcript length: {len(full_transcript) if full_transcript else 0}")
            
            # Build conversation text from available sources
            conversation_text = ""
            user_messages = getattr(ctx, 'user_messages', [])
            agent_responses = getattr(ctx, 'agent_responses', [])
            
            print(f"DEBUG: User messages count: {len(user_messages)}")
            print(f"DEBUG: Agent responses count: {len(agent_responses)}")
            
            # Try to build conversation from user/agent messages first
            if user_messages or agent_responses:
                all_messages = user_messages + agent_responses
                conversation_text = " ".join(all_messages)
                print(f"DEBUG: Built conversation from messages: {conversation_text[:100]}...")
            elif conversation_log:
                conversation_text = " ".join(conversation_log)
                print(f"DEBUG: Using conversation log: {conversation_text[:100]}...")
            elif full_transcript:
                conversation_text = full_transcript
                print(f"DEBUG: Using full transcript: {conversation_text[:100]}...")
            
            # Check tool calls for better summary generation
            tool_calls = getattr(ctx, 'tool_calls', [])
            print(f"DEBUG: Tool calls count: {len(tool_calls)}")
            print(f"DEBUG: Tool calls: {tool_calls}")
            
            print(f"DEBUG: Final conversation text length: {len(conversation_text)}")
            
            # Generate summary based on available data
            if tool_calls:
                # Use tool calls to create a detailed summary
                call_summary = f"Patient called the clinic. {' '.join(tool_calls)}."
                print(f"DEBUG: Generated tool-based summary: {call_summary}")
            elif conversation_text and len(conversation_text.strip()) > 10:
                # Generate a summary using the summarize_call endpoint
                try:
                    print(f"DEBUG: Attempting to summarize conversation...")
                    summary_result = await summarize_call(conversation_text)
                    if summary_result and len(summary_result.strip()) > 5:
                        call_summary = summary_result
                        print(f"DEBUG: Generated AI summary: {call_summary}")
                    else:
                        print(f"DEBUG: AI summary was empty or too short, using fallback")
                        call_summary = generate_fallback_summary(appointment_status, conversation_text)
                except Exception as e:
                    print(f"DEBUG: Error generating AI summary: {e}")
                    call_summary = generate_fallback_summary(appointment_status, conversation_text)
            else:
                print(f"DEBUG: No meaningful conversation text, using basic summary")
                call_summary = generate_fallback_summary(appointment_status, "")
                
        except Exception as e:
            print(f"DEBUG: Error in summary generation: {e}")
            call_summary = generate_fallback_summary(appointment_status, "")

        # Log basic call information
        print(f"DEBUG: Call completed - ID: {ctx.call_id}, Duration: {call_duration}, Final appointment_status: {appointment_status}")
        print(f"DEBUG: About to save call history with appointment_status: {appointment_status}")

        # Add the call history record with the summary
        await add_call_history(
            caller_number=ctx.caller_number,
            called_number=ctx.called_number,
            call_start=call_start_str,
            call_end=call_end_str,
            call_duration=call_duration,
            call_status=call_status,
            appointment_status=appointment_status,
            call_summary=call_summary,
            call_id=ctx.call_id,
            user_id=ctx.user_id,
        )
    session.on("close", lambda ev: asyncio.create_task(on_session_close(ev)))

    await session.start(
        room=ctx.room,
        agent=ClinicReceptionistAgent(
            instructions=agent_instruction,
            user_id=ctx.user_id,
            call_id=ctx.call_id,
            ctx=ctx
        ),
        room_input_options=RoomInputOptions(
            video_enabled=False,
            noise_cancellation=noise_cancellation.BVCTelephony(),
        ),
    )
    await session.generate_reply(
        instructions=session_instruction,
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))